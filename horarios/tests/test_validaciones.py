"""
Tests para validaciones de horarios.
"""

from django.test import TestCase
from django.db import IntegrityError
from django.core.exceptions import ValidationError

from horarios.models import (
    Curso, Materia, Profesor, Aula, Horario, BloqueHorario,
    DisponibilidadProfesor, MateriaGrado, MateriaProfesor, Grado
)
from horarios.domain.validators.validadores import validar_antes_de_persistir, ValidadorHorarios


class TestValidacionesHorarios(TestCase):
    """Tests para las validaciones de horarios."""
    
    def setUp(self):
        """Configurar datos de prueba."""
        # Crear bloques
        self.bloque1 = BloqueHorario.objects.create(
            numero=1, hora_inicio='08:00', hora_fin='09:00', tipo='clase'
        )
        self.bloque2 = BloqueHorario.objects.create(
            numero=2, hora_inicio='09:00', hora_fin='10:00', tipo='clase'
        )
        self.bloque_recreo = BloqueHorario.objects.create(
            numero=3, hora_inicio='10:00', hora_fin='10:15', tipo='descanso'
        )
        
        # Crear grado
        self.grado = Grado.objects.create(nombre='Primero')
        
        # Crear curso
        self.aula = Aula.objects.create(nombre='Aula 101', tipo='comun')
        self.curso = Curso.objects.create(
            nombre='1A', grado=self.grado, aula_fija=self.aula
        )
        
        # Crear materias
        self.materia1 = Materia.objects.create(
            nombre='Matemáticas', bloques_por_semana=3
        )
        self.materia2 = Materia.objects.create(
            nombre='Lenguaje', bloques_por_semana=2
        )
        
        # Crear profesores
        self.profesor1 = Profesor.objects.create(nombre='Profesor A')
        self.profesor2 = Profesor.objects.create(nombre='Profesor B')
        
        # Asignar materias a grado
        MateriaGrado.objects.create(grado=self.grado, materia=self.materia1)
        MateriaGrado.objects.create(grado=self.grado, materia=self.materia2)
        
        # Asignar profesores a materias
        MateriaProfesor.objects.create(profesor=self.profesor1, materia=self.materia1)
        MateriaProfesor.objects.create(profesor=self.profesor2, materia=self.materia2)
        
        # Crear disponibilidad de profesores
        DisponibilidadProfesor.objects.create(
            profesor=self.profesor1, dia='lunes', bloque_inicio=1, bloque_fin=2
        )
        DisponibilidadProfesor.objects.create(
            profesor=self.profesor1, dia='martes', bloque_inicio=1, bloque_fin=2
        )
        DisponibilidadProfesor.objects.create(
            profesor=self.profesor2, dia='lunes', bloque_inicio=1, bloque_fin=2
        )
        DisponibilidadProfesor.objects.create(
            profesor=self.profesor2, dia='martes', bloque_inicio=1, bloque_fin=2
        )
    
    def test_validacion_horario_valido(self):
        """Test que un horario válido pase todas las validaciones."""
        # Crear disponibilidad para miércoles
        DisponibilidadProfesor.objects.create(
            profesor=self.profesor1, dia='miércoles', bloque_inicio=1, bloque_fin=2
        )
        
        horarios = [
            {
                'curso_id': self.curso.id,
                'curso_nombre': self.curso.nombre,
                'materia_id': self.materia1.id,
                'materia_nombre': self.materia1.nombre,
                'profesor_id': self.profesor1.id,
                'profesor_nombre': self.profesor1.nombre,
                'aula_id': self.aula.id,
                'dia': 'lunes',
                'bloque': 1
            },
            {
                'curso_id': self.curso.id,
                'curso_nombre': self.curso.nombre,
                'materia_id': self.materia1.id,
                'materia_nombre': self.materia1.nombre,
                'profesor_id': self.profesor1.id,
                'profesor_nombre': self.profesor1.nombre,
                'aula_id': self.aula.id,
                'dia': 'martes',
                'bloque': 1
            },
            {
                'curso_id': self.curso.id,
                'curso_nombre': self.curso.nombre,
                'materia_id': self.materia1.id,
                'materia_nombre': self.materia1.nombre,
                'profesor_id': self.profesor1.id,
                'profesor_nombre': self.profesor1.nombre,
                'aula_id': self.aula.id,
                'dia': 'miércoles',
                'bloque': 1
            }
        ]
        
        resultado = validar_antes_de_persistir(horarios)
        self.assertTrue(resultado.es_valido)
        self.assertEqual(len(resultado.errores), 0)
    
    def test_validacion_duplicado_curso_dia_bloque(self):
        """Test que detecte duplicados en (curso, día, bloque)."""
        horarios = [
            {
                'curso_id': self.curso.id,
                'curso_nombre': self.curso.nombre,
                'materia_id': self.materia1.id,
                'materia_nombre': self.materia1.nombre,
                'profesor_id': self.profesor1.id,
                'profesor_nombre': self.profesor1.nombre,
                'aula_id': self.aula.id,
                'dia': 'lunes',
                'bloque': 1
            },
            {
                'curso_id': self.curso.id,
                'curso_nombre': self.curso.nombre,
                'materia_id': self.materia2.id,
                'materia_nombre': self.materia2.nombre,
                'profesor_id': self.profesor2.id,
                'profesor_nombre': self.profesor2.nombre,
                'aula_id': self.aula.id,
                'dia': 'lunes',
                'bloque': 1  # Mismo curso, día y bloque
            }
        ]
        
        resultado = validar_antes_de_persistir(horarios)
        self.assertFalse(resultado.es_valido)
        # Verificar que al menos hay un error de duplicado
        errores_duplicado = [e for e in resultado.errores if e.tipo == 'duplicado_curso_dia_bloque']
        self.assertGreater(len(errores_duplicado), 0)
    
    def test_validacion_choque_profesor(self):
        """Test que detecte choques de profesores."""
        horarios = [
            {
                'curso_id': self.curso.id,
                'curso_nombre': self.curso.nombre,
                'materia_id': self.materia1.id,
                'materia_nombre': self.materia1.nombre,
                'profesor_id': self.profesor1.id,
                'profesor_nombre': self.profesor1.nombre,
                'aula_id': self.aula.id,
                'dia': 'lunes',
                'bloque': 1
            },
            {
                'curso_id': self.curso.id,
                'curso_nombre': self.curso.nombre,
                'materia_id': self.materia2.id,
                'materia_nombre': self.materia2.nombre,
                'profesor_id': self.profesor1.id,  # Mismo profesor
                'profesor_nombre': self.profesor1.nombre,
                'aula_id': self.aula.id,
                'dia': 'lunes',
                'bloque': 1  # Mismo día y bloque
            }
        ]
        
        resultado = validar_antes_de_persistir(horarios)
        self.assertFalse(resultado.es_valido)
        # Verificar que al menos hay un error de choque de profesor
        errores_choque = [e for e in resultado.errores if e.tipo == 'choque_profesor_dia_bloque']
        self.assertGreater(len(errores_choque), 0)
    
    def test_validacion_disponibilidad_profesor(self):
        """Test que detecte asignaciones fuera de disponibilidad."""
        horarios = [
            {
                'curso_id': self.curso.id,
                'curso_nombre': self.curso.nombre,
                'materia_id': self.materia1.id,
                'materia_nombre': self.materia1.nombre,
                'profesor_id': self.profesor1.id,
                'profesor_nombre': self.profesor1.nombre,
                'aula_id': self.aula.id,
                'dia': 'jueves',  # Día no disponible
                'bloque': 1
            }
        ]
        
        resultado = validar_antes_de_persistir(horarios)
        self.assertFalse(resultado.es_valido)
        # Verificar que al menos hay un error de disponibilidad
        errores_disponibilidad = [e for e in resultado.errores if e.tipo == 'disponibilidad_profesor']
        self.assertGreater(len(errores_disponibilidad), 0)
    
    def test_validacion_bloque_tipo_invalido(self):
        """Test que detecte asignaciones en bloques no válidos."""
        horarios = [
            {
                'curso_id': self.curso.id,
                'curso_nombre': self.curso.nombre,
                'materia_id': self.materia1.id,
                'materia_nombre': self.materia1.nombre,
                'profesor_id': self.profesor1.id,
                'profesor_nombre': self.profesor1.nombre,
                'aula_id': self.aula.id,
                'dia': 'lunes',
                'bloque': 3  # Bloque de recreo
            }
        ]
        
        resultado = validar_antes_de_persistir(horarios)
        self.assertFalse(resultado.es_valido)
        # Verificar que al menos hay un error de bloque inválido
        errores_bloque = [e for e in resultado.errores if e.tipo == 'bloque_tipo_invalido']
        self.assertGreater(len(errores_bloque), 0)
    
    def test_validacion_bloques_por_semana(self):
        """Test que detecte materias con bloques incorrectos."""
        horarios = [
            {
                'curso_id': self.curso.id,
                'curso_nombre': self.curso.nombre,
                'materia_id': self.materia1.id,
                'materia_nombre': self.materia1.nombre,
                'profesor_id': self.profesor1.id,
                'profesor_nombre': self.profesor1.nombre,
                'aula_id': self.aula.id,
                'dia': 'lunes',
                'bloque': 1
            }
            # Solo 1 bloque para Matemáticas que requiere 3
        ]
        
        resultado = validar_antes_de_persistir(horarios)
        self.assertFalse(resultado.es_valido)
        self.assertEqual(len(resultado.errores), 1)
        self.assertEqual(resultado.errores[0].tipo, 'bloques_por_semana')
    
    def test_validacion_aula_fija(self):
        """Test que detecte asignaciones con aula incorrecta."""
        otra_aula = Aula.objects.create(nombre='Aula 102', tipo='comun')
        
        horarios = [
            {
                'curso_id': self.curso.id,
                'curso_nombre': self.curso.nombre,
                'materia_id': self.materia1.id,
                'materia_nombre': self.materia1.nombre,
                'profesor_id': self.profesor1.id,
                'profesor_nombre': self.profesor1.nombre,
                'aula_id': otra_aula.id,  # Aula incorrecta
                'dia': 'lunes',
                'bloque': 1
            }
        ]
        
        resultado = validar_antes_de_persistir(horarios)
        self.assertFalse(resultado.es_valido)
        # Verificar que al menos hay un error de aula fija
        errores_aula = [e for e in resultado.errores if e.tipo == 'aula_fija']
        self.assertGreater(len(errores_aula), 0)
    
    def test_persistencia_transaccion_atomica(self):
        """Test que la persistencia use transacciones atómicas."""
        # Crear horarios válidos
        horarios_validos = [
            {
                'curso_id': self.curso.id,
                'curso_nombre': self.curso.nombre,
                'materia_id': self.materia1.id,
                'materia_nombre': self.materia1.nombre,
                'profesor_id': self.profesor1.id,
                'profesor_nombre': self.profesor1.nombre,
                'aula_id': self.aula.id,
                'dia': 'lunes',
                'bloque': 1
            }
        ]
        
        # Crear horarios conflictivos
        horarios_conflictivos = [
            {
                'curso_id': self.curso.id,
                'curso_nombre': self.curso.nombre,
                'materia_id': self.materia1.id,
                'materia_nombre': self.materia1.nombre,
                'profesor_id': self.profesor1.id,
                'profesor_nombre': self.profesor1.nombre,
                'aula_id': self.aula.id,
                'dia': 'lunes',
                'bloque': 1
            },
            {
                'curso_id': self.curso.id,
                'curso_nombre': self.curso.nombre,
                'materia_id': self.materia2.id,
                'materia_nombre': self.materia2.nombre,
                'profesor_id': self.profesor2.id,
                'profesor_nombre': self.profesor2.nombre,
                'aula_id': self.aula.id,
                'dia': 'lunes',
                'bloque': 1  # Conflicto
            }
        ]
        
        # Verificar que los horarios válidos se persistan correctamente
        from django.db import transaction
        with transaction.atomic():
            for horario_data in horarios_validos:
                Horario.objects.create(
                    curso_id=horario_data['curso_id'],
                    materia_id=horario_data['materia_id'],
                    profesor_id=horario_data['profesor_id'],
                    aula_id=horario_data['aula_id'],
                    dia=horario_data['dia'],
                    bloque=horario_data['bloque']
                )
        
        # Verificar que se creó el horario
        self.assertEqual(Horario.objects.count(), 1)
        
        # Verificar que los horarios conflictivos fallen
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                for horario_data in horarios_conflictivos:
                    Horario.objects.create(
                        curso_id=horario_data['curso_id'],
                        materia_id=horario_data['materia_id'],
                        profesor_id=horario_data['profesor_id'],
                        aula_id=horario_data['aula_id'],
                        dia=horario_data['dia'],
                        bloque=horario_data['bloque']
                    )
        
        # Verificar que no se crearon horarios adicionales
        self.assertEqual(Horario.objects.count(), 1) 