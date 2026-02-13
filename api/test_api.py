from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth.models import User
from horarios.models import Profesor, Materia, Curso, Grado, Aula, BloqueHorario, DisponibilidadProfesor

class APITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(username='admin', password='password', email='admin@test.com')
        self.client.force_authenticate(user=self.user)

        # Datos básicos
        self.grado = Grado.objects.create(nombre='PRIMERO')
        self.profesor = Profesor.objects.create(nombre='Juan Pérez')
        self.materia = Materia.objects.create(nombre='Matemáticas', bloques_por_semana=4)
        self.curso = Curso.objects.create(nombre='1A', grado=self.grado)
        self.aula = Aula.objects.create(nombre='AULA-101', capacidad=40)

        from datetime import time
        self.bloque = BloqueHorario.objects.create(
            numero=1, hora_inicio=time(8, 0), hora_fin=time(9, 0), tipo='clase'
        )

        DisponibilidadProfesor.objects.create(
            profesor=self.profesor, dia='lunes', bloque_inicio=1, bloque_fin=6
        )

    def test_get_profesores(self):
        url = reverse('api_profesores')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['nombre'], 'Juan Pérez')

    def test_get_estado_sistema(self):
        url = reverse('api_estado_sistema')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('recursos', response.data)
        self.assertEqual(response.data['recursos']['profesores'], 1)

    def test_validar_prerrequisitos(self):
        url = reverse('api_validar_prerrequisitos')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('es_factible', response.data)

    def test_generar_horario_unauthenticated(self):
        self.client.force_authenticate(user=None)
        url = reverse('api_generar_horario')
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
