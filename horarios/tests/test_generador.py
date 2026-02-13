from django.test import TestCase
from horarios.application.services.generador_demand_first import GeneradorDemandFirst
from horarios.models import (
    Profesor, Materia, Curso, Grado, Aula, BloqueHorario,
    MateriaGrado, MateriaProfesor, DisponibilidadProfesor,
    ConfiguracionColegio, CursoMateriaRequerida, ConfiguracionCurso
)
from datetime import time

class GeneradorDemandFirstTest(TestCase):
    def setUp(self):
        # Configuración del colegio
        ConfiguracionColegio.objects.create(
            dias_clase='lunes,martes,miércoles,jueves,viernes',
            bloques_por_dia=6,
            jornada='mañana',
            duracion_bloque=60
        )

        # Bloques
        for i in range(1, 7):
            BloqueHorario.objects.create(
                numero=i,
                hora_inicio=time(7+i, 0),
                hora_fin=time(7+i, 45),
                tipo='clase'
            )

        # Datos maestros
        self.grado = Grado.objects.create(nombre='PRIMERO')
        self.aula = Aula.objects.create(nombre='A1', capacidad=30)
        self.curso = Curso.objects.create(nombre='1A', grado=self.grado, aula_fija=self.aula)

        self.profesor = Profesor.objects.create(nombre='Profesor Test')
        self.materia = Materia.objects.create(nombre='Materia Test', bloques_por_semana=2)

        # Asignaciones
        MateriaGrado.objects.create(grado=self.grado, materia=self.materia)
        MateriaProfesor.objects.create(profesor=self.profesor, materia=self.materia)

        # Disponibilidad: solo lunes bloques 1 y 2
        DisponibilidadProfesor.objects.create(
            profesor=self.profesor, dia='lunes', bloque_inicio=1, bloque_fin=2
        )

        # Requerimiento específico
        CursoMateriaRequerida.objects.create(
            curso=self.curso,
            materia=self.materia,
            bloques_requeridos=2
        )

        # Configuración del curso para completitud
        ConfiguracionCurso.objects.create(
            curso=self.curso,
            slots_objetivo=2
        )

    def test_generacion_basica(self):
        generador = GeneradorDemandFirst()
        # Mocking _obtener_slots_objetivo to require exactly 2 slots (the ones we provided)
        # to make it easy to succeed without needing many fillers.
        from unittest.mock import patch
        with patch.object(GeneradorDemandFirst, '_obtener_slots_objetivo', return_value=2):
            resultado = generador.generar_horarios(semilla=42)

        self.assertTrue(resultado['exito'], f"Generación falló: {resultado.get('razon')}")
        self.assertEqual(len(resultado['horarios']), 2)

        for h in resultado['horarios']:
            self.assertEqual(h['curso_id'], self.curso.id)
            self.assertEqual(h['materia_id'], self.materia.id)
            self.assertEqual(h['profesor_id'], self.profesor.id)
            self.assertEqual(h['dia'], 'lunes')
            self.assertIn(h['bloque'], [1, 2])
