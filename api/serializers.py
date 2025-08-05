from rest_framework import serializers
from horarios.models import Profesor, Materia, Curso, Horario, Aula


class ProfesorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profesor
        fields = ['id', 'nombre']


class MateriaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Materia
        fields = ['id', 'nombre', 'bloques_por_semana', 'jornada_preferida', 'requiere_bloques_consecutivos',
                  'requiere_aula_especial']


class CursoSerializer(serializers.ModelSerializer):
    grado = serializers.StringRelatedField()

    class Meta:
        model = Curso
        fields = ['id', 'nombre', 'grado']


class AulaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Aula
        fields = ['id', 'nombre', 'tipo', 'capacidad']


class HorarioSerializer(serializers.ModelSerializer):
    curso = CursoSerializer()
    profesor = ProfesorSerializer()
    materia = MateriaSerializer()
    aula = AulaSerializer()

    class Meta:
        model = Horario
        fields = ['id', 'curso', 'materia', 'profesor', 'aula', 'dia', 'bloque']
