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


# Serializadores de entrada para el Motor de Cálculo (Generador)
class SerializadorDisponibilidadEntrada(serializers.Serializer):
    """
    Define un rango de bloques libres para un profesor.
    Ej: Lunes, bloques 1 al 6.
    """
    dia = serializers.CharField()
    bloque_inicio = serializers.IntegerField()
    bloque_fin = serializers.IntegerField()

class SerializadorProfesorEntrada(serializers.Serializer):
    """
    Datos de entrada para crear un profesor en el Generador.
    Incluye su disponibilidad y qué materias puede dictar.
    """
    id_externo = serializers.CharField(required=False)
    nombre = serializers.CharField()
    disponibilidad = SerializadorDisponibilidadEntrada(many=True, required=False)
    materias_capaces = serializers.ListField(child=serializers.CharField(), required=False)

class SerializadorMateriaEntrada(serializers.Serializer):
    """
    Definición de materia para el generador.
    """
    id_externo = serializers.CharField(required=False)
    nombre = serializers.CharField()
    aula_especial = serializers.BooleanField(default=False)

class SerializadorCursoEntrada(serializers.Serializer):
    """
    Definición de curso y su carga académica requerida.
    plan_estudios: Diccionario { "Matemáticas": 5, "Lengua": 4 }
    """
    id_externo = serializers.CharField(required=False)
    nombre = serializers.CharField()
    grado = serializers.CharField()
    plan_estudios = serializers.DictField(child=serializers.IntegerField())

class SerializadorEntradaGenerador(serializers.Serializer):
    """
    Payload completo para el endpoint /solver/.
    Permite generar horarios desde cero sin usar la base de datos persistente (modo stateless).
    """
    configuracion = serializers.DictField()
    profesores = SerializadorProfesorEntrada(many=True)
    materias = SerializadorMateriaEntrada(many=True)
    cursos = SerializadorCursoEntrada(many=True)
