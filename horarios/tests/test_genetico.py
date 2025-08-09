import pytest
import random
import numpy as np
from unittest import mock
from hypothesis import given, strategies as st
from django.test import TestCase, TransactionTestCase
from django.db import transaction

from horarios.models import (
    Curso, Grado, Materia, MateriaGrado, Profesor, MateriaProfesor,
    DisponibilidadProfesor, Aula, Horario, BloqueHorario
)
from horarios.genetico import (
    generar_horarios_genetico, cargar_datos, inicializar_poblacion,
    evaluar_fitness, Cromosoma, DatosHorario
)


class TestGeneticoBase(TransactionTestCase):
    """Clase base para pruebas del algoritmo genético."""
    
    def setUp(self):
        """Configuración inicial para las pruebas."""
        # Crear bloques horarios (solo tipo 'clase')
        for i in range(1, 6):  # 5 bloques por día
            BloqueHorario.objects.create(numero=i, tipo='clase')
        
        # Crear un bloque de otro tipo para probar que no se use
        BloqueHorario.objects.create(numero=6, tipo='recreo')
        
        # Crear aulas
        self.aula_comun = Aula.objects.create(nombre="Aula 1", tipo="comun", capacidad=30)
        self.aula_especial = Aula.objects.create(nombre="Laboratorio", tipo="laboratorio", capacidad=25)
        
        # Crear grados
        self.grado1 = Grado.objects.create(nombre="Primero")
        self.grado2 = Grado.objects.create(nombre="Segundo")
        
        # Crear cursos
        self.curso1 = Curso.objects.create(nombre="1A", grado=self.grado1)
        self.curso2 = Curso.objects.create(nombre="2A", grado=self.grado2)
        
        # Crear materias
        self.matematicas = Materia.objects.create(
            nombre="Matemáticas", bloques_por_semana=3, requiere_aula_especial=False
        )
        self.fisica = Materia.objects.create(
            nombre="Física", bloques_por_semana=2, requiere_aula_especial=True
        )
        self.historia = Materia.objects.create(
            nombre="Historia", bloques_por_semana=2, requiere_aula_especial=False
        )
        
        # Asignar materias a grados
        MateriaGrado.objects.create(materia=self.matematicas, grado=self.grado1)
        MateriaGrado.objects.create(materia=self.fisica, grado=self.grado1)
        MateriaGrado.objects.create(materia=self.matematicas, grado=self.grado2)
        MateriaGrado.objects.create(materia=self.historia, grado=self.grado2)
        
        # Crear profesores
        self.profesor1 = Profesor.objects.create(nombre="Profesor 1")
        self.profesor2 = Profesor.objects.create(nombre="Profesor 2")
        
        # Asignar materias a profesores
        MateriaProfesor.objects.create(materia=self.matematicas, profesor=self.profesor1)
        MateriaProfesor.objects.create(materia=self.fisica, profesor=self.profesor1)
        MateriaProfesor.objects.create(materia=self.matematicas, profesor=self.profesor2)
        MateriaProfesor.objects.create(materia=self.historia, profesor=self.profesor2)
        
        # Crear disponibilidad para profesores (todos los días, todos los bloques)
        dias = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes']
        for profesor in [self.profesor1, self.profesor2]:
            for dia in dias:
                DisponibilidadProfesor.objects.create(
                    profesor=profesor, dia=dia, bloque_inicio=1, bloque_fin=5
                )


