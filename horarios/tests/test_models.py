from django.test import TestCase
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from horarios.models import (
    Profesor, Materia, Curso, Grado, Aula, BloqueHorario, 
    Horario, MateriaProfesor, MateriaGrado, DisponibilidadProfesor
)


class ProfesorModelTest(TestCase):
    def setUp(self):
        self.profesor_data = {
            'nombre': 'Juan Pérez'
        }

    def test_crear_profesor_valido(self):
        """Test que un profesor con nombre válido se crea correctamente"""
        profesor = Profesor.objects.create(**self.profesor_data)
        self.assertEqual(profesor.nombre, 'Juan Pérez')
        self.assertEqual(str(profesor), 'Juan Pérez')

    def test_nombre_profesor_invalido(self):
        """Test que un nombre inválido genera error de validación"""
        # Nombre que no empieza con mayúscula
        with self.assertRaises(ValidationError):
            profesor = Profesor(nombre='juan perez')
            profesor.full_clean()

        # Nombre con caracteres especiales
        with self.assertRaises(ValidationError):
            profesor = Profesor(nombre='Juan123')
            profesor.full_clean()

    def test_nombre_profesor_duplicado(self):
        """Test que no se pueden crear profesores con el mismo nombre"""
        Profesor.objects.create(**self.profesor_data)
        
        with self.assertRaises(ValidationError):
            profesor = Profesor(nombre='Juan Pérez')
            profesor.full_clean()

    def test_nombre_profesor_muy_corto(self):
        """Test que un nombre muy corto genera error"""
        with self.assertRaises(ValidationError):
            profesor = Profesor(nombre='A')
            profesor.full_clean()


class MateriaModelTest(TestCase):
    def setUp(self):
        self.materia_data = {
            'nombre': 'Matemáticas',
            'bloques_por_semana': 5,
            'jornada_preferida': 'mañana'
        }

    def test_crear_materia_valida(self):
        """Test que una materia válida se crea correctamente"""
        materia = Materia.objects.create(**self.materia_data)
        self.assertEqual(materia.nombre, 'Matemáticas')
        self.assertEqual(materia.bloques_por_semana, 5)
        self.assertEqual(str(materia), 'Matemáticas')

    def test_bloques_por_semana_invalidos(self):
        """Test que bloques por semana inválidos generan error"""
        # Demasiados bloques
        with self.assertRaises(ValidationError):
            materia = Materia(nombre='Test', bloques_por_semana=50)
            materia.full_clean()

        # Cero bloques
        with self.assertRaises(ValidationError):
            materia = Materia(nombre='Test', bloques_por_semana=0)
            materia.full_clean()

    def test_nombre_materia_duplicado(self):
        """Test que no se pueden crear materias con el mismo nombre"""
        Materia.objects.create(**self.materia_data)
        
        with self.assertRaises(ValidationError):
            materia = Materia(nombre='Matemáticas', bloques_por_semana=3)
            materia.full_clean()


class GradoModelTest(TestCase):
    def test_crear_grado_valido(self):
        """Test que un grado válido se crea correctamente"""
        grado = Grado.objects.create(nombre='PRIMERO')
        self.assertEqual(grado.nombre, 'PRIMERO')
        self.assertEqual(str(grado), 'PRIMERO')

    def test_nombre_grado_invalido(self):
        """Test que un nombre de grado inválido genera error"""
        # Nombre con caracteres no permitidos
        with self.assertRaises(ValidationError):
            grado = Grado(nombre='Primero!')
            grado.full_clean()

    def test_nombre_grado_duplicado(self):
        """Test que no se pueden crear grados con el mismo nombre"""
        Grado.objects.create(nombre='PRIMERO')
        
        with self.assertRaises(ValidationError):
            grado = Grado(nombre='PRIMERO')
            grado.full_clean()


