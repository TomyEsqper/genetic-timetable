#!/usr/bin/env python
"""
Script para cargar datos de ejemplo en el sistema de generación de horarios.
"""

import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'colegio.settings')
django.setup()

from horarios.models import (
    Grado, Curso, Materia, Profesor, Aula, BloqueHorario,
    MateriaGrado, MateriaProfesor, DisponibilidadProfesor
)

def cargar_datos_ejemplo():
    """Carga datos de ejemplo para probar el sistema."""
    print("Cargando datos de ejemplo...")
    
    # Crear grados
    print("1. Creando grados...")
    grado1, created = Grado.objects.get_or_create(nombre='Primero')
    grado2, created = Grado.objects.get_or_create(nombre='Segundo')
    print(f"   - Grados creados: {Grado.objects.count()}")
    
    # Crear aulas
    print("2. Creando aulas...")
    aulas = []
    for i in range(1, 6):
        aula, created = Aula.objects.get_or_create(
            nombre=f'Aula {i}01',
            defaults={'tipo': 'comun', 'capacidad': 40}
        )
        aulas.append(aula)
    print(f"   - Aulas creadas: {Aula.objects.count()}")
    
    # Crear cursos
    print("3. Creando cursos...")
    cursos = []
    for i, grado in enumerate([grado1, grado2]):
        for j in range(1, 4):  # 3 cursos por grado
            aula_index = i * 3 + j - 1
            if aula_index < len(aulas):
                aula = aulas[aula_index]
            else:
                aula = aulas[0]  # Usar la primera aula si no hay suficientes
                
            curso, created = Curso.objects.get_or_create(
                nombre=f'{i+1}{chr(64+j)}',  # 1A, 1B, 1C, 2A, 2B, 2C
                defaults={
                    'grado': grado,
                    'aula_fija': aula
                }
            )
            cursos.append(curso)
    print(f"   - Cursos creados: {Curso.objects.count()}")
    
    # Crear materias
    print("4. Creando materias...")
    materias_data = [
        ('Matemáticas', 4),
        ('Lenguaje', 3),
        ('Ciencias', 3),
        ('Historia', 2),
        ('Educación Física', 2),
        ('Arte', 2),
        ('Tecnología', 2),
    ]
    
    materias = []
    for nombre, bloques in materias_data:
        materia, created = Materia.objects.get_or_create(
            nombre=nombre,
            defaults={'bloques_por_semana': bloques}
        )
        materias.append(materia)
    print(f"   - Materias creadas: {Materia.objects.count()}")
    
    # Crear profesores
    print("5. Creando profesores...")
    profesores_data = [
        'Prof. García',
        'Prof. López',
        'Prof. Martínez',
        'Prof. Rodríguez',
        'Prof. González',
        'Prof. Pérez',
        'Prof. Sánchez',
    ]
    
    profesores = []
    for nombre in profesores_data:
        profesor, created = Profesor.objects.get_or_create(nombre=nombre)
        profesores.append(profesor)
    print(f"   - Profesores creados: {Profesor.objects.count()}")
    
    # Crear bloques horarios
    print("6. Creando bloques horarios...")
    bloques_data = [
        (1, '08:00', '09:00'),
        (2, '09:00', '10:00'),
        (3, '10:00', '11:00'),
        (4, '11:00', '12:00'),
        (5, '14:00', '15:00'),
        (6, '15:00', '16:00'),
    ]
    
    for numero, inicio, fin in bloques_data:
        BloqueHorario.objects.get_or_create(
            numero=numero,
            defaults={
                'hora_inicio': inicio,
                'hora_fin': fin,
                'tipo': 'clase'
            }
        )
    print(f"   - Bloques creados: {BloqueHorario.objects.count()}")
    
    # Asignar materias a grados
    print("7. Asignando materias a grados...")
    for grado in [grado1, grado2]:
        for materia in materias:
            MateriaGrado.objects.get_or_create(
                grado=grado,
                materia=materia
            )
    print(f"   - Relaciones materia-grado creadas: {MateriaGrado.objects.count()}")
    
    # Asignar profesores a materias
    print("8. Asignando profesores a materias...")
    for i, materia in enumerate(materias):
        profesor = profesores[i % len(profesores)]
        MateriaProfesor.objects.get_or_create(
            profesor=profesor,
            materia=materia
        )
    print(f"   - Relaciones materia-profesor creadas: {MateriaProfesor.objects.count()}")
    
    # Crear disponibilidad de profesores
    print("9. Creando disponibilidad de profesores...")
    dias = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes']
    
    for profesor in profesores:
        for dia in dias:
            # Disponibilidad de 8:00 a 16:00 (bloques 1-6)
            DisponibilidadProfesor.objects.get_or_create(
                profesor=profesor,
                dia=dia,
                defaults={
                    'bloque_inicio': 1,
                    'bloque_fin': 6
                }
            )
    print(f"   - Disponibilidad creada: {DisponibilidadProfesor.objects.count()}")
    
    print("\n✅ Datos de ejemplo cargados exitosamente!")
    print("\nResumen:")
    print(f"   - Grados: {Grado.objects.count()}")
    print(f"   - Cursos: {Curso.objects.count()}")
    print(f"   - Materias: {Materia.objects.count()}")
    print(f"   - Profesores: {Profesor.objects.count()}")
    print(f"   - Aulas: {Aula.objects.count()}")
    print(f"   - Bloques: {BloqueHorario.objects.count()}")
    print(f"   - Relaciones materia-grado: {MateriaGrado.objects.count()}")
    print(f"   - Relaciones materia-profesor: {MateriaProfesor.objects.count()}")
    print(f"   - Disponibilidad: {DisponibilidadProfesor.objects.count()}")
    
    print("\n🎯 Ahora puedes:")
    print("   1. Ejecutar: python manage.py runserver")
    print("   2. Ir a: http://localhost:8000/horarios/")
    print("   3. Generar horarios con el algoritmo genético robusto")

if __name__ == '__main__':
    cargar_datos_ejemplo() 