class TestCargaDatos(TestGeneticoBase):
    """Pruebas para la función de carga de datos."""
    
    def test_carga_datos_correcta(self):
        """Verifica que la carga de datos sea correcta."""
        datos = cargar_datos()
        
        # Verificar bloques disponibles (solo tipo 'clase')
        self.assertEqual(len(datos.bloques_disponibles), 5)
        self.assertNotIn(6, datos.bloques_disponibles)  # No debe incluir el bloque tipo 'recreo'
        
        # Verificar profesores y disponibilidad
        self.assertEqual(len(datos.profesores), 2)
        for profesor_id, profesor_data in datos.profesores.items():
            self.assertEqual(len(profesor_data.disponibilidad), 25)  # 5 días x 5 bloques
        
        # Verificar materias
        self.assertEqual(len(datos.materias), 3)
        self.assertEqual(datos.materias[self.matematicas.id].bloques_por_semana, 3)
        self.assertEqual(datos.materias[self.fisica.id].bloques_por_semana, 2)
        
        # Verificar cursos
        self.assertEqual(len(datos.cursos), 2)
        
        # Verificar relaciones materia-profesor
        self.assertTrue((self.matematicas.id, self.profesor1.id) in datos.materia_profesor)
        self.assertTrue((self.fisica.id, self.profesor1.id) in datos.materia_profesor)
        self.assertTrue((self.matematicas.id, self.profesor2.id) in datos.materia_profesor)
        self.assertTrue((self.historia.id, self.profesor2.id) in datos.materia_profesor)


class TestInicializacionPoblacion(TestGeneticoBase):
    """Pruebas para la inicialización de la población."""
    
    def test_inicializacion_poblacion(self):
        """Verifica que la inicialización de la población sea correcta."""
        datos = cargar_datos()
        poblacion = inicializar_poblacion(datos, tamano_poblacion=10, semilla=42)
        
        # Verificar tamaño de la población
        self.assertEqual(len(poblacion), 10)
        
        # Verificar que cada cromosoma tenga genes
        for cromosoma in poblacion:
            self.assertGreater(len(cromosoma.genes), 0)
            
            # Verificar que los genes sean válidos
            for (curso_id, dia, bloque), (materia_id, profesor_id) in cromosoma.genes.items():
                # Verificar que el curso exista
                self.assertIn(curso_id, datos.cursos)
                
                # Verificar que la materia exista
                self.assertIn(materia_id, datos.materias)
                
                # Verificar que el profesor exista
                self.assertIn(profesor_id, datos.profesores)
                
                # Verificar que el profesor pueda impartir la materia
                self.assertIn((materia_id, profesor_id), datos.materia_profesor)
                
                # Verificar que el bloque sea válido
                self.assertIn(bloque, datos.bloques_disponibles)
                
                # Verificar que el día sea válido
                self.assertIn(dia, ['lunes', 'martes', 'miércoles', 'jueves', 'viernes'])
    
    def test_reproducibilidad_con_semilla(self):
        """Verifica que la inicialización sea reproducible con la misma semilla."""
        datos = cargar_datos()
        poblacion1 = inicializar_poblacion(datos, tamano_poblacion=5, semilla=42)
        poblacion2 = inicializar_poblacion(datos, tamano_poblacion=5, semilla=42)
        
        # Verificar que los cromosomas sean iguales
        for i in range(5):
            self.assertEqual(len(poblacion1[i].genes), len(poblacion2[i].genes))
            for key in poblacion1[i].genes:
                self.assertIn(key, poblacion2[i].genes)
                self.assertEqual(poblacion1[i].genes[key], poblacion2[i].genes[key])