class AulaModelTest(TestCase):
    def setUp(self):
        self.aula_data = {
            'nombre': 'AULA-101',
            'tipo': 'comun',
            'capacidad': 40
        }

    def test_crear_aula_valida(self):
        """Test que un aula válida se crea correctamente"""
        aula = Aula.objects.create(**self.aula_data)
        self.assertEqual(aula.nombre, 'AULA-101')
        self.assertEqual(aula.capacidad, 40)
        self.assertEqual(str(aula), 'AULA-101 (comun)')

    def test_capacidad_aula_invalida(self):
        """Test que capacidades inválidas generan error"""
        # Capacidad muy alta
        with self.assertRaises(ValidationError):
            aula = Aula(nombre='TEST', capacidad=300)
            aula.full_clean()

        # Capacidad cero
        with self.assertRaises(ValidationError):
            aula = Aula(nombre='TEST', capacidad=0)
            aula.full_clean()

    def test_nombre_aula_invalido(self):
        """Test que un nombre de aula inválido genera error"""
        with self.assertRaises(ValidationError):
            aula = Aula(nombre='aula 101', capacidad=40)
            aula.full_clean()


class BloqueHorarioModelTest(TestCase):
    def test_crear_bloque_valido(self):
        """Test que un bloque válido se crea correctamente"""
        from datetime import time
        bloque = BloqueHorario.objects.create(
            numero=1,
            hora_inicio=time(8, 0),
            hora_fin=time(9, 0),
            tipo='clase'
        )
        self.assertEqual(bloque.numero, 1)
        self.assertEqual(str(bloque), 'Bloque 1 (clase)')

    def test_hora_inicio_mayor_hora_fin(self):
        """Test que hora de inicio mayor a hora de fin genera error"""
        from datetime import time
        with self.assertRaises(ValidationError):
            bloque = BloqueHorario(
                numero=1,
                hora_inicio=time(9, 0),
                hora_fin=time(8, 0),
                tipo='clase'
            )
            bloque.full_clean()

    def test_numero_bloque_invalido(self):
        """Test que número de bloque inválido genera error"""
        from datetime import time
        with self.assertRaises(ValidationError):
            bloque = BloqueHorario(
                numero=0,
                hora_inicio=time(8, 0),
                hora_fin=time(9, 0),
                tipo='clase'
            )
            bloque.full_clean()


class DisponibilidadProfesorModelTest(TestCase):
    def setUp(self):
        self.profesor = Profesor.objects.create(nombre='Juan Pérez')

    def test_crear_disponibilidad_valida(self):
        """Test que una disponibilidad válida se crea correctamente"""
        disponibilidad = DisponibilidadProfesor.objects.create(
            profesor=self.profesor,
            dia='lunes',
            bloque_inicio=1,
            bloque_fin=4
        )
        self.assertEqual(disponibilidad.profesor, self.profesor)
        self.assertEqual(disponibilidad.dia, 'lunes')

    def test_bloque_inicio_mayor_bloque_fin(self):
        """Test que bloque de inicio mayor al final genera error"""
        with self.assertRaises(ValidationError):
            disponibilidad = DisponibilidadProfesor(
                profesor=self.profesor,
                dia='lunes',
                bloque_inicio=5,
                bloque_fin=3
            )
            disponibilidad.full_clean()

    def test_disponibilidad_muy_larga(self):
        """Test que disponibilidad muy larga genera error"""
        with self.assertRaises(ValidationError):
            disponibilidad = DisponibilidadProfesor(
                profesor=self.profesor,
                dia='lunes',
                bloque_inicio=1,
                bloque_fin=10
            )
            disponibilidad.full_clean()

    def test_disponibilidad_duplicada_por_profesor_dia(self):
        """Test que no se puede tener dos disponibilidades para el mismo profesor y día"""
        DisponibilidadProfesor.objects.create(
            profesor=self.profesor,
            dia='lunes',
            bloque_inicio=1,
            bloque_fin=4
        )
        
        with self.assertRaises(IntegrityError):
            DisponibilidadProfesor.objects.create(
                profesor=self.profesor,
                dia='lunes',
                bloque_inicio=5,
                bloque_fin=6
            )


