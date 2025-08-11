from django.shortcuts import render
from rest_framework.permissions import IsAuthenticated

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, generics
from datetime import datetime

from horarios.models import Profesor, Materia, Curso, Horario, Aula, BloqueHorario
from horarios.genetico_funcion import generar_horarios_genetico
from .serializers import (
    ProfesorSerializer,
    MateriaSerializer,
    CursoSerializer,
    HorarioSerializer,
    AulaSerializer,
)


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
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            # Obtener parámetros del request con defaults
            data = request.data or {}
            poblacion_size = data.get('tam_poblacion', 80)
            generaciones = data.get('generaciones', 500)
            prob_cruce = data.get('prob_cruce', 0.85)
            prob_mutacion = data.get('prob_mutacion', 0.25)
            elite = data.get('elite', 4)
            paciencia = data.get('paciencia', 25)
            timeout_seg = data.get('timeout_seg', 180)
            semilla = data.get('semilla', 42)
            workers = data.get('workers', None)
            
            # Ejecutar algoritmo genético robusto
            resultado = generar_horarios_genetico(
                poblacion_size=poblacion_size,
                generaciones=generaciones,
                prob_cruce=prob_cruce,
                prob_mutacion=prob_mutacion,
                elite=elite,
                paciencia=paciencia,
                timeout_seg=timeout_seg,
                semilla=semilla,
                workers=workers
            )
            
            # Verificar resultado
            if resultado.get('status') == 'error':
                return Response({
                    "status": "error",
                    "mensaje": resultado.get('mensaje', 'Error desconocido'),
                    "detalles": resultado.get('errores', [])
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Respuesta exitosa
            return Response({
                "status": "ok",
                "mensaje": "Horario generado exitosamente",
                "metricas": {
                    "generaciones_completadas": resultado.get('generaciones_completadas'),
                    "tiempo_total_segundos": resultado.get('tiempo_total_segundos'),
                    "mejor_fitness_final": resultado.get('mejor_fitness_final'),
                    "conflictos_finales": resultado.get('conflictos_finales'),
                    "total_horarios_generados": resultado.get('total_horarios_generados'),
                    "validacion_final": resultado.get('validacion_final', {})
                },
                "resumen_por_curso": self._generar_resumen_por_curso()
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error en generación de horarios: {str(e)}", exc_info=True)
            
            return Response({
                "status": "error",
                "mensaje": "Error interno del servidor durante la generación de horarios",
                "detalle": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def _generar_resumen_por_curso(self):
        """Genera un resumen de horarios por curso."""
        from horarios.models import Horario, Curso, Materia, Profesor
        
        resumen = {}
        horarios = Horario.objects.select_related('curso', 'materia', 'profesor').all()
        
        for horario in horarios:
            curso_nombre = horario.curso.nombre
            if curso_nombre not in resumen:
                resumen[curso_nombre] = {
                    'total_asignaciones': 0,
                    'materias': set(),
                    'profesores': set()
                }
            
            resumen[curso_nombre]['total_asignaciones'] += 1
            resumen[curso_nombre]['materias'].add(horario.materia.nombre)
            resumen[curso_nombre]['profesores'].add(horario.profesor.nombre)
        
        # Convertir sets a listas para serialización JSON
        for curso in resumen.values():
            curso['materias'] = list(curso['materias'])
            curso['profesores'] = list(curso['profesores'])
        
        return resumen
    
    def _validar_prerrequisitos(self):
        """Valida que se cumplan todos los prerrequisitos para generar horarios."""
        errores = []
        
        # Verificar que todos los cursos tengan aula fija
        cursos_sin_aula = Curso.objects.filter(aula_fija__isnull=True)
        if cursos_sin_aula.exists():
            errores.append(f"Los siguientes cursos no tienen aula fija asignada: {', '.join([c.nombre for c in cursos_sin_aula])}")
        
        # Verificar que existan bloques de tipo 'clase'
        bloques_clase = BloqueHorario.objects.filter(tipo='clase')
        if not bloques_clase.exists():
            errores.append("No existen bloques de tipo 'clase' configurados")
        
        # Verificar que cada MateriaGrado tenga al menos un profesor apto
        from horarios.models import MateriaGrado, MateriaProfesor
        for mg in MateriaGrado.objects.all():
            profesores_aptos = MateriaProfesor.objects.filter(materia=mg.materia)
            if not profesores_aptos.exists():
                errores.append(f"La materia '{mg.materia.nombre}' del grado '{mg.grado.nombre}' no tiene profesores asignados")
        
        return errores

class GenerarHorarioDesacopladoView(APIView):
    def post(self, request):
        try:
            data = request.data
            config = data["configuracion"]
            dias = config["dias_clase"]
            bloques_definidos = {b["numero"]: (b["hora_inicio"], b["hora_fin"]) for b in config["bloques"]}

            cursos = data["cursos"]
            profesores = data["profesores"]
            materias = data["materias"]
            aulas = data["aulas"]
            materia_profesor = data["materia_profesor"]
            materia_grado = data["materia_grado"]
            grados = {g["id"]: g["nombre"] for g in data["grados"]}

            # Simulación muy básica para demostrar la estructura
            horarios = []
            bloque_actual = 1
            dia_actual = 0

            for curso in cursos:
                grado_id = curso["grado_id"]
                grado_nombre = grados.get(grado_id, "")
                for mg in materia_grado:
                    if mg["grado_id"] == grado_id:
                        materia = next((m for m in materias if m["id"] == mg["materia_id"]), None)
                        profesor = next((p for mp in materia_profesor if mp["materia_id"] == materia["id"] and (p := next((pr for pr in profesores if pr["id"] == mp["profesor_id"]), None))), None)
                        aula = aulas[0] if aulas else None

                        if materia and profesor and aula:
                            dia = dias[dia_actual % len(dias)]
                            hora_inicio, hora_fin = bloques_definidos[bloque_actual]

                            horarios.append({
                                "curso": curso["nombre"],
                                "grado": grado_nombre,
                                "dia": dia,
                                "bloque": bloque_actual,
                                "hora_inicio": hora_inicio,
                                "hora_fin": hora_fin,
                                "materia": materia["nombre"],
                                "profesor": profesor["nombre"],
                                "aula": aula["nombre"]
                            })

                            bloque_actual += 1
                            if bloque_actual > config["bloques_por_dia"]:
                                bloque_actual = 1
                                dia_actual += 1

            return Response({"horarios": horarios}, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