class TestEvaluacionFitness(TestGeneticoBase):
    """Pruebas para la función de evaluación de fitness."""
    
    def test_evaluacion_sin_conflictos(self):
        """Verifica que un horario sin conflictos tenga un buen fitness."""
        datos = cargar_datos()
        cromosoma = Cromosoma()
        
        # Crear un horario sin conflictos
        # Curso 1: Matemáticas (3 bloques) con Profesor 1
        cromosoma.genes[(self.curso1.id, 'lunes', 1)] = (self.matematicas.id, self.profesor1.id)
        cromosoma.genes[(self.curso1.id, 'martes', 1)] = (self.matematicas.id, self.profesor1.id)
        cromosoma.genes[(self.curso1.id, 'miércoles', 1)] = (self.matematicas.id, self.profesor1.id)
        
        # Curso 1: Física (2 bloques) con Profesor 1
        cromosoma.genes[(self.curso1.id, 'jueves', 1)] = (self.fisica.id, self.profesor1.id)
        cromosoma.genes[(self.curso1.id, 'viernes', 1)] = (self.fisica.id, self.profesor1.id)
        
        # Curso 2: Matemáticas (3 bloques) con Profesor 2
        cromosoma.genes[(self.curso2.id, 'lunes', 2)] = (self.matematicas.id, self.profesor2.id)
        cromosoma.genes[(self.curso2.id, 'martes', 2)] = (self.matematicas.id, self.profesor2.id)
        cromosoma.genes[(self.curso2.id, 'miércoles', 2)] = (self.matematicas.id, self.profesor2.id)
        
        # Curso 2: Historia (2 bloques) con Profesor 2
        cromosoma.genes[(self.curso2.id, 'jueves', 2)] = (self.historia.id, self.profesor2.id)
        cromosoma.genes[(self.curso2.id, 'viernes', 2)] = (self.historia.id, self.profesor2.id)
        
        fitness, conflictos = evaluar_fitness(cromosoma, datos)
        
        # Verificar que no haya conflictos
        self.assertEqual(conflictos, 0)
        
        # Verificar que el fitness sea positivo
        self.assertGreater(fitness, 0)
    
    def test_evaluacion_con_solape_curso(self):
        """Verifica que un horario con solape de curso tenga conflictos."""
        datos = cargar_datos()
        cromosoma = Cromosoma()
        
        # Crear un horario con solape de curso (mismo curso, mismo día, mismo bloque)
        cromosoma.genes[(self.curso1.id, 'lunes', 1)] = (self.matematicas.id, self.profesor1.id)
        cromosoma.genes[(self.curso1.id, 'lunes', 1)] = (self.fisica.id, self.profesor1.id)  # Solape
        
        fitness, conflictos = evaluar_fitness(cromosoma, datos)
        
        # Verificar que haya conflictos
        self.assertGreater(conflictos, 0)
    
    def test_evaluacion_con_solape_profesor(self):
        """Verifica que un horario con solape de profesor tenga conflictos."""
        datos = cargar_datos()
        cromosoma = Cromosoma()
        
        # Crear un horario con solape de profesor (mismo profesor, mismo día, mismo bloque)
        cromosoma.genes[(self.curso1.id, 'lunes', 1)] = (self.matematicas.id, self.profesor1.id)
        cromosoma.genes[(self.curso2.id, 'lunes', 1)] = (self.matematicas.id, self.profesor1.id)  # Solape
        
        fitness, conflictos = evaluar_fitness(cromosoma, datos)
        
        # Verificar que haya conflictos
        self.assertGreater(conflictos, 0)
    
    def test_evaluacion_bloques_por_semana(self):
        """Verifica que se respete el número de bloques por semana."""
        datos = cargar_datos()
        cromosoma = Cromosoma()
        
        # Crear un horario con número incorrecto de bloques por semana
        # Matemáticas debería tener 3 bloques, pero solo asignamos 2
        cromosoma.genes[(self.curso1.id, 'lunes', 1)] = (self.matematicas.id, self.profesor1.id)
        cromosoma.genes[(self.curso1.id, 'martes', 1)] = (self.matematicas.id, self.profesor1.id)
        
        fitness, conflictos = evaluar_fitness(cromosoma, datos)
        
        # Verificar que haya conflictos
        self.assertGreater(conflictos, 0)