class HorarioModelTest(TestCase):
    def setUp(self):
        self.profesor = Profesor.objects.create(nombre='Juan Pérez')
        self.materia = Materia.objects.create(
            nombre='Matemáticas',
            bloques_por_semana=5
        )
        self.grado = Grado.objects.create(nombre='PRIMERO')
        self.curso = Curso.objects.create(
            nombre='1A',
            grado=self.grado
        )
        self.aula = Aula.objects.create(
            nombre='AULA-101',
            capacidad=40
        )
        self.bloque = BloqueHorario.objects.create(
            numero=1,
            tipo='clase'
        )
        
        # Crear disponibilidad para el profesor
        self.disponibilidad = DisponibilidadProfesor.objects.create(
            profesor=self.profesor,
            dia='lunes',
            bloque_inicio=1,
            bloque_fin=6
        )

    def test_crear_horario_valido(self):
        """Test que un horario válido se crea correctamente"""
        horario = Horario.objects.create(
            curso=self.curso,
            materia=self.materia,
            profesor=self.profesor,
            aula=self.aula,
            dia='lunes',
            bloque=1
        )
        self.assertEqual(horario.curso, self.curso)
        self.assertEqual(horario.materia, self.materia)
        self.assertEqual(str(horario), '1A - Matemáticas - lunes Bloque 1')

    def test_horario_sin_disponibilidad_profesor(self):
        """Test que un horario sin disponibilidad del profesor genera error"""
        # Eliminar disponibilidad
        self.disponibilidad.delete()
        
        with self.assertRaises(ValidationError):
            horario = Horario(
                curso=self.curso,
                materia=self.materia,
                profesor=self.profesor,
                aula=self.aula,
                dia='lunes',
                bloque=1
            )
            horario.full_clean()

    def test_horario_duplicado_curso_dia_bloque(self):
        """Test que no se puede tener dos horarios para el mismo curso, día y bloque"""
        Horario.objects.create(
            curso=self.curso,
            materia=self.materia,
            profesor=self.profesor,
            aula=self.aula,
            dia='lunes',
            bloque=1
        )
        
        with self.assertRaises(IntegrityError):
            Horario.objects.create(
                curso=self.curso,
                materia=self.materia,
                profesor=self.profesor,
                aula=self.aula,
                dia='lunes',
                bloque=1
            )

    def test_horario_duplicado_profesor_dia_bloque(self):
        """Test que no se puede tener dos horarios para el mismo profesor, día y bloque"""
        Horario.objects.create(
            curso=self.curso,
            materia=self.materia,
            profesor=self.profesor,
            aula=self.aula,
            dia='lunes',
            bloque=1
        )
        
        # Crear otro curso
        curso2 = Curso.objects.create(nombre='1B', grado=self.grado)
        
        with self.assertRaises(IntegrityError):
            Horario.objects.create(
                curso=curso2,
                materia=self.materia,
                profesor=self.profesor,
                aula=self.aula,
                dia='lunes',
                bloque=1
            )


class MateriaProfesorModelTest(TestCase):
    def setUp(self):
        self.profesor = Profesor.objects.create(nombre='Juan Pérez')
        self.materia = Materia.objects.create(
            nombre='Matemáticas',
            bloques_por_semana=5
        )

    def test_crear_asignacion_valida(self):
        """Test que una asignación válida se crea correctamente"""
        asignacion = MateriaProfesor.objects.create(
            profesor=self.profesor,
            materia=self.materia
        )
        self.assertEqual(asignacion.profesor, self.profesor)
        self.assertEqual(asignacion.materia, self.materia)
        self.assertEqual(str(asignacion), 'Juan Pérez - Matemáticas')

    def test_asignacion_duplicada(self):
        """Test que no se puede asignar la misma materia al mismo profesor dos veces"""
        MateriaProfesor.objects.create(
            profesor=self.profesor,
            materia=self.materia
        )
        
        with self.assertRaises(IntegrityError):
            MateriaProfesor.objects.create(
                profesor=self.profesor,
                materia=self.materia
            )


class MateriaGradoModelTest(TestCase):
    def setUp(self):
        self.grado = Grado.objects.create(nombre='PRIMERO')
        self.materia = Materia.objects.create(
            nombre='Matemáticas',
            bloques_por_semana=5
        )

    def test_crear_asignacion_valida(self):
        """Test que una asignación válida se crea correctamente"""
        asignacion = MateriaGrado.objects.create(
            grado=self.grado,
            materia=self.materia
        )
        self.assertEqual(asignacion.grado, self.grado)
        self.assertEqual(asignacion.materia, self.materia)
        self.assertEqual(str(asignacion), 'PRIMERO - Matemáticas')

    def test_asignacion_duplicada(self):
        """Test que no se puede asignar la misma materia al mismo grado dos veces"""
        MateriaGrado.objects.create(
            grado=self.grado,
            materia=self.materia
        )
        
        with self.assertRaises(IntegrityError):
            MateriaGrado.objects.create(
                grado=self.grado,
                materia=self.materia
            )