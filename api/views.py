from django.shortcuts import render
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, generics
from django.db import transaction
from datetime import datetime
import logging
import time
import random
import numpy as np
from typing import List, Dict, Any

from horarios.models import Profesor, Materia, Curso, Horario, Aula, BloqueHorario, MateriaGrado, MateriaProfesor, DisponibilidadProfesor, ConfiguracionColegio
from horarios.application.services.generador_demand_first import GeneradorDemandFirst
from horarios.domain.validators.validador_precondiciones import ValidadorPrecondiciones
from horarios.domain.validators.validadores import prevalidar_factibilidad_dataset, validar_antes_de_persistir, construir_semana_tipo_desde_bd
from horarios.infrastructure.utils.logging_estructurado import crear_logger_estructurado
from horarios.infrastructure.adapters.exportador import exportar_horario_csv, exportar_horario_por_curso_csv, exportar_horario_por_profesor_csv
from horarios.infrastructure.utils.serialization import make_json_serializable
from .serializers import (
    ProfesorSerializer,
    MateriaSerializer,
    CursoSerializer,
    HorarioSerializer,
    AulaSerializer,
    SolverInputSerializer,
)

# Nuevos imports para jobs
try:
    from celery.result import AsyncResult
    from horarios.infrastructure.utils.tasks import generar_horarios_async, CELERY_AVAILABLE
except Exception:
    CELERY_AVAILABLE = False
    generar_horarios_async = None
    AsyncResult = None

logger = logging.getLogger(__name__)


class ProfesorList(generics.ListAPIView):
    queryset = Profesor.objects.all()
    serializer_class = ProfesorSerializer

class MateriaList(generics.ListAPIView):
    queryset = Materia.objects.all()
    serializer_class = MateriaSerializer

class CursoList(generics.ListAPIView):
    queryset = Curso.objects.all()
    serializer_class = CursoSerializer

class AulaList(generics.ListAPIView):
    queryset = Aula.objects.all()
    serializer_class = AulaSerializer

class HorarioList(generics.ListAPIView):
    queryset = Horario.objects.all()
    serializer_class = HorarioSerializer

