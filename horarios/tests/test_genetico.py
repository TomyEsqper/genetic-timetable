"""
Tests para el algoritmo genético de generación de horarios.
"""

import pytest
import time
import random
from django.test import TestCase
from django.db import transaction
from horarios.models import (
    Profesor, Materia, Curso, Aula, Grado, MateriaGrado, 
    MateriaProfesor, DisponibilidadProfesor, BloqueHorario, Horario
)
from horarios.application.services.genetico import (
    generar_horarios_genetico, cargar_datos, evaluar_fitness,
    inicializar_poblacion, Cromosoma, pre_validacion_dura
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
        
        # Crear bloques horarios (5 bloques por día)
        for i in range(1, 6):
            BloqueHorario.objects.create(
                numero=i,
                hora_inicio=f"{7+i:02d}:00",
                hora_fin=f"{8+i:02d}:00",
                tipo="clase"
            )
        
        # Crear materias con bloques_por_semana que sumen exactamente 25 (5 días * 5 bloques)
        self.materia1 = Materia.objects.create(
            nombre="Matemáticas",
            bloques_por_semana=10,  # 10 bloques por semana
            jornada_preferida="mañana"
        )
        self.materia2 = Materia.objects.create(
            nombre="Lenguaje",
            bloques_por_semana=8,  # 8 bloques por semana
            jornada_preferida="mañana"
        )
        self.materia3 = Materia.objects.create(
            nombre="Ciencias",
            bloques_por_semana=7,  # 7 bloques por semana
            jornada_preferida="mañana"
        )
        
        # Crear profesores
        self.profesor1 = Profesor.objects.create(nombre="Ana García")
        self.profesor2 = Profesor.objects.create(nombre="Carlos López")
        self.profesor3 = Profesor.objects.create(nombre="María Fernández")
        
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
        MateriaGrado.objects.create(materia=self.materia2, grado=self.grado1)
        MateriaGrado.objects.create(materia=self.materia3, grado=self.grado1)
        
        MateriaGrado.objects.create(materia=self.materia1, grado=self.grado2)
        MateriaGrado.objects.create(materia=self.materia2, grado=self.grado2)
        MateriaGrado.objects.create(materia=self.materia3, grado=self.grado2)
        
        # Crear relaciones materia-profesor
        MateriaProfesor.objects.create(materia=self.materia1, profesor=self.profesor1)
        MateriaProfesor.objects.create(materia=self.materia2, profesor=self.profesor2)
        MateriaProfesor.objects.create(materia=self.materia3, profesor=self.profesor3)
        
        # Crear disponibilidad de profesores (todos los días, todos los bloques)
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
            DisponibilidadProfesor.objects.create(
                profesor=self.profesor3,
                dia=dia,
                bloque_inicio=1,
                bloque_fin=5
            )
    
    def test_pre_validacion_dura(self):
        """Test para verificar la pre-validación dura."""
        datos = cargar_datos()
        errores = pre_validacion_dura(datos)
        
        # Debería no haber errores porque los bloques suman exactamente 25 por curso
        self.assertEqual(len(errores), 0, f"Pre-validación falló: {errores}")
    
    def test_cargar_datos(self):
        """Test para verificar que se cargan correctamente los datos."""
        datos = cargar_datos()
        
        self.assertIsNotNone(datos)
        self.assertEqual(len(datos.cursos), 2)
        self.assertEqual(len(datos.materias), 3)
        self.assertEqual(len(datos.profesores), 3)
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
        self.assertIn('status', metricas)
        self.assertIn('mejor_fitness_final', metricas)
        self.assertIn('conflictos_finales', metricas)
        
        # Verificar que se crearon horarios
        horarios = Horario.objects.all()
        self.assertGreater(len(horarios), 0)


class TestRestricciones(TestCase):
    """Tests para verificar que se respetan todas las restricciones."""
    
    def setUp(self):
        """Configurar datos de prueba para restricciones."""
        self.crear_datos_prueba()
    
    def crear_datos_prueba(self):
        """Crea datos de prueba para verificar restricciones."""
        # Crear grados
        self.grado1 = Grado.objects.create(nombre="Primero")
        
        # Crear aulas
        self.aula1 = Aula.objects.create(nombre="Aula 101", tipo="comun", capacidad=30)
        
        # Crear bloques horarios (6 bloques por día)
        for i in range(1, 7):
            BloqueHorario.objects.create(
                numero=i,
                hora_inicio=f"{7+i:02d}:00",
                hora_fin=f"{8+i:02d}:00",
                tipo="clase"
            )
        
        # Crear materias que sumen exactamente 30 bloques (5 días * 6 bloques)
        self.materia1 = Materia.objects.create(
            nombre="Matemáticas",
            bloques_por_semana=12,  # 12 bloques por semana
            jornada_preferida="mañana"
        )
        self.materia2 = Materia.objects.create(
            nombre="Lenguaje",
            bloques_por_semana=10,  # 10 bloques por semana
            jornada_preferida="mañana"
        )
        self.materia3 = Materia.objects.create(
            nombre="Ciencias",
            bloques_por_semana=8,  # 8 bloques por semana
            jornada_preferida="mañana"
        )
        
        # Crear profesores
        self.profesor1 = Profesor.objects.create(nombre="Ana García")
        self.profesor2 = Profesor.objects.create(nombre="Carlos López")
        self.profesor3 = Profesor.objects.create(nombre="María Fernández")
        
        # Crear curso
        self.curso1 = Curso.objects.create(
            nombre="Primero A",
            grado=self.grado1,
            aula_fija=self.aula1
        )
        
        # Crear relaciones materia-grado
        MateriaGrado.objects.create(materia=self.materia1, grado=self.grado1)
        MateriaGrado.objects.create(materia=self.materia2, grado=self.grado1)
        MateriaGrado.objects.create(materia=self.materia3, grado=self.grado1)
        
        # Crear relaciones materia-profesor
        MateriaProfesor.objects.create(materia=self.materia1, profesor=self.profesor1)
        MateriaProfesor.objects.create(materia=self.materia2, profesor=self.profesor2)
        MateriaProfesor.objects.create(materia=self.materia3, profesor=self.profesor3)
        
        # Crear disponibilidad de profesores
        dias = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes']
        for dia in dias:
            DisponibilidadProfesor.objects.create(
                profesor=self.profesor1,
                dia=dia,
                bloque_inicio=1,
                bloque_fin=6
            )
            DisponibilidadProfesor.objects.create(
                profesor=self.profesor2,
                dia=dia,
                bloque_inicio=1,
                bloque_fin=6
            )
            DisponibilidadProfesor.objects.create(
                profesor=self.profesor3,
                dia=dia,
                bloque_inicio=1,
                bloque_fin=6
            )
    
    def test_sin_huecos_en_bloques_de_clase(self):
        """Test para verificar que no hay huecos en los bloques de clase."""
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
        
        # Verificar que todos los bloques de clase están ocupados
        slots_ocupados = set()
        for horario in horarios:
            slot = (horario.curso_id, horario.dia, horario.bloque)
            slots_ocupados.add(slot)
        
        # Calcular slots totales esperados (1 curso * 5 días * 6 bloques)
        slots_totales = set()
        for dia in ['lunes', 'martes', 'miércoles', 'jueves', 'viernes']:
            for bloque in range(1, 7):
                slots_totales.add((self.curso1.id, dia, bloque))
        
        # Verificar que no hay huecos
        huecos = slots_totales - slots_ocupados
        self.assertEqual(len(huecos), 0, f"Se encontraron huecos: {huecos}")
    
    def test_cumple_bloques_por_semana(self):
        """Test para verificar que se cumplen los bloques_por_semana."""
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
            self.assertEqual(count, materia.bloques_por_semana,
                           f"Se asignaron {count} bloques a {materia.nombre} pero se requieren {materia.bloques_por_semana}")
    
    def test_sin_solapes(self):
        """Test para verificar que no hay solapes."""
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
    
    def test_respeta_disponibilidad(self):
        """Test para verificar que se respeta la disponibilidad de profesores."""
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
        
        # Verificar que cada asignación respeta la disponibilidad del profesor
        for horario in horarios:
            disponibilidad = DisponibilidadProfesor.objects.filter(
                profesor=horario.profesor,
                dia=horario.dia,
                bloque_inicio__lte=horario.bloque,
                bloque_fin__gte=horario.bloque
            )
            
            self.assertTrue(disponibilidad.exists(),
                          f"El profesor {horario.profesor.nombre} no tiene disponibilidad en {horario.dia} bloque {horario.bloque}")


class TestPreValidacion(TestCase):
    """Tests para la pre-validación dura."""
    
    def test_pre_validacion_falla_con_datos_invalidos(self):
        """Test para verificar que la pre-validación falla con datos inválidos."""
        # Crear datos que no sumen correctamente
        grado = Grado.objects.create(nombre="Primero")
        aula = Aula.objects.create(nombre="Aula 101", tipo="comun", capacidad=30)
        
        # Crear bloques horarios (5 bloques por día)
        for i in range(1, 6):
            BloqueHorario.objects.create(
                numero=i,
                hora_inicio=f"{7+i:02d}:00",
                hora_fin=f"{8+i:02d}:00",
                tipo="clase"
            )
        
        # Crear materias que sumen más de 25 bloques (imposible)
        materia1 = Materia.objects.create(
            nombre="Matemáticas",
            bloques_por_semana=15,  # Demasiados bloques
            jornada_preferida="mañana"
        )
        materia2 = Materia.objects.create(
            nombre="Lenguaje",
            bloques_por_semana=15,  # Demasiados bloques
            jornada_preferida="mañana"
        )
        
        profesor = Profesor.objects.create(nombre="Ana García")
        curso = Curso.objects.create(nombre="Primero A", grado=grado, aula_fija=aula)
        
        # Crear relaciones
        MateriaGrado.objects.create(materia=materia1, grado=grado)
        MateriaGrado.objects.create(materia=materia2, grado=grado)
        MateriaProfesor.objects.create(materia=materia1, profesor=profesor)
        MateriaProfesor.objects.create(materia=materia2, profesor=profesor)
        
        # Crear disponibilidad
        dias = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes']
        for dia in dias:
            DisponibilidadProfesor.objects.create(
                profesor=profesor,
                dia=dia,
                bloque_inicio=1,
                bloque_fin=5
            )
        
        # Verificar que la pre-validación detecta el error
        datos = cargar_datos()
        errores = pre_validacion_dura(datos)
        
        self.assertGreater(len(errores), 0, "La pre-validación debería detectar que faltan bloques")
        self.assertTrue(any("faltan" in error for error in errores), "Debería indicar que faltan bloques")


class TestRendimiento(TestCase):
    """Tests de rendimiento."""
    
    def setUp(self):
        """Configurar datos de prueba para rendimiento."""
        self.crear_dataset_pequeno()
    
    def crear_dataset_pequeno(self):
        """Crea un dataset pequeño para pruebas de rendimiento."""
        # Crear grados
        grados = []
        for i in range(2):
            grado = Grado.objects.create(nombre=f"Grado {i+1}")
            grados.append(grado)
        
        # Crear aulas
        aulas = []
        for i in range(3):
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
        
        # Crear materias que sumen exactamente 25 bloques por curso
        materias = []
        nombres_materias = ['Matemáticas', 'Lenguaje', 'Ciencias', 'Historia', 'Inglés']
        bloques_por_materia = [6, 5, 5, 5, 4]  # Suma 25
        
        for nombre, bloques in zip(nombres_materias, bloques_por_materia):
            materia = Materia.objects.create(
                nombre=nombre,
                bloques_por_semana=bloques,
                jornada_preferida="mañana"
            )
            materias.append(materia)
        
        # Crear profesores
        profesores = []
        for i in range(5):
            profesor = Profesor.objects.create(nombre=f"Profesor {i+1}")
            profesores.append(profesor)
        
        # Crear cursos
        cursos = []
        for i in range(2):
            curso = Curso.objects.create(
                nombre=f"Curso {i+1}",
                grado=grados[i],
                aula_fija=aulas[i]
            )
            cursos.append(curso)
        
        # Crear relaciones
        for materia in materias:
            # Asignar a grados
            for grado in grados:
                MateriaGrado.objects.create(materia=materia, grado=grado)
            
            # Asignar profesores
            for profesor in profesores:
                MateriaProfesor.objects.create(materia=materia, profesor=profesor)
        
        # Crear disponibilidad
        dias = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes']
        for profesor in profesores:
            for dia in dias:
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
        self.assertIn('status', metricas)
    
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
        self.assertIsInstance(metricas, dict)
    
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
        self.assertIsInstance(metricas, dict)


# Importar random para las pruebas
import random