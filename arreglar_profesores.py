#!/usr/bin/env python
"""
Script para arreglar la asignación de profesores a materias.
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

def arreglar_profesores():
    """Asegura que todas las materias tengan profesores asignados."""
    print("🔧 Arreglando asignación de profesores...")
    
    # Obtener todas las materias
    materias = list(Materia.objects.all())
    profesores = list(Profesor.objects.all())
    
    if not materias:
        print("❌ No hay materias en la base de datos")
        return
    
    if not profesores:
        print("❌ No hay profesores en la base de datos")
        return
    
    print(f"📚 Materias encontradas: {len(materias)}")
    print(f"👨‍🏫 Profesores encontrados: {len(profesores)}")
    
    # Verificar qué materias no tienen profesores
    materias_con_profesor = set(MateriaProfesor.objects.values_list('materia_id', flat=True))
    materias_sin_profesor = [m for m in materias if m.id not in materias_con_profesor]
    
    print(f"🔍 Materias sin profesor: {len(materias_sin_profesor)}")
    
    # Asignar profesores a materias que no los tienen
    for i, materia in enumerate(materias_sin_profesor):
        # Rotar entre profesores para distribuir la carga
        profesor = profesores[i % len(profesores)]
        
        # Crear la relación materia-profesor
        mp, created = MateriaProfesor.objects.get_or_create(
            profesor=profesor,
            materia=materia
        )
        
        if created:
            print(f"✅ Asignado {profesor.nombre} a {materia.nombre}")
        else:
            print(f"ℹ️ {profesor.nombre} ya estaba asignado a {materia.nombre}")
    
    # Verificar que todos los profesores tengan disponibilidad
    print("\n🔍 Verificando disponibilidad de profesores...")
    
    dias = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes']
    profesores_sin_disponibilidad = []
    
    for profesor in profesores:
        disponibilidad = DisponibilidadProfesor.objects.filter(profesor=profesor)
        if disponibilidad.count() == 0:
            profesores_sin_disponibilidad.append(profesor)
    
    print(f"👨‍🏫 Profesores sin disponibilidad: {len(profesores_sin_disponibilidad)}")
    
    # Crear disponibilidad para profesores que no la tienen
    for profesor in profesores_sin_disponibilidad:
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
                print(f"✅ Creada disponibilidad para {profesor.nombre} en {dia}")
    
    # Verificar estado final
    print("\n📊 Estado final:")
    print(f"   - Materias: {Materia.objects.count()}")
    print(f"   - Profesores: {Profesor.objects.count()}")
    print(f"   - Relaciones materia-profesor: {MateriaProfesor.objects.count()}")
    print(f"   - Disponibilidad: {DisponibilidadProfesor.objects.count()}")
    
    # Verificar que no haya materias sin profesor
    materias_con_profesor_final = set(MateriaProfesor.objects.values_list('materia_id', flat=True))
    materias_sin_profesor_final = [m for m in materias if m.id not in materias_con_profesor_final]
    
    if len(materias_sin_profesor_final) == 0:
        print("✅ Todas las materias tienen profesores asignados")
    else:
        print(f"❌ Aún hay {len(materias_sin_profesor_final)} materias sin profesor:")
        for materia in materias_sin_profesor_final:
            print(f"   - {materia.nombre}")
    
    # Verificar que no haya profesores sin disponibilidad
    profesores_sin_disponibilidad_final = []
    for profesor in profesores:
        disponibilidad = DisponibilidadProfesor.objects.filter(profesor=profesor)
        if disponibilidad.count() == 0:
            profesores_sin_disponibilidad_final.append(profesor)
    
    if len(profesores_sin_disponibilidad_final) == 0:
        print("✅ Todos los profesores tienen disponibilidad")
    else:
        print(f"❌ Aún hay {len(profesores_sin_disponibilidad_final)} profesores sin disponibilidad:")
        for profesor in profesores_sin_disponibilidad_final:
            print(f"   - {profesor.nombre}")
    
    print("\n🎯 Sistema listo para generar horarios!")

if __name__ == '__main__':
    arreglar_profesores() 