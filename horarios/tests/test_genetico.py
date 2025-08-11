"""
Tests para el algoritmo genético de generación de horarios.
"""

import pytest
import time
from django.test import TestCase
from django.db import transaction
from horarios.models import (
    Profesor, Materia, Curso, Aula, Grado, MateriaGrado, 
    MateriaProfesor, DisponibilidadProfesor, BloqueHorario, Horario
)
from horarios.genetico import (
    generar_horarios_genetico, cargar_datos, evaluar_fitness,
    inicializar_poblacion, Cromosoma
)


class TestAlgoritmoGenetico(TestCase):
    """Tests para el algoritmo genético."""
    
    def setUp(self):
        """Configurar datos de prueba."""
        self.crear_datos_prueba()
    
    def crear_datos_prueba(self):
        """Crea un conjunto mínimo de datos para pruebas."""
        # Crear grados
        self.grado1 = Grado.objects.create(nombre="Primero")
        self.grado2 = Grado.objects.create(nombre="Segundo")
        
        # Crear aulas
        self.aula1 = Aula.objects.create(nombre="Aula 101", tipo="comun", capacidad=30)
        self.aula2 = Aula.objects.create(nombre="Aula 102", tipo="comun", capacidad=30)
        
        # Crear bloques horarios
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
            bloques_por_semana=3,
            jornada_preferida="mañana"
        )
        self.materia2 = Materia.objects.create(
            nombre="Lenguaje",
            bloques_por_semana=2,
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
        
        # Crear relaciones materia-grado
        MateriaGrado.objects.create(materia=self.materia1, grado=self.grado1)
        MateriaGrado.objects.create(materia=self.materia1, grado=self.grado2)
        MateriaGrado.objects.create(materia=self.materia2, grado=self.grado1)
        MateriaGrado.objects.create(materia=self.materia2, grado=self.grado2)
        
        # Crear relaciones materia-profesor
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
    
    def test_cargar_datos(self):
        """Test para verificar que se cargan correctamente los datos."""
        datos = cargar_datos()
        
        self.assertIsNotNone(datos)
        self.assertEqual(len(datos.cursos), 2)
        self.assertEqual(len(datos.materias), 2)
        self.assertEqual(len(datos.profesores), 2)
        self.assertEqual(len(datos.bloques_disponibles), 5)
    
    def test_inicializar_poblacion(self):
        """Test para verificar la inicialización de población."""
        datos = cargar_datos()
        poblacion = inicializar_poblacion(datos, tamano_poblacion=10, semilla=42)
        
        self.assertEqual(len(poblacion), 10)
        for cromosoma in poblacion:
            self.assertIsInstance(cromosoma, Cromosoma)
            self.assertIsInstance(cromosoma.genes, dict)
    
    def test_evaluar_fitness(self):
        """Test para verificar la evaluación de fitness."""
        datos = cargar_datos()
        cromosoma = Cromosoma()
        
        # Crear un cromosoma válido
        cromosoma.genes = {
            (self.curso1.id, 'lunes', 1): (self.materia1.id, self.profesor1.id),
            (self.curso1.id, 'martes', 2): (self.materia2.id, self.profesor2.id),
        }
        
        fitness, conflictos = evaluar_fitness(cromosoma, datos)
        
        self.assertIsInstance(fitness, float)
        self.assertIsInstance(conflictos, int)
        self.assertGreaterEqual(conflictos, 0)
    
    def test_generar_horarios_basico(self):
        """Test básico para generar horarios."""
        metricas = generar_horarios_genetico(
            poblacion_size=10,
            generaciones=5,
            prob_cruce=0.8,
            prob_mutacion=0.2,
            elite=2,
            paciencia=3,
            timeout_seg=30,
            semilla=42,
            workers=1
        )
        
        self.assertIsInstance(metricas, dict)
        self.assertIn('total_time_s', metricas)
        self.assertIn('n_generations', metricas)
        self.assertIn('best_fitness', metricas)
        self.assertIn('conflicts_hard', metricas)
        
        # Verificar que se crearon horarios
        horarios = Horario.objects.all()
        self.assertGreater(len(horarios), 0)
    
    def test_restricciones_sin_solapes(self):
        """Test para verificar que no hay solapes en los horarios generados."""
        generar_horarios_genetico(
            poblacion_size=20,
            generaciones=10,
            prob_cruce=0.8,
            prob_mutacion=0.2,
            elite=2,
            paciencia=5,
            timeout_seg=30,
            semilla=42,
            workers=1
        )
        
        horarios = Horario.objects.all()
        
        # Verificar que no hay solapes de curso
        slots_curso = set()
        for horario in horarios:
            slot = (horario.curso_id, horario.dia, horario.bloque)
            self.assertNotIn(slot, slots_curso, f"Solape detectado en curso: {slot}")
            slots_curso.add(slot)
        
        # Verificar que no hay solapes de profesor
        slots_profesor = set()
        for horario in horarios:
            slot = (horario.profesor_id, horario.dia, horario.bloque)
            self.assertNotIn(slot, slots_profesor, f"Solape detectado en profesor: {slot}")
            slots_profesor.add(slot)
    
    def test_bloques_tipo_clase(self):
        """Test para verificar que solo se usan bloques tipo 'clase'."""
        generar_horarios_genetico(
            poblacion_size=20,
            generaciones=10,
            prob_cruce=0.8,
            prob_mutacion=0.2,
            elite=2,
            paciencia=5,
            timeout_seg=30,
            semilla=42,
            workers=1
        )
        
        horarios = Horario.objects.all()
        
        for horario in horarios:
            bloque = BloqueHorario.objects.get(numero=horario.bloque)
            self.assertEqual(bloque.tipo, 'clase', 
                           f"Horario usa bloque tipo '{bloque.tipo}' en lugar de 'clase'")
    
    def test_bloques_por_semana(self):
        """Test para verificar que se respetan los bloques_por_semana."""
        generar_horarios_genetico(
            poblacion_size=20,
            generaciones=10,
            prob_cruce=0.8,
            prob_mutacion=0.2,
            elite=2,
            paciencia=5,
            timeout_seg=30,
            semilla=42,
            workers=1
        )
        
        horarios = Horario.objects.all()
        
        # Contar bloques por materia y curso
        bloques_por_materia_curso = {}
        for horario in horarios:
            key = (horario.curso_id, horario.materia_id)
            bloques_por_materia_curso[key] = bloques_por_materia_curso.get(key, 0) + 1
        
        # Verificar que se respetan los bloques_por_semana
        for (curso_id, materia_id), count in bloques_por_materia_curso.items():
            materia = Materia.objects.get(id=materia_id)
            self.assertLessEqual(count, materia.bloques_por_semana,
                               f"Se asignaron {count} bloques a {materia.nombre} pero solo se requieren {materia.bloques_por_semana}")


class TestRendimiento(TestCase):
    """Tests de rendimiento para diferentes tamaños de dataset."""
    
    def setUp(self):
        """Configurar datos de prueba para rendimiento."""
        self.crear_dataset_pequeno()
    
    def crear_dataset_pequeno(self):
        """Crea un dataset pequeño para pruebas de rendimiento."""
        # Crear grados
        grados = []
        for i in range(3):
            grado = Grado.objects.create(nombre=f"Grado {i+1}")
            grados.append(grado)
        
        # Crear aulas
        aulas = []
        for i in range(5):
            aula = Aula.objects.create(
                nombre=f"Aula {i+1:03d}",
                tipo="comun",
                capacidad=30
            )
            aulas.append(aula)
        
        # Crear bloques horarios
        for i in range(1, 6):
            BloqueHorario.objects.create(
                numero=i,
                hora_inicio=f"{7+i:02d}:00",
                hora_fin=f"{8+i:02d}:00",
                tipo="clase"
            )
        
        # Crear materias
        materias = []
        nombres_materias = ['Matemáticas', 'Lenguaje', 'Ciencias', 'Historia', 'Inglés']
        for nombre in nombres_materias:
            materia = Materia.objects.create(
                nombre=nombre,
                bloques_por_semana=random.randint(2, 4),
                jornada_preferida="mañana"
            )
            materias.append(materia)
        
        # Crear profesores
        profesores = []
        for i in range(8):
            profesor = Profesor.objects.create(nombre=f"Profesor {i+1}")
            profesores.append(profesor)
        
        # Crear cursos
        cursos = []
        for i in range(5):
            curso = Curso.objects.create(
                nombre=f"Curso {i+1}",
                grado=random.choice(grados),
                aula_fija=aulas[i % len(aulas)]
            )
            cursos.append(curso)
        
        # Crear relaciones
        for materia in materias:
            # Asignar a grados
            for grado in random.sample(grados, random.randint(1, len(grados))):
                MateriaGrado.objects.create(materia=materia, grado=grado)
            
            # Asignar profesores
            for profesor in random.sample(profesores, random.randint(1, 3)):
                MateriaProfesor.objects.create(materia=materia, profesor=profesor)
        
        # Crear disponibilidad
        dias = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes']
        for profesor in profesores:
            for dia in random.sample(dias, random.randint(3, 5)):
                DisponibilidadProfesor.objects.create(
                    profesor=profesor,
                    dia=dia,
                    bloque_inicio=1,
                    bloque_fin=5
                )
    
    def test_rendimiento_dataset_pequeno(self):
        """Test de rendimiento para dataset pequeño (< 30s)."""
        inicio = time.time()
        
        metricas = generar_horarios_genetico(
            poblacion_size=20,
            generaciones=10,
            prob_cruce=0.8,
            prob_mutacion=0.2,
            elite=2,
            paciencia=5,
            timeout_seg=30,
            semilla=42,
            workers=1
        )
        
        tiempo_total = time.time() - inicio
        
        self.assertLess(tiempo_total, 30, f"Dataset pequeño tardó {tiempo_total:.2f}s, debe ser < 30s")
        self.assertIsInstance(metricas, dict)
        self.assertIn('total_time_s', metricas)
    
    def test_paralelismo(self):
        """Test para verificar que el paralelismo funciona."""
        inicio = time.time()
        
        metricas = generar_horarios_genetico(
            poblacion_size=30,
            generaciones=15,
            prob_cruce=0.8,
            prob_mutacion=0.2,
            elite=3,
            paciencia=8,
            timeout_seg=60,
            semilla=42,
            workers=2  # Usar 2 workers
        )
        
        tiempo_total = time.time() - inicio
        
        self.assertLess(tiempo_total, 60, f"Test de paralelismo tardó {tiempo_total:.2f}s, debe ser < 60s")
        self.assertEqual(metricas['pool_size'], 2)
    
    def test_timeout(self):
        """Test para verificar que el timeout funciona."""
        inicio = time.time()
        
        metricas = generar_horarios_genetico(
            poblacion_size=50,
            generaciones=1000,  # Muchas generaciones
            prob_cruce=0.8,
            prob_mutacion=0.2,
            elite=5,
            paciencia=1000,  # Alta paciencia
            timeout_seg=5,  # Timeout corto
            semilla=42,
            workers=1
        )
        
        tiempo_total = time.time() - inicio
        
        self.assertLess(tiempo_total, 10, f"Test de timeout tardó {tiempo_total:.2f}s, debe ser < 10s")
        self.assertTrue(metricas['early_stopped'])


class TestValidaciones(TestCase):
    """Tests para validaciones de prerrequisitos."""
    
    def test_validacion_cursos_sin_aula(self):
        """Test para verificar validación de cursos sin aula fija."""
        # Crear curso sin aula fija
        grado = Grado.objects.create(nombre="Primero")
        Curso.objects.create(nombre="Curso sin aula", grado=grado, aula_fija=None)
        
        # Verificar que se detecta el error
        from api.views import GenerarHorarioView
        view = GenerarHorarioView()
        errores = view._validar_prerrequisitos()
        
        self.assertGreater(len(errores), 0)
        self.assertTrue(any("aula fija" in error.lower() for error in errores))
    
    def test_validacion_sin_bloques_clase(self):
        """Test para verificar validación sin bloques de tipo 'clase'."""
        # Crear solo bloques de descanso
        BloqueHorario.objects.create(
            numero=1,
            hora_inicio="08:00",
            hora_fin="09:00",
            tipo="descanso"
        )
        
        # Verificar que se detecta el error
        from api.views import GenerarHorarioView
        view = GenerarHorarioView()
        errores = view._validar_prerrequisitos()
        
        self.assertGreater(len(errores), 0)
        self.assertTrue(any("bloques de tipo 'clase'" in error.lower() for error in errores))
    
    def test_validacion_materia_sin_profesor(self):
        """Test para verificar validación de materias sin profesores."""
        # Crear materia sin profesor
        grado = Grado.objects.create(nombre="Primero")
        materia = Materia.objects.create(nombre="Materia sin profesor", bloques_por_semana=2)
        MateriaGrado.objects.create(materia=materia, grado=grado)
        
        # Verificar que se detecta el error
        from api.views import GenerarHorarioView
        view = GenerarHorarioView()
        errores = view._validar_prerrequisitos()
        
        self.assertGreater(len(errores), 0)
        self.assertTrue(any("no tiene profesores asignados" in error.lower() for error in errores))


# Importar random para las pruebas
import random