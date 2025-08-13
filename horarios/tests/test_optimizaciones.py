"""
Tests para las optimizaciones implementadas en el algoritmo genético.

Este módulo incluye tests de:
- Máscaras booleanas precomputadas
- Fitness optimizado con Numba
- Logging estructurado
- Validaciones consolidadas
"""

import pytest
import numpy as np
import time
import random
from django.test import TestCase
from django.db import transaction
from unittest.mock import patch, MagicMock

from horarios.models import (
    Profesor, Materia, Curso, Aula, Grado, MateriaGrado, 
    MateriaProfesor, DisponibilidadProfesor, BloqueHorario, Horario,
    ConfiguracionColegio
)
from horarios.mascaras import precomputar_mascaras, validar_slot_con_mascaras
from horarios.fitness_optimizado import (
    calcular_fitness_unificado, 
    ConfiguracionFitness,
    evaluar_calidad_solucion
)
from horarios.logging_estructurado import crear_logger_genetico
from horarios.genetico_funcion import validar_prerrequisitos_criticos

class TestMascarasOptimizadas(TestCase):
    """Tests para las máscaras booleanas precomputadas"""
    
    def setUp(self):
        """Configurar datos de prueba para máscaras"""
        self.crear_datos_prueba()
    
    def crear_datos_prueba(self):
        """Crea un conjunto mínimo de datos para pruebas de máscaras"""
        # Configuración del colegio
        self.config = ConfiguracionColegio.objects.create(
            jornada='mañana',
            bloques_por_dia=5,
            duracion_bloque=60,
            dias_clase='lunes,martes,miércoles,jueves,viernes'
        )
        
        # Crear grados
        self.grado1 = Grado.objects.create(nombre="Primero")
        self.grado2 = Grado.objects.create(nombre="Segundo")
        
        # Crear aulas
        self.aula1 = Aula.objects.create(nombre="Aula 101", tipo="comun", capacidad=30)
        self.aula2 = Aula.objects.create(nombre="Aula 102", tipo="comun", capacidad=30)
        
        # Crear bloques horarios (5 bloques por día)
        for i in range(1, 6):
            BloqueHorario.objects.create(
                numero=i,
                hora_inicio=f"{7+i:02d}:00",
                hora_fin=f"{8+i:02d}:00",
                tipo="clase"
            )
        
        # Crear materias
        self.materia1 = Materia.objects.create(
            nombre="Matemáticas",
            bloques_por_semana=10,
            jornada_preferida="mañana"
        )
        self.materia2 = Materia.objects.create(
            nombre="Lenguaje",
            bloques_por_semana=8,
            jornada_preferida="mañana"
        )
        
        # Crear profesores
        self.profesor1 = Profesor.objects.create(nombre="Ana García")
        self.profesor2 = Profesor.objects.create(nombre="Carlos López")
        
        # Crear cursos
        self.curso1 = Curso.objects.create(
            nombre="Primero A",
            grado=self.grado1,
            aula_fija=self.aula1
        )
        self.curso2 = Curso.objects.create(
            nombre="Segundo A",
            grado=self.grado2,
            aula_fija=self.aula2
        )
        
        # Crear relaciones
        MateriaGrado.objects.create(materia=self.materia1, grado=self.grado1)
        MateriaGrado.objects.create(materia=self.materia2, grado=self.grado1)
        MateriaGrado.objects.create(materia=self.materia1, grado=self.grado2)
        MateriaGrado.objects.create(materia=self.materia2, grado=self.grado2)
        
        MateriaProfesor.objects.create(materia=self.materia1, profesor=self.profesor1)
        MateriaProfesor.objects.create(materia=self.materia2, profesor=self.profesor2)
        
        # Crear disponibilidad de profesores
        dias = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes']
        for dia in dias:
            DisponibilidadProfesor.objects.create(
                profesor=self.profesor1,
                dia=dia,
                bloque_inicio=1,
                bloque_fin=5
            )
            DisponibilidadProfesor.objects.create(
                profesor=self.profesor2,
                dia=dia,
                bloque_inicio=1,
                bloque_fin=5
            )
    
    def test_precomputar_mascaras(self):
        """Test de precomputación de máscaras"""
        mascaras = precomputar_mascaras()
        
        # Verificar estructura básica
        self.assertIsNotNone(mascaras)
        self.assertEqual(len(mascaras.dias_clase), 5)
        self.assertEqual(mascaras.bloques_por_dia, 5)
        self.assertEqual(mascaras.total_slots, 25)
        
        # Verificar mapeos de IDs
        self.assertIn(self.profesor1.id, mascaras.profesor_to_idx)
        self.assertIn(self.materia1.id, mascaras.materia_to_idx)
        self.assertIn(self.curso1.id, mascaras.curso_to_idx)
        self.assertIn(self.aula1.id, mascaras.aula_to_idx)
        
        # Verificar máscaras de disponibilidad
        prof_idx = mascaras.profesor_to_idx[self.profesor1.id]
        self.assertTrue(np.any(mascaras.profesor_disponible[prof_idx]))
        
        # Verificar máscaras de compatibilidad
        prof_idx = mascaras.profesor_to_idx[self.profesor1.id]
        mat_idx = mascaras.materia_to_idx[self.materia1.id]
        self.assertTrue(mascaras.profesor_materia[prof_idx, mat_idx])
    
    def test_validar_slot_con_mascaras(self):
        """Test de validación de slots usando máscaras"""
        mascaras = precomputar_mascaras()
        
        # Slot válido
        es_valido, mensaje = validar_slot_con_mascaras(
            mascaras, self.curso1.id, self.materia1.id, 
            self.profesor1.id, 'lunes', 1
        )
        self.assertTrue(es_valido)
        self.assertEqual(mensaje, "Slot válido")
        
        # Slot inválido - profesor no disponible
        es_valido, mensaje = validar_slot_con_mascaras(
            mascaras, self.curso1.id, self.materia1.id, 
            self.profesor1.id, 'lunes', 6  # Bloque fuera de rango
        )
        self.assertFalse(es_valido)
        self.assertIn("fuera de rango", mensaje)
        
        # Slot inválido - incompatibilidad profesor-materia
        es_valido, mensaje = validar_slot_con_mascaras(
            mascaras, self.curso1.id, self.materia1.id, 
            self.profesor2.id, 'lunes', 1  # Profesor2 no puede enseñar materia1
        )
        self.assertFalse(es_valido)
        self.assertIn("no puede enseñar", mensaje)

