from django.test import TestCase, Client
from django.urls import reverse
from horarios.models import (
    Profesor, Materia, Curso, Grado, Aula, BloqueHorario, 
    Horario, MateriaProfesor, MateriaGrado, DisponibilidadProfesor
)


class ViewsTestCase(TestCase):
    def setUp(self):
        """Configurar datos de prueba"""
        self.client = Client()
        
        # Crear datos básicos
        self.grado = Grado.objects.create(nombre='PRIMERO')
        self.profesor = Profesor.objects.create(nombre='Juan Pérez')
        self.materia = Materia.objects.create(
            nombre='Matemáticas',
            bloques_por_semana=5
        )
        self.curso = Curso.objects.create(
            nombre='1A',
            grado=self.grado
        )
        self.aula = Aula.objects.create(
            nombre='AULA-101',
            capacidad=40
        )
        
        # Crear bloques de horario
        from datetime import time
        self.bloque1 = BloqueHorario.objects.create(
            numero=1,
            hora_inicio=time(8, 0),
            hora_fin=time(9, 0),
            tipo='clase'
        )
        
        # Crear disponibilidad del profesor
        self.disponibilidad = DisponibilidadProfesor.objects.create(
            profesor=self.profesor,
            dia='lunes',
            bloque_inicio=1,
            bloque_fin=6
        )
        
        # Crear asignaciones
        self.materia_profesor = MateriaProfesor.objects.create(
            profesor=self.profesor,
            materia=self.materia
        )
        self.materia_grado = MateriaGrado.objects.create(
            grado=self.grado,
            materia=self.materia
        )
        
        # Crear horario
        self.horario = Horario.objects.create(
            curso=self.curso,
            materia=self.materia,
            profesor=self.profesor,
            aula=self.aula,
            dia='lunes',
            bloque=1
        )

    def test_dashboard_view(self):
        """Test que la vista dashboard se carga correctamente"""
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'frontend/dashboard.html')
        
        # Verificar que los datos están en el contexto
        self.assertIn('total_cursos', response.context)
        self.assertIn('total_profesores', response.context)
        self.assertIn('total_horarios', response.context)

    def test_horario_curso_view(self):
        """Test que la vista de horario por curso funciona"""
        response = self.client.get(reverse('horario_curso', args=[self.curso.id]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'frontend/horario.html')

    def test_horario_profesor_view(self):
        """Test que la vista de horario por profesor funciona"""
        response = self.client.get(reverse('horario_profesor', args=[self.profesor.id]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'frontend/horario.html')

    def test_horario_aula_view(self):
        """Test que la vista de horario por aula funciona"""
        response = self.client.get(reverse('horario_aula', args=[self.aula.id]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'frontend/horario.html')

    def test_validar_datos_view(self):
        """Test que la vista de validación de datos funciona"""
        response = self.client.get(reverse('validar_datos'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'frontend/validaciones.html')
        self.assertIn('errores', response.context)

    def test_lista_cursos_view(self):
        """Test que la vista de lista de cursos funciona"""
        response = self.client.get(reverse('lista_cursos'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'frontend/lista_cursos.html')
        self.assertIn('page_obj', response.context)

    def test_lista_profesores_view(self):
        """Test que la vista de lista de profesores funciona"""
        response = self.client.get(reverse('lista_profesores'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'frontend/lista_profesores.html')
        self.assertIn('page_obj', response.context)

    def test_horario_ajax_view(self):
        """Test que la vista AJAX de horarios funciona"""
        response = self.client.get(reverse('horario_ajax'), {
            'tipo': 'curso',
            'id': self.curso.id
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/json')
        
        data = response.json()
        self.assertIn('titulo', data)
        self.assertIn('horarios', data)

    def test_estadisticas_ajax_view(self):
        """Test que la vista AJAX de estadísticas funciona"""
        response = self.client.get(reverse('estadisticas_ajax'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/json')
        
        data = response.json()
        self.assertIn('total_cursos', data)
        self.assertIn('total_profesores', data)

    def test_generar_horario_view_get(self):
        """Test que la vista de generar horario redirige en GET"""
        response = self.client.get(reverse('generar_horario'))
        self.assertEqual(response.status_code, 302)  # Redirección

    def test_pdf_curso_view(self):
        """Test que la vista de PDF funciona"""
        response = self.client.get(reverse('pdf_curso', args=[self.curso.id]))
        # En el entorno de test, xhtml2pdf puede no estar disponible
        if response.status_code == 503:
            self.assertEqual(response.content, b"El generador de PDF no est\xc3\xa1 disponible en este entorno.")
        else:
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response['Content-Type'], 'application/pdf')

    def test_404_curso_inexistente(self):
        """Test que se maneja correctamente un curso inexistente"""
        non_existing_id = Curso.objects.order_by('-id').values_list('id', flat=True).first()
        non_existing_id = (non_existing_id or 0) + 1
        response = self.client.get(reverse('horario_curso', args=[non_existing_id]))
        self.assertEqual(response.status_code, 404)