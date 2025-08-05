from django.shortcuts import render
from rest_framework.permissions import IsAuthenticated

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, generics
from datetime import datetime

from horarios.models import Profesor, Materia, Curso, Horario, Aula
from horarios.genetico import generar_horarios_genetico
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
            generar_horarios_genetico()  # ✅ esta es la función que importa
            return Response({"message": "Horario generado exitosamente"}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

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