class TestFitnessOptimizado(TestCase):
    """Tests para el fitness optimizado"""
    
    def setUp(self):
        """Configurar datos de prueba para fitness"""
        self.crear_datos_prueba()
        self.mascaras = precomputar_mascaras()
        self.config_fitness = ConfiguracionFitness()
    
    def crear_datos_prueba(self):
        """Crea datos mínimos para pruebas de fitness"""
        # Reutilizar la configuración del test anterior
        self.config = ConfiguracionColegio.objects.create(
            jornada='mañana',
            bloques_por_dia=5,
            duracion_bloque=60,
            dias_clase='lunes,martes,miércoles,jueves,viernes'
        )
        
        # Crear datos mínimos
        self.grado = Grado.objects.create(nombre="Primero")
        self.aula = Aula.objects.create(nombre="Aula 101", tipo="comun", capacidad=30)
        self.profesor = Profesor.objects.create(nombre="Ana García")
        self.materia = Materia.objects.create(
            nombre="Matemáticas",
            bloques_por_semana=5,
            jornada_preferida="mañana"
        )
        self.curso = Curso.objects.create(
            nombre="Primero A",
            grado=self.grado,
            aula_fija=self.aula
        )
        
        # Crear relaciones
        MateriaGrado.objects.create(materia=self.materia, grado=self.grado)
        MateriaProfesor.objects.create(materia=self.materia, profesor=self.profesor)
        
        # Crear disponibilidad
        for dia in ['lunes', 'martes', 'miércoles', 'jueves', 'viernes']:
            DisponibilidadProfesor.objects.create(
                profesor=self.profesor,
                dia=dia,
                bloque_inicio=1,
                bloque_fin=5
            )
        
        # Crear bloques
        for i in range(1, 6):
            BloqueHorario.objects.create(
                numero=i,
                hora_inicio=f"{7+i:02d}:00",
                hora_fin=f"{8+i:02d}:00",
                tipo="clase"
            )
    
    def test_calcular_fitness_unificado_solucion_valida(self):
        """Test de fitness para una solución válida"""
        # Crear cromosoma válido (5 bloques distribuidos)
        cromosoma = {
            (self.curso.id, 'lunes', 1): (self.materia.id, self.profesor.id),
            (self.curso.id, 'martes', 1): (self.materia.id, self.profesor.id),
            (self.curso.id, 'miércoles', 1): (self.materia.id, self.profesor.id),
            (self.curso.id, 'jueves', 1): (self.materia.id, self.profesor.id),
            (self.curso.id, 'viernes', 1): (self.materia.id, self.profesor.id),
        }
        
        resultado = calcular_fitness_unificado(cromosoma, self.mascaras, self.config_fitness)
        
        # Verificar que es válida
        self.assertTrue(resultado.es_valida)
        self.assertEqual(resultado.num_solapes, 0)
        self.assertEqual(resultado.num_huecos, 0)
        self.assertEqual(resultado.porcentaje_primeras_ultimas, 1.0)  # Todos en bloque 1
    
    def test_calcular_fitness_unificado_con_solapes(self):
        """Test de fitness para una solución con solapes"""
        # Crear cromosoma con solape de profesor
        cromosoma = {
            (self.curso.id, 'lunes', 1): (self.materia.id, self.profesor.id),
            (self.curso.id, 'lunes', 2): (self.materia.id, self.profesor.id),  # Solape!
        }
        
        resultado = calcular_fitness_unificado(cromosoma, self.mascaras, self.config_fitness)
        
        # Verificar que no es válida
        self.assertFalse(resultado.es_valida)
        self.assertGreater(resultado.num_solapes, 0)
        self.assertEqual(resultado.penalizacion_solapes, float('inf'))
    
    def test_evaluar_calidad_solucion(self):
        """Test de evaluación de calidad de solución"""
        # Crear resultado de fitness
        resultado = ResultadoFitness(
            fitness_total=-50.0,
            penalizacion_solapes=0.0,
            penalizacion_huecos=2.0,
            penalizacion_primeras_ultimas=1.0,
            penalizacion_balance_dia=0.5,
            penalizacion_bloques_semana=0.0,
            num_solapes=0,
            num_huecos=2,
            porcentaje_primeras_ultimas=0.2,
            desviacion_balance_dia=0.5,
            es_valida=True,
            mensaje_estado="Solución válida"
        )
        
        calidad = evaluar_calidad_solucion(resultado)
        
        # Verificar evaluación
        self.assertEqual(calidad['solapes'], "Óptimo")
        self.assertEqual(calidad['huecos'], "Bueno")
        self.assertEqual(calidad['primeras_ultimas'], "Aceptable")
        self.assertEqual(calidad['balance_dia'], "Óptimo")

