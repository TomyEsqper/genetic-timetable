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


# Serializadores de entrada para el Motor de Cálculo (Solver)
class InputDisponibilidadSerializer(serializers.Serializer):
    dia = serializers.CharField()
    bloque_inicio = serializers.IntegerField()
    bloque_fin = serializers.IntegerField()

class InputProfesorSerializer(serializers.Serializer):
    id_externo = serializers.CharField(required=False)
    nombre = serializers.CharField()
    disponibilidad = InputDisponibilidadSerializer(many=True, required=False)
    materias_capaces = serializers.ListField(child=serializers.CharField(), required=False)

class InputMateriaSerializer(serializers.Serializer):
    id_externo = serializers.CharField(required=False)
    nombre = serializers.CharField()
    aula_especial = serializers.BooleanField(default=False)

class InputCursoSerializer(serializers.Serializer):
    id_externo = serializers.CharField(required=False)
    nombre = serializers.CharField()
    grado = serializers.CharField()
    plan_estudios = serializers.DictField(child=serializers.IntegerField())

class SolverInputSerializer(serializers.Serializer):
    configuracion = serializers.DictField()
    profesores = InputProfesorSerializer(many=True)
    materias = InputMateriaSerializer(many=True)
    cursos = InputCursoSerializer(many=True)