class TestGeneracionHorarios(TestGeneticoBase):
    """Pruebas para la generación completa de horarios."""
    
    @mock.patch('horarios.genetico.logger')  # Mockear el logger para evitar salida en consola
    def test_generacion_horarios_sin_conflictos(self, mock_logger):
        """Verifica que la generación de horarios no produzca conflictos."""
        # Generar horarios con parámetros reducidos para la prueba
        generar_horarios_genetico(
            poblacion_size=20,
            generaciones=50,
            prob_cruce=0.85,
            prob_mutacion=0.25,
            elite=2,
            paciencia=10,
            semilla=42,
            workers=1  # Usar un solo worker para las pruebas
        )
        
        # Verificar que se hayan generado horarios
        horarios = Horario.objects.all()
        self.assertGreater(horarios.count(), 0)
        
        # Verificar que no haya solapes de curso
        curso_slots = {}
        for horario in horarios:
            key = (horario.curso_id, horario.dia, horario.bloque)
            self.assertNotIn(key, curso_slots, f"Solape de curso en {key}")
            curso_slots[key] = True
        
        # Verificar que no haya solapes de profesor
        profesor_slots = {}
        for horario in horarios:
            key = (horario.profesor_id, horario.dia, horario.bloque)
            self.assertNotIn(key, profesor_slots, f"Solape de profesor en {key}")
            profesor_slots[key] = True
        
        # Verificar que solo se usen bloques tipo 'clase'
        bloques_clase = set(BloqueHorario.objects.filter(tipo='clase').values_list('numero', flat=True))
        for horario in horarios:
            self.assertIn(horario.bloque, bloques_clase, f"Bloque no válido: {horario.bloque}")
        
        # Verificar que se respete el número de bloques por semana para cada materia y curso
        bloques_materia_curso = {}
        for horario in horarios:
            key = (horario.curso_id, horario.materia_id)
            bloques_materia_curso[key] = bloques_materia_curso.get(key, 0) + 1
        
        for (curso_id, materia_id), count in bloques_materia_curso.items():
            materia = Materia.objects.get(id=materia_id)
            self.assertEqual(count, materia.bloques_por_semana, 
                             f"Bloques incorrectos para curso {curso_id}, materia {materia_id}")
    
    @mock.patch('horarios.genetico.logger')  # Mockear el logger para evitar salida en consola
    def test_determinismo_con_semilla(self, mock_logger):
        """Verifica que la generación sea determinista con la misma semilla."""
        # Limpiar horarios existentes
        Horario.objects.all().delete()
        
        # Primera generación
        generar_horarios_genetico(poblacion_size=20, generaciones=20, semilla=42, workers=1)
        horarios1 = list(Horario.objects.all().order_by('curso_id', 'dia', 'bloque').values())
        
        # Limpiar horarios
        Horario.objects.all().delete()
        
        # Segunda generación con la misma semilla
        generar_horarios_genetico(poblacion_size=20, generaciones=20, semilla=42, workers=1)
        horarios2 = list(Horario.objects.all().order_by('curso_id', 'dia', 'bloque').values())
        
        # Verificar que los horarios sean iguales
        self.assertEqual(len(horarios1), len(horarios2))
        for i in range(len(horarios1)):
            self.assertEqual(horarios1[i]['curso_id'], horarios2[i]['curso_id'])
            self.assertEqual(horarios1[i]['materia_id'], horarios2[i]['materia_id'])
            self.assertEqual(horarios1[i]['profesor_id'], horarios2[i]['profesor_id'])
            self.assertEqual(horarios1[i]['dia'], horarios2[i]['dia'])
            self.assertEqual(horarios1[i]['bloque'], horarios2[i]['bloque'])