class TestLoggingEstructurado(TestCase):
    """Tests para el logging estructurado"""
    
    def setUp(self):
        """Configurar logger de prueba"""
        self.logger = crear_logger_genetico("logs/test_logging.txt")
    
    def test_iniciar_ejecucion(self):
        """Test de inicio de ejecución"""
        config = {
            'poblacion_size': 100,
            'generaciones': 500,
            'semilla': 42
        }
        
        self.logger.iniciar_ejecucion(config, 42)
        
        # Verificar que se inició correctamente
        self.assertIsNotNone(self.logger.metricas_ejecucion)
        self.assertEqual(self.logger.metricas_ejecucion.semilla, 42)
        self.assertEqual(self.logger.metricas_ejecucion.poblacion_size, 100)
    
    def test_registrar_generacion(self):
        """Test de registro de generación"""
        config = {'poblacion_size': 50, 'generaciones': 100}
        self.logger.iniciar_ejecucion(config, 42)
        
        # Registrar generación
        fitness_poblacion = [-10.0, -15.0, -20.0, -25.0, -30.0]
        self.logger.registrar_generacion(1, fitness_poblacion, 2.5, 0, 0)
        
        # Verificar registro
        self.assertEqual(len(self.logger.metricas_ejecucion.metricas_por_generacion), 1)
        self.assertEqual(self.logger.metricas_ejecucion.generaciones_completadas, 1)
        self.assertEqual(self.logger.metricas_ejecucion.fitness_final, -10.0)
    
    def test_registrar_resultado_final(self):
        """Test de registro de resultado final"""
        config = {'poblacion_size': 50, 'generaciones': 100}
        self.logger.iniciar_ejecucion(config, 42)
        
        resultado = {
            'exito': True,
            'metricas': {
                'num_solapes': 0,
                'num_huecos': 2,
                'porcentaje_primeras_ultimas': 0.1,
                'desviacion_balance_dia': 0.5
            }
        }
        
        self.logger.registrar_resultado_final(resultado, True, True)
        
        # Verificar resultado final
        self.assertTrue(self.logger.metricas_ejecucion.exito)
        self.assertTrue(self.logger.metricas_ejecucion.convergencia)
        self.assertEqual(self.logger.metricas_ejecucion.num_solapes, 0)
        self.assertEqual(self.logger.metricas_ejecucion.num_huecos, 2)

