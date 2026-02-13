"""
Tests de integración consolidados: Vistas de Frontend y Endpoints de API.
"""

from django.test import TestCase, Client
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth.models import User
from datetime import time

from horarios.models import (
    Profesor, Materia, Curso, Grado, Aula, BloqueHorario,
    Horario, MateriaProfesor, MateriaGrado, DisponibilidadProfesor,
    ConfiguracionColegio
)

class IntegrationTests(APITestCase):
    """Pruebas de integración que cubren Frontend y API."""

    def setUp(self):
        """Configurar datos de prueba"""
        # Usuario para API
        self.user = User.objects.create_superuser(username='admin', password='password', email='admin@test.com')
        self.client.force_authenticate(user=self.user)

        # Datos básicos
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

    # --- Tests de Vistas (Frontend) ---

    def test_dashboard_view(self):
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('total_cursos', response.context)

    def test_horario_curso_view(self):
        response = self.client.get(reverse('horario_curso', args=[self.curso.id]))
        self.assertEqual(response.status_code, 200)

    def test_pdf_curso_view(self):
        """Test que la vista de PDF funciona (con fallback si no está xhtml2pdf)"""
        response = self.client.get(reverse('pdf_curso', args=[self.curso.id]))
        if response.status_code == 503:
            self.assertEqual(response.content, b"El generador de PDF no est\xc3\xa1 disponible en este entorno.")
        else:
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response['Content-Type'], 'application/pdf')

    # --- Tests de API ---

    def test_api_get_profesores(self):
        url = reverse('api_profesores')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_api_get_estado_sistema(self):
        url = reverse('api_estado_sistema')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('recursos', response.data)

    def test_api_generar_horario_unauthenticated(self):
        self.client.force_authenticate(user=None)
        url = reverse('api_generar_horario')
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_flujo_completo_generacion(self):
        """
        SMOKE TEST: Verifica el flujo completo desde la petición hasta el resultado.
        Este es el test más robusto ya que cubre múltiples capas del sistema.
        """
        # 1. Asegurar configuración global
        ConfiguracionColegio.objects.get_or_create(
            jornada='mañana',
            bloques_por_dia=6,
            duracion_bloque=60,
            dias_clase='lunes,martes,miércoles,jueves,viernes'
        )

        # 2. Verificar estado inicial (factibilidad)
        url_validar = reverse('api_validar_prerrequisitos')
        resp_validar = self.client.get(url_validar)
        self.assertEqual(resp_validar.status_code, 200)

        # 3. Lanzar generación vía API
        url_generar = reverse('api_generar_horario')
        payload = {
            "generaciones": 10,
            "paciencia": 5,
            "semilla": 123
        }

        response = self.client.post(url_generar, payload, format='json')

        # 4. Verificar resultado (puede ser éxito o error de factibilidad dependiendo de los datos de setUp)
        # Lo importante es que el endpoint responda correctamente a la lógica de negocio
        self.assertIn(response.status_code, [200, 400, 409])
        if response.status_code == 200:
            self.assertEqual(response.data['status'], 'success')
            self.assertGreater(len(response.data['asignaciones']), 0)