class TestStressHorarios(TransactionTestCase):
    """Pruebas de estrés para la generación de horarios."""
    
    def setUp(self):
        """Configuración para pruebas de estrés con muchos cursos y bloques."""
        # Crear bloques horarios (10 bloques por día)
        for i in range(1, 11):
            BloqueHorario.objects.create(numero=i, tipo='clase')
        
        # Crear aulas (30 aulas comunes, 5 especiales)
        for i in range(1, 31):
            Aula.objects.create(nombre=f"Aula {i}", tipo="comun", capacidad=30)
        
        for i in range(1, 6):
            Aula.objects.create(nombre=f"Laboratorio {i}", tipo="laboratorio", capacidad=25)
        
        # Crear grados (10 grados)
        grados = []
        for i in range(1, 11):
            grado = Grado.objects.create(nombre=f"Grado {i}")
            grados.append(grado)
        
        # Crear cursos (3 cursos por grado = 30 cursos)
        cursos = []
        for grado in grados:
            for letra in ['A', 'B', 'C']:
                curso = Curso.objects.create(nombre=f"{grado.nombre} {letra}", grado=grado)
                cursos.append(curso)
        
        # Crear materias (10 materias)
        materias = []
        for i in range(1, 11):
            requiere_especial = i % 5 == 0  # Cada quinta materia requiere aula especial
            materia = Materia.objects.create(
                nombre=f"Materia {i}", 
                bloques_por_semana=random.randint(2, 4),
                requiere_aula_especial=requiere_especial
            )
            materias.append(materia)
        
        # Asignar materias a grados (cada grado tiene 6 materias)
        for grado in grados:
            for materia in random.sample(materias, 6):
                MateriaGrado.objects.create(materia=materia, grado=grado)
        
        # Crear profesores (20 profesores)
        profesores = []
        for i in range(1, 21):
            profesor = Profesor.objects.create(nombre=f"Profesor {i}")
            profesores.append(profesor)
        
        # Asignar materias a profesores (cada profesor puede impartir 2-3 materias)
        for profesor in profesores:
            for materia in random.sample(materias, random.randint(2, 3)):
                MateriaProfesor.objects.create(materia=materia, profesor=profesor)
        
        # Crear disponibilidad para profesores (disponibilidad parcial)
        dias = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes']
        for profesor in profesores:
            for dia in dias:
                # Cada profesor tiene disponibilidad en bloques aleatorios
                bloque_inicio = random.randint(1, 5)
                bloque_fin = random.randint(bloque_inicio, 10)
                DisponibilidadProfesor.objects.create(
                    profesor=profesor, dia=dia, bloque_inicio=bloque_inicio, bloque_fin=bloque_fin
                )
    
    @mock.patch('horarios.genetico.logger')  # Mockear el logger para evitar salida en consola
    def test_stress_generacion_horarios(self, mock_logger):
        """Prueba de estrés para la generación de horarios con muchos cursos y bloques."""
        import time
        
        # Medir tiempo de ejecución
        inicio = time.time()
        
        # Generar horarios
        generar_horarios_genetico(
            poblacion_size=80,
            generaciones=200,  # Reducido para la prueba
            prob_cruce=0.85,
            prob_mutacion=0.25,
            elite=4,
            paciencia=25,
            semilla=42,
            workers=None  # Usar todos los workers disponibles
        )
        
        tiempo_total = time.time() - inicio
        
        # Verificar que el tiempo sea menor a 5 minutos (300 segundos)
        self.assertLess(tiempo_total, 300, f"La generación tomó {tiempo_total:.2f} segundos, excediendo el límite de 5 minutos")
        
        # Verificar que se hayan generado horarios
        horarios = Horario.objects.all()
        self.assertGreater(horarios.count(), 0)
        
        # Verificar que no haya solapes de curso
        curso_slots = {}
        for horario in horarios:
            key = (horario.curso_id, horario.dia, horario.bloque)
            self.assertNotIn(key, curso_slots, f"Solape de curso en {key}")
            curso_slots[key] = True
        
        # Verificar que no haya solapes de profesor
        profesor_slots = {}
        for horario in horarios:
            key = (horario.profesor_id, horario.dia, horario.bloque)
            self.assertNotIn(key, profesor_slots, f"Solape de profesor en {key}")
            profesor_slots[key] = True
        
        # Verificar que solo se usen bloques tipo 'clase'
        bloques_clase = set(BloqueHorario.objects.filter(tipo='clase').values_list('numero', flat=True))
        for horario in horarios:
            self.assertIn(horario.bloque, bloques_clase, f"Bloque no válido: {horario.bloque}")