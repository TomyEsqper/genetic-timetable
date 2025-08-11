#!/usr/bin/env python
"""
Script para limpiar y verificar completamente el sistema.
"""

import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'colegio.settings')
django.setup()

from horarios.models import (
    Grado, Curso, Materia, Profesor, Aula, BloqueHorario,
    MateriaGrado, MateriaProfesor, DisponibilidadProfesor, Horario
)

def limpiar_y_verificar():
    """Limpia y verifica completamente el sistema."""
    print("🧹 Limpiando y verificando el sistema...")
    
    # 1. Limpiar horarios existentes
    print("1. Limpiando horarios existentes...")
    horarios_eliminados = Horario.objects.count()
    Horario.objects.all().delete()
    print(f"   ✅ Eliminados {horarios_eliminados} horarios")
    
    # 2. Verificar y arreglar relaciones materia-profesor
    print("2. Verificando relaciones materia-profesor...")
    
    # Obtener todas las materias y profesores
    materias = list(Materia.objects.all())
    profesores = list(Profesor.objects.all())
    
    if not materias:
        print("   ❌ No hay materias en la base de datos")
        return
    
    if not profesores:
        print("   ❌ No hay profesores en la base de datos")
        return
    
    # Eliminar todas las relaciones existentes
    MateriaProfesor.objects.all().delete()
    print("   🗑️ Relaciones materia-profesor eliminadas")
    
    # Crear nuevas relaciones asegurando que cada materia tenga al menos un profesor
    for i, materia in enumerate(materias):
        # Rotar entre profesores para distribuir la carga
        profesor = profesores[i % len(profesores)]
        
        # Crear la relación materia-profesor
        mp, created = MateriaProfesor.objects.get_or_create(
            profesor=profesor,
            materia=materia
        )
        
        if created:
            print(f"   ✅ Asignado {profesor.nombre} a {materia.nombre}")
    
    # 3. Verificar y arreglar disponibilidad de profesores
    print("3. Verificando disponibilidad de profesores...")
    
    # Eliminar disponibilidad existente
    DisponibilidadProfesor.objects.all().delete()
    print("   🗑️ Disponibilidad eliminada")
    
    # Crear disponibilidad completa para todos los profesores
    dias = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes']
    
    for profesor in profesores:
        for dia in dias:
            # Disponibilidad de 8:00 a 16:00 (bloques 1-6)
            disp, created = DisponibilidadProfesor.objects.get_or_create(
                profesor=profesor,
                dia=dia,
                defaults={
                    'bloque_inicio': 1,
                    'bloque_fin': 6
                }
            )
            
            if created:
                print(f"   ✅ Creada disponibilidad para {profesor.nombre} en {dia}")
    
    # 4. Verificar estado final
    print("4. Verificando estado final...")
    
    # Verificar materias sin profesor (lógica del dashboard)
    materias_sin_profesor = MateriaGrado.objects.exclude(
        materia__in=MateriaProfesor.objects.values_list('materia', flat=True)
    )
    
    print(f"   📊 Estado final:")
    print(f"      - Materias: {Materia.objects.count()}")
    print(f"      - Profesores: {Profesor.objects.count()}")
    print(f"      - Relaciones materia-profesor: {MateriaProfesor.objects.count()}")
    print(f"      - Disponibilidad: {DisponibilidadProfesor.objects.count()}")
    print(f"      - MateriaGrado: {MateriaGrado.objects.count()}")
    print(f"      - Materias sin profesor (dashboard): {materias_sin_profesor.count()}")
    
    if materias_sin_profesor.count() == 0:
        print("   ✅ Todas las materias tienen profesores asignados")
    else:
        print(f"   ❌ Aún hay {materias_sin_profesor.count()} materias sin profesor")
        for mg in materias_sin_profesor[:5]:
            print(f"      - {mg.grado.nombre} → {mg.materia.nombre}")
    
    # 5. Verificar que no haya profesores sin disponibilidad
    profesores_sin_disponibilidad = []
    for profesor in profesores:
        disponibilidad = DisponibilidadProfesor.objects.filter(profesor=profesor)
        if disponibilidad.count() == 0:
            profesores_sin_disponibilidad.append(profesor)
    
    if len(profesores_sin_disponibilidad) == 0:
        print("   ✅ Todos los profesores tienen disponibilidad")
    else:
        print(f"   ❌ Aún hay {len(profesores_sin_disponibilidad)} profesores sin disponibilidad")
        for profesor in profesores_sin_disponibilidad[:5]:
            print(f"      - {profesor.nombre}")
    
    # 6. Verificar bloques disponibles
    bloques_disponibles = list(BloqueHorario.objects.filter(tipo='clase').order_by('numero').values_list('numero', flat=True))
    print(f"   📅 Bloques disponibles: {len(bloques_disponibles)} ({bloques_disponibles})")
    
    if len(bloques_disponibles) == 0:
        print("   ❌ No hay bloques de tipo 'clase' configurados")
    else:
        print("   ✅ Bloques de tipo 'clase' configurados correctamente")
    
    print("\n🎯 Sistema limpio y verificado!")
    print("🌐 Ahora puedes acceder a http://localhost:8000/horarios/")
    print("📋 El dashboard debería mostrar '✅ Todas las materias están cubiertas'")

if __name__ == '__main__':
    limpiar_y_verificar() 