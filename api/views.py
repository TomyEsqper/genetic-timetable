from django.shortcuts import render
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, generics
from datetime import datetime
import logging
import time
import random
import numpy as np

from horarios.models import Profesor, Materia, Curso, Horario, Aula, BloqueHorario, MateriaGrado, MateriaProfesor, DisponibilidadProfesor, ConfiguracionColegio
from horarios.genetico_funcion import generar_horarios_genetico, validar_prerrequisitos_criticos
from horarios.validadores import prevalidar_factibilidad_dataset, validar_antes_de_persistir, construir_semana_tipo_desde_bd
from horarios.logging_estructurado import crear_logger_genetico
from .serializers import (
    ProfesorSerializer,
    MateriaSerializer,
    CursoSerializer,
    HorarioSerializer,
    AulaSerializer,
)

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
    Endpoint principal para generación de horarios con formato estándar de respuesta
    POST /api/generar-horario/
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        inicio_tiempo = time.time()
        logger_struct = crear_logger_genetico()
        
        try:
            # 1. VALIDACIÓN PREVIA IMPRESCINDIBLE
            errores_validacion = validar_prerrequisitos_criticos()
            if errores_validacion:
                return Response({
                    "status": "error",
                    "mensaje": "Validación previa fallida",
                    "errores_validacion": errores_validacion,
                    "tiempo_validacion_s": time.time() - inicio_tiempo
                }, status=status.HTTP_400_BAD_REQUEST)
 
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
            self._configurar_semilla_global(semilla)
 
            # 3. PARÁMETROS DEL ALGORITMO
            config = {
                'poblacion_size': data.get('poblacion_size', 200),
                'generaciones': data.get('generaciones', 800),
                'timeout_seg': data.get('timeout_seg', 900),
                'prob_cruce': data.get('prob_cruce', 0.9),
                'prob_mutacion': data.get('prob_mutacion', 0.15),
                'elite': data.get('elite', 10),
                'paciencia': data.get('paciencia', 50),
                'workers': data.get('workers', 2),
                'semilla': semilla
            }
 
            logger.info(f"Iniciando generación con semilla {semilla} y config: {config}")
 
            # 4. EJECUCIÓN DEL ALGORITMO GENÉTICO
            resultado = generar_horarios_genetico(**config)
 
            # 5. ANÁLISIS DEL RESULTADO
            tiempo_total = time.time() - inicio_tiempo
 
            if resultado.get('exito'):
                # 6. PERSISTENCIA RÁPIDA DEL RESULTADO
                # Validación final antes de persistir
                horarios_res = resultado.get('horarios', [])
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
                        "errores": [e.__dict__ for e in validacion.errores],
                        "advertencias": [a.__dict__ for a in validacion.advertencias],
                        "log_path": logger_struct.archivo_log,
                    }, status=status.HTTP_400_BAD_REQUEST)

                horarios_generados = self._persistir_resultado_atomico(resultado)
 
                # 7. RESPUESTA ESTÁNDAR EXITOSA
                od = resultado.get('oferta_vs_demanda', {})
                dims = od.get('dimensiones', {
                    "cursos": Curso.objects.count(),
                    "materias": Materia.objects.count(),
                    "profesores": Profesor.objects.count(),
                    "slots": BloqueHorario.objects.filter(tipo='clase').count() * len(set(DisponibilidadProfesor.objects.values_list('dia', flat=True)))
                })
                return Response({
                    "status": "success",
                    "objetivo": {
                        "fitness_final": resultado.get('mejor_fitness', 0),
                        "generaciones_completadas": resultado.get('generaciones_completadas', 0),
                        "convergencia": resultado.get('convergencia', False)
                    },
                    "penalizaciones": {
                        "choques_profesores": len(resultado.get('choques', [])),
                        "asignaciones_invalidas": len(resultado.get('asignaciones_invalidas', [])),
                        "diferencias_horas": len(resultado.get('diferencias', []))
                    },
                    "solapes": 0,
                    "huecos": resultado.get('huecos', 0),
                    "tiempo_total_s": round(tiempo_total, 2),
                    "semilla": semilla,
                    "asignaciones": horarios_generados,
                    "dimensiones": dims,
                    "oferta_vs_demanda": od,
                    "diferencias_finales": resultado.get('diferencias_finales', []),
                    "log_path": logger_struct.archivo_log,
                    "metricas_adicionales": {
                        "poblacion_size": config['poblacion_size'],
                        "generaciones": config['generaciones'],
                        "prob_cruce": config['prob_cruce'],
                        "prob_mutacion": config['prob_mutacion']
                    }
                }, status=status.HTTP_200_OK)
            else:
                # 8. RESPUESTA ESTÁNDAR DE ERROR
                return Response({
                    "status": "error",
                    "mensaje": "No se pudo generar una solución válida",
                    "errores": resultado,
                    "tiempo_total_s": round(tiempo_total, 2),
                    "semilla": semilla,
                    "configuracion_usada": config,
                    "log_path": logger_struct.archivo_log
                }, status=status.HTTP_400_BAD_REQUEST)
                 
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
        """Persistencia rápida y atómica del resultado con inserción masiva optimizada"""
        from django.db import transaction
        
        try:
            with transaction.atomic():
                # Limpiar horarios existentes de cursos afectados
                cursos_afectados = set()
                for horario_data in resultado.get('horarios', []):
                    cursos_afectados.add(horario_data['curso_id'])
                
                if cursos_afectados:
                    Horario.objects.filter(curso_id__in=cursos_afectados).delete()
                    logger.info(f"Limpiados horarios existentes para {len(cursos_afectados)} cursos")
                
                # Crear horarios en lote con validación previa
                horarios_nuevos = []
                for horario_data in resultado.get('horarios', []):
                    # Validar que los datos sean consistentes
                    if all(key in horario_data for key in ['curso_id', 'materia_id', 'profesor_id', 'dia', 'bloque']):
                        horario = Horario(
                            curso_id=horario_data['curso_id'],
                            materia_id=horario_data['materia_id'],
                            profesor_id=horario_data['profesor_id'],
                            aula_id=horario_data.get('aula_id'),
                            dia=horario_data['dia'],
                            bloque=horario_data['bloque']
                        )
                        horarios_nuevos.append(horario)
                    else:
                        logger.warning(f"Datos de horario incompletos: {horario_data}")
                
                # Inserción masiva optimizada
                if horarios_nuevos:
                    # Usar batch_size para evitar problemas de memoria con muchos registros
                    batch_size = 1000
                    for i in range(0, len(horarios_nuevos), batch_size):
                        batch = horarios_nuevos[i:i + batch_size]
                        Horario.objects.bulk_create(batch, ignore_conflicts=False)
                    
                    logger.info(f"Persistidos {len(horarios_nuevos)} horarios en transacción atómica")
                    return len(horarios_nuevos)
                else:
                    logger.warning("No se encontraron horarios válidos para persistir")
                    return 0
                
        except Exception as e:
            logger.error(f"Error en persistencia atómica: {e}")
            raise

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