class TestValidacionesConsolidadas(TestCase):
    """Tests para las validaciones consolidadas"""
    
    def setUp(self):
        """Configurar datos de prueba para validaciones"""
        self.crear_datos_prueba()
    
    def crear_datos_prueba(self):
        """Crea datos mínimos para pruebas de validación"""
        # Configuración básica
        self.config = ConfiguracionColegio.objects.create(
            jornada='mañana',
            bloques_por_dia=5,
            duracion_bloque=60,
            dias_clase='lunes,martes,miércoles,jueves,viernes'
        )
        
        # Crear datos mínimos
        self.grado = Grado.objects.create(nombre="Primero")
        self.aula = Aula.objects.create(nombre="Aula 101", tipo="comun", capacidad=30)
        self.profesor = Profesor.objects.create(nombre="Ana García")
        self.materia = Materia.objects.create(
            nombre="Matemáticas",
            bloques_por_semana=5,
            jornada_preferida="mañana"
        )
        self.curso = Curso.objects.create(
            nombre="Primero A",
            grado=self.grado,
            aula_fija=self.aula
        )
        
        # Crear relaciones
        MateriaGrado.objects.create(materia=self.materia, grado=self.grado)
        MateriaProfesor.objects.create(materia=self.materia, profesor=self.profesor)
        
        # Crear disponibilidad
        for dia in ['lunes', 'martes', 'miércoles', 'jueves', 'viernes']:
            DisponibilidadProfesor.objects.create(
                profesor=self.profesor,
                dia=dia,
                bloque_inicio=1,
                bloque_fin=5
            )
        
        # Crear bloques
        for i in range(1, 6):
            BloqueHorario.objects.create(
                numero=i,
                hora_inicio=f"{7+i:02d}:00",
                hora_fin=f"{8+i:02d}:00",
                tipo="clase"
            )
    
    def test_validar_prerrequisitos_criticos_sin_errores(self):
        """Test de validación sin errores"""
        errores = validar_prerrequisitos_criticos()
        
        # Debe pasar sin errores
        self.assertEqual(len(errores), 0)
    
    def test_validar_prerrequisitos_criticos_con_errores(self):
        """Test de validación con errores"""
        # Crear profesor sin disponibilidad
        profesor_sin_disponibilidad = Profesor.objects.create(nombre="Juan Pérez")
        
        errores = validar_prerrequisitos_criticos()
        
        # Debe detectar el error
        self.assertGreater(len(errores), 0)
        self.assertTrue(any("sin disponibilidad" in error for error in errores))
        
        # Limpiar
        profesor_sin_disponibilidad.delete()
    
    def test_validar_prerrequisitos_criticos_materia_sin_profesor(self):
        """Test de validación con materia sin profesor"""
        # Crear materia sin profesor
        materia_sin_profesor = Materia.objects.create(
            nombre="Física",
            bloques_por_semana=5,
            jornada_preferida="mañana"
        )
        MateriaGrado.objects.create(materia=materia_sin_profesor, grado=self.grado)
        
        errores = validar_prerrequisitos_criticos()
        
        # Debe detectar el error
        self.assertGreater(len(errores), 0)
        self.assertTrue(any("sin profesor" in error for error in errores))
        
        # Limpiar
        materia_sin_profesor.delete()