class GenerarHorarioView(APIView):
    """
    Endpoint principal para generación de horarios con formato estándar de respuesta.
    
    Proceso:
    1. Recibe parámetros de configuración (semilla, paciencia, iteraciones).
    2. Ejecuta validaciones de precondiciones (Factibilidad matemática).
    3. Lanza el algoritmo 'Demand-First + Hill Climbing'.
    4. Persiste los resultados o devuelve preview.
    
    POST /api/generar-horario/
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        inicio_tiempo = time.time()
        logger_struct = crear_logger_estructurado()
        
        try:
            # 1. VALIDACIÓN PREVIA IMPRESCINDIBLE
            validador = ValidadorPrecondiciones()
            resultado_factibilidad = validador.validar_factibilidad_completa()
            
            if not resultado_factibilidad.es_factible:
                return Response({
                    "status": "error",
                    "mensaje": "Validación previa fallida",
                    "errores_validacion": [p.descripcion for p in resultado_factibilidad.problemas],
                    "reporte": make_json_serializable(resultado_factibilidad.reporte_detallado),
                    "tiempo_validacion_s": time.time() - inicio_tiempo
                }, status=status.HTTP_409_CONFLICT)
 
            # 1b. PREVALIDACIÓN FACTIBILIDAD DATA-DRIVEN (oferta vs demanda)
            pre = prevalidar_factibilidad_dataset()
            logger_struct.log_evento("prevalidacion_oferta_vs_demanda", pre)
            if not pre.get('viable', False):
                od = pre.get('oferta_vs_demanda', {})
                dims = od.get('dimensiones', {})
                return Response({
                    "status": "error",
                    "mensaje": "instancia_inviable",
                    "oferta_vs_demanda": od,
                    "dimensiones": dims,
                    "log_path": logger_struct.archivo_log,
                }, status=status.HTTP_400_BAD_REQUEST)

            # 2. CONFIGURACIÓN DE SEMILLA GLOBAL
            data = request.data or {}
            semilla = data.get('semilla', 42)
            preview = bool(data.get('preview', False))
            self._configurar_semilla_global(semilla)
 
            # 3. PARÁMETROS DEL ALGORITMO
            parametros = {
                'max_iteraciones': data.get('generaciones', 1000),
                'paciencia': data.get('paciencia', 100)
            }
 
            logger.info(f"Iniciando generación con semilla {semilla} y config: {parametros}, preview={preview}")
 
            # 4. EJECUCIÓN DEL ALGORITMO DEMAND-FIRST
            generador = GeneradorDemandFirst()
            resultado = generador.generar_horarios(semilla=semilla, **parametros)
 
            # 5. ANÁLISIS DEL RESULTADO
            tiempo_total = time.time() - inicio_tiempo

            if not resultado.get('exito'):
                return Response({
                    "status": "error",
                    "mensaje": "No se pudo generar una solución válida",
                    "errores": make_json_serializable(resultado.get('validacion_final', {})),
                    "tiempo_total_s": round(tiempo_total, 2),
                    "semilla": semilla,
                    "configuracion_usada": parametros,
                    "log_path": logger_struct.archivo_log
                }, status=status.HTTP_400_BAD_REQUEST)

            horarios_res = resultado.get('horarios', [])

            # Si preview: calcular diffs y no persistir
            if preview:
                diffs = self._calcular_diffs(horarios_res)
                return Response({
                    "status": "preview",
                    "differences": diffs,
                    "tiempo_total_s": round(tiempo_total, 2),
                    "semilla": semilla,
                    "log_path": logger_struct.archivo_log,
                }, status=status.HTTP_200_OK)

            # Validación final antes de persistir
            try:
                validacion = validar_antes_de_persistir(horarios_res)
            except Exception as e:
                logger.error(f"Error validando resultado antes de persistir: {e}")
                return Response({
                    "status": "error",
                    "mensaje": "Error validando horarios generados",
                    "error": str(e),
                    "log_path": logger_struct.archivo_log,
                }, status=status.HTTP_400_BAD_REQUEST)

            if not validacion.es_valido:
                return Response({
                    "status": "error",
                    "mensaje": "Horarios generados no pasan validación final",
                    "errores": make_json_serializable(validacion.errores),
                    "advertencias": make_json_serializable(validacion.advertencias),
                    "log_path": logger_struct.archivo_log,
                }, status=status.HTTP_400_BAD_REQUEST)

            horarios_generados = self._persistir_resultado_atomico(resultado)
 
            # 7. RESPUESTA ESTÁNDAR EXITOSA
            # Usamos 'pre' para los datos de oferta vs demanda ya que GeneradorDemandFirst no lo devuelve en 'resultado'
            od = pre.get('oferta_vs_demanda', {})
            dims = od.get('dimensiones', {
                "cursos": Curso.objects.count(),
                "materias": Materia.objects.count(),
                "profesores": Profesor.objects.count(),
                "slots": BloqueHorario.objects.filter(tipo='clase').count() * len(set(DisponibilidadProfesor.objects.values_list('dia', flat=True)))
            })
            return Response({
                "status": "success",
                "timeout": False,
                "objetivo": {
                    "fitness_final": resultado.get('calidad', 0),
                    "generaciones_completadas": resultado.get('estadisticas', {}).get('slots_generados', 0),
                    "convergencia": True
                },
                "solapes": 0,
                "huecos": 0,
                "tiempo_total_s": round(tiempo_total, 2),
                "semilla": semilla,
                "asignaciones": horarios_generados,
                "dimensiones": dims,
                "oferta_vs_demanda": od,
                "log_path": logger_struct.archivo_log,
            }, status=status.HTTP_200_OK)
        except Exception as e:
            tiempo_total = time.time() - inicio_tiempo
            logger.error(f"Error crítico en generación: {str(e)}", exc_info=True)
 
            return Response({
                "status": "error",
                "mensaje": "Error interno del servidor",
                "error": str(e),
                "tiempo_total_s": round(tiempo_total, 2),
                "semilla": semilla if 'semilla' in locals() else None,
                "log_path": logger_struct.archivo_log
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def _configurar_semilla_global(self, semilla):
        """Configura semilla global para reproducibilidad completa"""
        # Semillas para todas las librerías de random
        random.seed(semilla)
        np.random.seed(semilla)
        
        # Intentar configurar semilla para otras librerías si están disponibles
        try:
            import os
            os.environ['PYTHONHASHSEED'] = str(semilla)
        except:
            pass
        
        # Documentar la semilla usada
        logger.info(f"Semilla global configurada: {semilla}")
        
        # Guardar en archivo de última ejecución con formato estructurado
        try:
            with open('logs/ultima_ejecucion.txt', 'w') as f:
                f.write(f"Semilla: {semilla}\n")
                f.write(f"Timestamp: {datetime.now().isoformat()}\n")
                f.write(f"Config: {self.request.data if hasattr(self, 'request') else 'N/A'}\n")
        except Exception as e:
            logger.warning(f"No se pudo guardar archivo de última ejecución: {e}")
    

    
    def _persistir_resultado_atomico(self, resultado):
        """Persistencia rápida y atómica del resultado."""
        from django.db import transaction
        from horarios.models import Horario
        
        try:
            with transaction.atomic():
                # Promover por curso: borrar e insertar en lote
                cursos_afectados = set([h['curso_id'] for h in resultado.get('horarios', []) if 'curso_id' in h])
                if cursos_afectados:
                    Horario.objects.filter(curso_id__in=cursos_afectados).delete()
                    objetos = []
                    for h in resultado.get('horarios', []):
                        objetos.append(Horario(
                            curso_id=h['curso_id'], materia_id=h['materia_id'], profesor_id=h['profesor_id'],
                            aula_id=h.get('aula_id'), dia=h['dia'], bloque=h['bloque']
                        ))
                    Horario.objects.bulk_create(objetos, batch_size=1000)
                    return len(objetos)
                return 0
        except Exception as e:
            logger.error(f"Error en persistencia atómica: {e}")
            raise

    def _calcular_diffs(self, nuevos_horarios: List[Dict]) -> Dict[str, Any]:
        actuales = list(Horario.objects.all().values('curso_id','profesor_id','materia_id','dia','bloque'))
        actuales_set = set((h['curso_id'], h['profesor_id'], h['materia_id'], h['dia'], h['bloque']) for h in actuales)
        nuevos_set = set((h['curso_id'], h['profesor_id'], h['materia_id'], h['dia'], h['bloque']) for h in nuevos_horarios)
        added = nuevos_set - actuales_set
        removed = actuales_set - nuevos_set
        # Agrupar por curso y por profesor
        def agrupar_por(items, idx):
            d = {}
            for it in items:
                key = it[idx]
                d.setdefault(key, []).append({'curso_id': it[0], 'profesor_id': it[1], 'materia_id': it[2], 'dia': it[3], 'bloque': it[4]})
            return d
        return {
            'added_by_curso': agrupar_por(added, 0),
            'removed_by_curso': agrupar_por(removed, 0),
            'added_by_profesor': agrupar_por(added, 1),
            'removed_by_profesor': agrupar_por(removed, 1),
        }

class ValidarPrerrequisitosView(APIView):
    """
    Endpoint para validación previa de prerrequisitos
    GET /api/validar-prerrequisitos/
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Valida todos los prerrequisitos críticos"""
        try:
            errores = self._validar_todos_prerrequisitos()
            advertencias = self._generar_advertencias()
            
            return Response({
                "status": "success" if not errores else "error",
                "errores_criticos": errores,
                "advertencias": advertencias,
                "es_factible": len(errores) == 0,
                "timestamp": datetime.now().isoformat()
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error en validación de prerrequisitos: {e}")
            return Response({
                "status": "error",
                "mensaje": "Error en validación",
                "error": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def _validar_todos_prerrequisitos(self):
        """Valida todos los prerrequisitos críticos"""
        errores = []
        
        # 1. Profesores sin disponibilidad
        profesores_sin_disponibilidad = Profesor.objects.exclude(
            id__in=DisponibilidadProfesor.objects.values_list('profesor', flat=True)
        )
        if profesores_sin_disponibilidad.exists():
            nombres = [p.nombre for p in profesores_sin_disponibilidad]
            errores.append({
                "tipo": "profesores_sin_disponibilidad",
                "mensaje": f"Profesores sin disponibilidad: {', '.join(nombres)}",
                "count": len(nombres),
                "profesores": nombres
            })
        
        # 2. Materias del plan sin profesores habilitados
        materias_sin_profesor = MateriaGrado.objects.exclude(
            materia__in=MateriaProfesor.objects.values_list('materia', flat=True)
        )
        if materias_sin_profesor.exists():
            detalles = [f"{mg.materia.nombre} ({mg.grado.nombre})" for mg in materias_sin_profesor]
            errores.append({
                "tipo": "materias_sin_profesor",
                "mensaje": f"Materias sin profesor: {', '.join(detalles)}",
                "count": len(detalles),
                "materias": detalles
            })
        
        # 3. Bloques por semana inviables
        materias_inviables = []
        for mg in MateriaGrado.objects.all():
            if mg.materia.bloques_por_semana > 40:
                materias_inviables.append(f"{mg.materia.nombre} ({mg.grado.nombre}): {mg.materia.bloques_por_semana} bloques")
        
        if materias_inviables:
            errores.append({
                "tipo": "bloques_por_semana_inviables",
                "mensaje": f"Materias con bloques por semana inviables: {', '.join(materias_inviables)}",
                "count": len(materias_inviables),
                "materias": materias_inviables
            })
        
        # 4. Bloques no tipo "clase" en el dominio
        bloques_no_clase = BloqueHorario.objects.exclude(tipo='clase')
        if bloques_no_clase.exists():
            tipos = list(set([b.tipo for b in bloques_no_clase]))
            errores.append({
                "tipo": "bloques_no_clase",
                "mensaje": f"Existen bloques de tipo no 'clase': {', '.join(tipos)}",
                "count": len(tipos),
                "tipos": tipos
            })
        
        return errores
    
    def _generar_advertencias(self):
        """Genera advertencias no críticas"""
        advertencias = []
        
        # Verificar capacidad vs requerimientos basados en datos reales
        total_bloques_requeridos = sum(
            mg.materia.bloques_por_semana for mg in MateriaGrado.objects.all()
        )
        try:
            semana = construir_semana_tipo_desde_bd()
            num_dias = len(semana['dias'])
            num_bloques = len(semana['bloques_clase'])
        except Exception:
            num_dias = 5
            num_bloques = 6
        capacidad_total = Aula.objects.count() * num_dias * num_bloques
        
        if total_bloques_requeridos > capacidad_total * 0.8:
            advertencias.append({
                "tipo": "capacidad_alta",
                "mensaje": f"Factor de ocupación alto: {total_bloques_requeridos}/{capacidad_total} ({(total_bloques_requeridos/capacidad_total if capacidad_total else 0):.1%})",
                "bloques_requeridos": total_bloques_requeridos,
                "capacidad_disponible": capacidad_total
            })
        
        return advertencias


class EstadoSistemaView(APIView):
    """
    Endpoint para obtener el estado actual del sistema
    GET /api/estado-sistema/
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Retorna el estado completo del sistema"""
        try:
            estado = {
                "recursos": self._contar_recursos(),
                "configuracion": self._obtener_configuracion(),
                "estado_horarios": self._obtener_estado_horarios(),
                "metricas": self._calcular_metricas(),
                "timestamp": datetime.now().isoformat()
            }
            
            return Response(estado, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error obteniendo estado del sistema: {e}")
            return Response({
                "status": "error",
                "mensaje": "Error obteniendo estado",
                "error": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def _contar_recursos(self):
        """Cuenta los recursos disponibles"""
        return {
            "cursos": Curso.objects.count(),
            "profesores": Profesor.objects.count(),
            "materias": Materia.objects.count(),
            "aulas": Aula.objects.count(),
            "horarios": Horario.objects.count(),
            "bloques_horario": BloqueHorario.objects.count()
        }
    
    def _obtener_configuracion(self):
        """Obtiene la configuración del sistema"""
        try:
            config = ConfiguracionColegio.objects.first()
            try:
                semana = construir_semana_tipo_desde_bd()
                dias = semana['dias']
                bloques = semana['bloques_clase']
            except Exception:
                dias = ["lunes", "martes", "miércoles", "jueves", "viernes"]
                bloques = list(BloqueHorario.objects.filter(tipo='clase').order_by('numero').values_list('numero', flat=True)) or [1,2,3,4,5,6]
            return {
                "dias_clase": len(dias),
                "bloques_por_dia": len(bloques),
                "semana_laboral": dias,
                "configuracion_bd": {
                    "jornada": getattr(config, 'jornada', None),
                    "duracion_bloque": getattr(config, 'duracion_bloque', None),
                    "dias_clase_str": getattr(config, 'dias_clase', None),
                }
            }
        except Exception:
            return {
                "dias_clase": 5,
                "bloques_por_dia": 6,
                "semana_laboral": ["lunes", "martes", "miércoles", "jueves", "viernes"]
            }
    
    def _obtener_estado_horarios(self):
        """Obtiene el estado de los horarios"""
        total_horarios = Horario.objects.count()
        if total_horarios == 0:
            return {
                "estado": "sin_horarios",
                "mensaje": "No hay horarios generados",
                "total": 0
            }
        
        # Verificar validez de horarios existentes usando validación data-driven
        try:
            horarios_qs = Horario.objects.select_related('curso', 'materia', 'profesor', 'aula').all()
            horarios_data = []
            for h in horarios_qs:
                horarios_data.append({
                    'curso_id': h.curso_id,
                    'materia_id': h.materia_id,
                    'profesor_id': h.profesor_id,
                    'aula_id': h.aula_id,
                    'dia': h.dia,
                    'bloque': h.bloque,
                    'curso_nombre': h.curso.nombre,
                    'materia_nombre': h.materia.nombre,
                    'profesor_nombre': h.profesor.nombre,
                })
            validacion = validar_antes_de_persistir(horarios_data)
            return {
                "estado": "con_horarios" if validacion.es_valido else "con_horarios_con_errores",
                "mensaje": f"Hay {total_horarios} horarios generados",
                "total": total_horarios,
                "validacion": {
                    "es_valido": validacion.es_valido,
                    "errores": [e.__dict__ for e in validacion.errores],
                    "advertencias": [a.__dict__ for a in validacion.advertencias],
                    "estadisticas": validacion.estadisticas,
                }
            }
        except Exception as e:
            return {
                "estado": "con_horarios_invalidos",
                "mensaje": f"Hay {total_horarios} horarios pero la validación falló",
                "total": total_horarios,
                "error_validacion": str(e)
            }
    
    def _calcular_metricas(self):
        """Calcula métricas del sistema"""
        try:
            # Calcular bloques requeridos vs disponibles
            total_bloques_requeridos = sum(
                mg.materia.bloques_por_semana for mg in MateriaGrado.objects.all()
            )
            try:
                semana = construir_semana_tipo_desde_bd()
                num_dias = len(semana['dias'])
                num_bloques = len(semana['bloques_clase'])
            except Exception:
                num_dias = 5
                num_bloques = 6
            capacidad_total = Aula.objects.count() * num_dias * num_bloques
            
            return {
                "bloques_requeridos": total_bloques_requeridos,
                "capacidad_disponible": capacidad_total,
                "factor_ocupacion": round((total_bloques_requeridos / capacidad_total) if capacidad_total else 0, 3),
                "capacidad_excedente": capacidad_total - total_bloques_requeridos
            }
        except Exception as e:
            return {
                "error": f"Error calculando métricas: {str(e)}"
            }

class JobsGenerarHorarioView(APIView):
	permission_classes = [IsAuthenticated]
	def post(self, request):
		data = request.data or {}
		colegio_id = int(data.get('colegio_id', 1))
		params = data.get('params', {})
		if not CELERY_AVAILABLE:
			return Response({
				'status': 'error', 'mensaje': 'Celery no disponible', 'detalle': 'Instale/Configure broker'
			}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
		# Enqueue
		task = generar_horarios_async.delay(colegio_id, params)
		return Response({'status': 'queued', 'task_id': task.id}, status=status.HTTP_202_ACCEPTED)

class JobsEstadoView(APIView):
	permission_classes = [IsAuthenticated]
	def get(self, request, task_id:str):
		if not CELERY_AVAILABLE or AsyncResult is None:
			return Response({'status': 'unknown', 'mensaje': 'Celery no disponible'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
		res = AsyncResult(task_id)
		meta = res.info if isinstance(res.info, dict) else {'info': str(res.info)}
		map_state = {
			'PENDING': 'en-cola',
			'STARTED': 'corriendo',
			'PROGRESS': 'corriendo',
			'SUCCESS': 'listo',
			'FAILURE': 'fallo',
			'REVOKED': 'cancelado'
		}
		return Response({'task_id': task_id, 'estado': map_state.get(res.state, res.state), 'meta': meta})

class JobsCancelarView(APIView):
	permission_classes = [IsAuthenticated]
	def post(self, request, task_id:str):
		if not CELERY_AVAILABLE or AsyncResult is None:
			return Response({'status': 'error', 'mensaje': 'Celery no disponible'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
		res = AsyncResult(task_id)
		try:
			res.revoke(terminate=True)
			return Response({'status': 'ok', 'task_id': task_id, 'estado': 'cancelado'})
		except Exception as e:
			return Response({'status': 'error', 'mensaje': str(e)}, status=status.HTTP_400_BAD_REQUEST)

class RegenerarParcialView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request):
        data = request.data or {}
        cursos_objetivo = data.get('curso_ids', [])
        preview = bool(data.get('preview', True))
        gestor = crear_gestor_slots_bloqueados()
        # Bloquear todo lo existente excepto los cursos objetivo
        if cursos_objetivo:
            todos = Horario.objects.values('curso_id','materia_id','profesor_id','dia','bloque')
            for h in todos:
                if h['curso_id'] not in cursos_objetivo:
                    gestor.bloquear_slot(h['curso_id'], h['materia_id'], h['profesor_id'], h['dia'], h['bloque'], razon='regeneracion_parcial')
        # Correr GA
        config = {
            'poblacion_size': data.get('poblacion_size', 120),
            'generaciones': data.get('generaciones', 300),
            'timeout_seg': data.get('timeout_seg', 180),
            'prob_cruce': data.get('prob_cruce', 0.9),
            'prob_mutacion': data.get('prob_mutacion', 0.15),
            'elite': data.get('elite', 6),
            'paciencia': data.get('paciencia', 30),
            'workers': data.get('workers', 2),
            'semilla': data.get('semilla', 42)
        }
        resultado = generar_horarios_genetico(**config)
        horarios_res = resultado.get('horarios', [])
        if preview:
            diffs = self._calcular_diffs(horarios_res)
            return Response({'status':'preview','differences':diffs})
        validacion = validar_antes_de_persistir(horarios_res)
        if not validacion.es_valido:
            return Response({'status':'error','errores':[e.__dict__ for e in validacion.errores]}, status=400)
        creados = self._persistir_resultado_atomico({'horarios': horarios_res})
        return Response({'status':'success','asignaciones': creados})
    def _calcular_diffs(self, nuevos_horarios):
        actuales = list(Horario.objects.all().values('curso_id','profesor_id','materia_id','dia','bloque'))
        actuales_set = set((h['curso_id'], h['profesor_id'], h['materia_id'], h['dia'], h['bloque']) for h in actuales)
        nuevos_set = set((h['curso_id'], h['profesor_id'], h['materia_id'], h['dia'], h['bloque']) for h in nuevos_horarios)
        added = nuevos_set - actuales_set
        removed = actuales_set - nuevos_set
        return {'added': list(added), 'removed': list(removed)}

class ExportCursoView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request, curso_id: int, formato: str = 'csv'):
        if formato == 'csv':
            return exportar_horario_por_curso_csv()
        return Response({'status':'error','mensaje':'formato no soportado'}, status=400)

class ExportProfesorView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request, profesor_id: int, formato: str = 'csv'):
        if formato == 'csv':
            return exportar_horario_por_profesor_csv()
        return Response({'status':'error','mensaje':'formato no soportado'}, status=400)

class SolverView(APIView):
    """
    Motor de Cálculo Puro:
    Recibe un snapshot completo del problema (JSON), lo carga, resuelve y devuelve el resultado.
    Ideal para integración server-to-server.
    """
    permission_classes = [AllowAny]
    def post(self, request):
        serializer = SolverInputSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        data = serializer.validated_data
        try:
            with transaction.atomic():
                self._limpiar_base_de_datos()
                mapeo_materias = {}
                mapeo_profesores = {}
                conf = data.get('configuracion', {})
                dias = conf.get('dias_clase', 'lunes,martes,miércoles,jueves,viernes').lower()
                ConfiguracionColegio.objects.create(
                    dias_clase=dias,
                    bloques_por_dia=conf.get('bloques_por_dia', 6),
                    duracion_bloque=conf.get('duracion_bloque', 60),
                    jornada=conf.get('jornada', 'mañana')
                )
                self._generar_bloques_y_slots(dias, conf.get('bloques_por_dia', 6))
                for m_data in data['materias']:
                    materia = Materia.objects.create(
                        nombre=m_data['nombre'],
                        bloques_por_semana=0,
                        requiere_aula_especial=m_data.get('aula_especial', False)
                    )
                    mapeo_materias[m_data['nombre']] = materia
                for p_data in data['profesores']:
                    profesor = Profesor.objects.create(nombre=p_data['nombre'])
                    mapeo_profesores[p_data['nombre']] = profesor
                    disponibilidad = p_data.get('disponibilidad', [])
                    if disponibilidad:
                        for disp in disponibilidad:
                            DisponibilidadProfesor.objects.create(
                                profesor=profesor,
                                dia=disp['dia'].lower(),
                                bloque_inicio=disp['bloque_inicio'],
                                bloque_fin=disp['bloque_fin']
                            )
                    else:
                        # Si no se especifica disponibilidad, asumimos disponibilidad total
                        dias_list = [d.strip() for d in dias.split(',')]
                        bloques_dia = conf.get('bloques_por_dia', 6)
                        for dia in dias_list:
                            DisponibilidadProfesor.objects.create(
                                profesor=profesor,
                                dia=dia,
                                bloque_inicio=1,
                                bloque_fin=bloques_dia
                            )
                    if 'materias_capaces' in p_data:
                        for mat_nombre in p_data['materias_capaces']:
                            if mat_nombre in mapeo_materias:
                                MateriaProfesor.objects.create(
                                    profesor=profesor,
                                    materia=mapeo_materias[mat_nombre]
                                )
                from horarios.models import Grado, MateriaGrado, CursoMateriaRequerida, ConfiguracionCurso
                for c_data in data['cursos']:
                    grado_nombre = c_data['grado']
                    grado, _ = Grado.objects.get_or_create(nombre=grado_nombre)
                    curso = Curso.objects.create(nombre=c_data['nombre'], grado=grado)
                    Aula.objects.create(nombre=f"Salón {curso.nombre}", capacidad=40, tipo='general')
                    plan = c_data.get('plan_estudios', {})
                    total_bloques_plan = sum(plan.values())
                    # Ajustar automáticamente la configuración del curso para que coincida con la carga real
                    ConfiguracionCurso.objects.create(
                        curso=curso,
                        slots_objetivo=total_bloques_plan, # Usar el campo correcto del modelo
                        permite_relleno=False # Desactivar relleno si no se usa
                    )
                    for mat_nombre, bloques in plan.items():
                        if mat_nombre in mapeo_materias:
                            materia = mapeo_materias[mat_nombre]
                            MateriaGrado.objects.get_or_create(grado=grado, materia=materia)
                            CursoMateriaRequerida.objects.create(
                                curso=curso,
                                materia=materia,
                                bloques_requeridos=bloques
                            )
                # Materializar datos antes de invocar al generador
                from horarios.management.commands.sync_aux_tables import Command as SyncCommand
                sync_cmd = SyncCommand()
                # 1. Crear Slots físicos
                sync_cmd._sync_slots()
                # 2. Materializar disponibilidad docente (crucial para _profesor_disponible)
                sync_cmd._materialize_profesor_slot()
                # 3. Materializar requerimientos por curso (YA LO HICIMOS MANUALMENTE, NO SOBREESCRIBIR)
                # sync_cmd._sync_curso_materia_requerida()

                generador = GeneradorDemandFirst()
                resultado = generador.generar_horarios()
                if resultado['exito']:
                    # Persistir resultados en la base de datos
                    objs = []
                    for h in resultado.get('horarios', []):
                         objs.append(Horario(
                             curso_id=h['curso_id'],
                             materia_id=h['materia_id'],
                             profesor_id=h['profesor_id'],
                             aula_id=h.get('aula_id'),
                             dia=h['dia'],
                             bloque=h['bloque']
                         ))
                    Horario.objects.bulk_create(objs)
                    
                    horarios = Horario.objects.all()
                    serializer_out = HorarioSerializer(horarios, many=True)
                    return Response({
                        "status": "success",
                        "metadata": {
                            "total_horarios": len(horarios),
                            "fitness": resultado.get('fitness_score', 0)
                        },
                        "horarios": serializer_out.data
                    })
                else:
                    return Response({
                        "status": "failure",
                        "mensaje": "No se pudo encontrar una solución válida",
                        "detalles": make_json_serializable(resultado)
                    }, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
        except Exception as e:
            logger.exception("Error en SolverView")
            return Response({"status": "error", "mensaje": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def _limpiar_base_de_datos(self):
        from horarios.models import MateriaRelleno, CursoMateriaRequerida, ProfesorSlot, Slot
        Horario.objects.all().delete()
        MateriaRelleno.objects.all().delete()
        CursoMateriaRequerida.objects.all().delete()
        ProfesorSlot.objects.all().delete()
        Slot.objects.all().delete()
        MateriaProfesor.objects.all().delete()
        MateriaGrado.objects.all().delete()
        DisponibilidadProfesor.objects.all().delete()
        Curso.objects.all().delete()
        Aula.objects.all().delete()
        from horarios.models import Grado
        Grado.objects.all().delete()
        Profesor.objects.all().delete()
        Materia.objects.all().delete()
        BloqueHorario.objects.all().delete()
        ConfiguracionColegio.objects.all().delete()

    def _generar_bloques_y_slots(self, dias_str, bloques_por_dia):
        from datetime import time
        for i in range(1, bloques_por_dia + 1):
            BloqueHorario.objects.create(
                numero=i,
                hora_inicio=time(7 + i, 0),
                hora_fin=time(7 + i, 50),
                tipo='clase'
            )
