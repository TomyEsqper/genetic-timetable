from django.test import TestCase
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from horarios.models import (
    Profesor, Materia, Curso, Grado, Aula, BloqueHorario, 
    Horario, MateriaProfesor, MateriaGrado, DisponibilidadProfesor
)
from datetime import time


class ProfesorModelTest(TestCase):
    def setUp(self):
        self.profesor_data = {
            'nombre': 'Juan Pérez'
        }

    def test_validaciones_profesor(self):
        """Test validaciones de reglas de negocio para Profesor"""
        # 1. Nombre inválido (minúscula)
        with self.assertRaises(ValidationError):
            p = Profesor(nombre='juan perez')
            p.full_clean()

        # 2. Nombre con caracteres especiales
        with self.assertRaises(ValidationError):
            p = Profesor(nombre='Juan123')
            p.full_clean()

        # 3. Nombre duplicado
        Profesor.objects.create(**self.profesor_data)
        with self.assertRaises(ValidationError):
            p = Profesor(nombre='Juan Pérez')
            p.full_clean()


class MateriaModelTest(TestCase):
    def setUp(self):
        self.materia_data = {
            'nombre': 'Matemáticas',
            'bloques_por_semana': 5,
            'jornada_preferida': 'mañana'
        }

    def test_validaciones_materia(self):
        """Test validaciones de reglas de negocio para Materia"""
        # 1. Bloques excesivos
        with self.assertRaises(ValidationError):
            m = Materia(nombre='Test', bloques_por_semana=50)
            m.full_clean()

        # 2. Cero bloques
        with self.assertRaises(ValidationError):
            m = Materia(nombre='Test', bloques_por_semana=0)
            m.full_clean()

        # 3. Nombre duplicado
        Materia.objects.create(**self.materia_data)
        with self.assertRaises(ValidationError):
            m = Materia(nombre='Matemáticas', bloques_por_semana=3)
            m.full_clean()


class GradoModelTest(TestCase):
    def test_validaciones_grado(self):
        """Test validaciones de reglas de negocio para Grado"""
        # 1. Nombre inválido
        with self.assertRaises(ValidationError):
            g = Grado(nombre='Primero!')
            g.full_clean()

        # 2. Nombre duplicado
        Grado.objects.create(nombre='PRIMERO')
        with self.assertRaises(ValidationError):
            g = Grado(nombre='PRIMERO')
            g.full_clean()


class AulaModelTest(TestCase):
    def setUp(self):
        self.aula_data = {
            'nombre': 'AULA-101',
            'tipo': 'comun',
            'capacidad': 40
        }

    def test_validaciones_aula(self):
        """Test validaciones de reglas de negocio para Aula"""
        # 1. Capacidad inválida
        with self.assertRaises(ValidationError):
            a = Aula(nombre='TEST', capacidad=300)
            a.full_clean()
            
        with self.assertRaises(ValidationError):
            a = Aula(nombre='TEST', capacidad=0)
            a.full_clean()

        # 2. Nombre inválido (minúsculas)
        with self.assertRaises(ValidationError):
            a = Aula(nombre='aula 101', capacidad=40)
            a.full_clean()


class BloqueHorarioModelTest(TestCase):
    def test_validaciones_bloque(self):
        """Test validaciones de reglas de negocio para BloqueHorario"""
        # 1. Hora inicio > Hora fin
        with self.assertRaises(ValidationError):
            b = BloqueHorario(
                numero=1,
                hora_inicio=time(9, 0),
                hora_fin=time(8, 0),
                tipo='clase'
            )
            b.full_clean()

        # 2. Número inválido
        with self.assertRaises(ValidationError):
            b = BloqueHorario(
                numero=0,
                hora_inicio=time(8, 0),
                hora_fin=time(9, 0),
                tipo='clase'
            )
            b.full_clean()


class DisponibilidadProfesorModelTest(TestCase):
    def setUp(self):
        self.profesor = Profesor.objects.create(nombre='Juan Pérez')

    def test_validaciones_disponibilidad(self):
        """Test validaciones de reglas de negocio para Disponibilidad"""
        # 1. Bloque inicio > Bloque fin
        with self.assertRaises(ValidationError):
            d = DisponibilidadProfesor(
                profesor=self.profesor,
                dia='lunes',
                bloque_inicio=5,
                bloque_fin=2
            )
            d.full_clean()