class TestReproducibilidad(TestCase):
    """Tests para reproducibilidad del algoritmo"""
    
    def setUp(self):
        """Configurar datos de prueba para reproducibilidad"""
        self.crear_datos_prueba()
    
    def crear_datos_prueba(self):
        """Crea datos mínimos para pruebas de reproducibilidad"""
        # Configuración básica
        self.config = ConfiguracionColegio.objects.create(
            jornada='mañana',
            bloques_por_dia=5,
            duracion_bloque=60,
            dias_clase='lunes,martes,miércoles,jueves,viernes'
        )
        
        # Crear datos mínimos
        self.grado = Grado.objects.create(nombre="Primero")
        self.aula = Aula.objects.create(nombre="Aula 101", tipo="comun", capacidad=30)
        self.profesor = Profesor.objects.create(nombre="Ana García")
        self.materia = Materia.objects.create(
            nombre="Matemáticas",
            bloques_por_semana=5,
            jornada_preferida="mañana"
        )
        self.curso = Curso.objects.create(
            nombre="Primero A",
            grado=self.grado,
            aula_fija=self.aula
        )
        
        # Crear relaciones
        MateriaGrado.objects.create(materia=self.materia, grado=self.grado)
        MateriaProfesor.objects.create(materia=self.materia, profesor=self.profesor)
        
        # Crear disponibilidad
        for dia in ['lunes', 'martes', 'miércoles', 'jueves', 'viernes']:
            DisponibilidadProfesor.objects.create(
                profesor=self.profesor,
                dia=dia,
                bloque_inicio=1,
                bloque_fin=5
            )
        
        # Crear bloques
        for i in range(1, 6):
            BloqueHorario.objects.create(
                numero=i,
                hora_inicio=f"{7+i:02d}:00",
                hora_fin=f"{8+i:02d}:00",
                tipo="clase"
            )
    
    def test_reproducibilidad_semilla(self):
        """Test de reproducibilidad por semilla"""
        # Configurar semillas
        semilla1 = 42
        semilla2 = 42
        semilla3 = 123
        
        # Configurar random seeds
        random.seed(semilla1)
        np.random.seed(semilla1)
        
        # Generar números aleatorios
        numeros1 = [random.randint(1, 100) for _ in range(10)]
        numeros_np1 = [np.random.randint(1, 100) for _ in range(10)]
        
        # Resetear y usar misma semilla
        random.seed(semilla2)
        np.random.seed(semilla2)
        
        numeros2 = [random.randint(1, 100) for _ in range(10)]
        numeros_np2 = [np.random.randint(1, 100) for _ in range(10)]
        
        # Resetear y usar semilla diferente
        random.seed(semilla3)
        np.random.seed(semilla3)
        
        numeros3 = [random.randint(1, 100) for _ in range(10)]
        numeros_np3 = [np.random.randint(1, 100) for _ in range(10)]
        
        # Verificar reproducibilidad
        self.assertEqual(numeros1, numeros2)
        self.assertEqual(numeros_np1, numeros_np2)
        
        # Verificar que semillas diferentes producen resultados diferentes
        self.assertNotEqual(numeros1, numeros3)
        self.assertNotEqual(numeros_np1, numeros_np3) 