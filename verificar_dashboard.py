#!/usr/bin/env python
"""
Script para verificar los datos del dashboard.
"""

import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'colegio.settings')
django.setup()

from horarios.models import (
    Curso, Profesor, Aula, Horario, MateriaGrado, MateriaProfesor, 
    DisponibilidadProfesor, BloqueHorario, Materia
)

def verificar_dashboard():
    """Verifica los datos que se pasan al dashboard."""
    print("🔍 Verificando datos del dashboard...")
    
    # Datos básicos
    total_cursos = Curso.objects.count()
    total_profesores = Profesor.objects.count()
    total_horarios = Horario.objects.count()
    
    print(f"📊 Datos básicos:")
    print(f"   - Cursos: {total_cursos}")
    print(f"   - Profesores: {total_profesores}")
    print(f"   - Horarios: {total_horarios}")
    
    # Verificar materias sin profesor (lógica del dashboard)
    print(f"\n🔍 Verificando materias sin profesor...")
    
    # Lógica exacta del dashboard
    materias_sin_profesor = MateriaGrado.objects.exclude(
        materia__in=MateriaProfesor.objects.values_list('materia', flat=True)
    )
    
    print(f"   - MateriaGrado total: {MateriaGrado.objects.count()}")
    print(f"   - MateriaProfesor total: {MateriaProfesor.objects.count()}")
    print(f"   - Materias sin profesor (dashboard): {materias_sin_profesor.count()}")
    
    if materias_sin_profesor.count() > 0:
        print(f"   - Lista de materias sin profesor:")
        for mg in materias_sin_profesor[:10]:  # Mostrar solo las primeras 10
            print(f"     * {mg.grado.nombre} → {mg.materia.nombre}")
    else:
        print(f"   ✅ No hay materias sin profesor")
    
    # Verificar bloques disponibles
    bloques_disponibles = list(BloqueHorario.objects.filter(tipo='clase').order_by('numero').values_list('numero', flat=True))
    print(f"\n📅 Bloques disponibles:")
    print(f"   - Bloques tipo 'clase': {len(bloques_disponibles)}")
    print(f"   - Lista: {bloques_disponibles}")
    
    # Verificar horarios por curso
    horarios_por_curso = {}
    for curso in Curso.objects.all():
        horarios = Horario.objects.filter(curso=curso).select_related('materia', 'profesor')
        horarios_por_curso[curso] = horarios
    
    print(f"\n📋 Horarios por curso:")
    print(f"   - Cursos con horarios: {len([c for c, h in horarios_por_curso.items() if h.count() > 0])}")
    print(f"   - Cursos sin horarios: {len([c for c, h in horarios_por_curso.items() if h.count() == 0])}")
    
    # Verificar disponibilidad de profesores
    print(f"\n👨‍🏫 Disponibilidad de profesores:")
    profesores_sin_disponibilidad = []
    for profesor in Profesor.objects.all():
        disponibilidad = DisponibilidadProfesor.objects.filter(profesor=profesor)
        if disponibilidad.count() == 0:
            profesores_sin_disponibilidad.append(profesor)
    
    print(f"   - Profesores sin disponibilidad: {len(profesores_sin_disponibilidad)}")
    if len(profesores_sin_disponibilidad) > 0:
        for profesor in profesores_sin_disponibilidad[:5]:
            print(f"     * {profesor.nombre}")
    
    # Verificar relaciones materia-profesor
    print(f"\n📚 Relaciones materia-profesor:")
    materias_con_profesor = set(MateriaProfesor.objects.values_list('materia_id', flat=True))
    materias_sin_profesor_directo = [m for m in Materia.objects.all() if m.id not in materias_con_profesor]
    
    print(f"   - Materias con profesor: {len(materias_con_profesor)}")
    print(f"   - Materias sin profesor (directo): {len(materias_sin_profesor_directo)}")
    
    if len(materias_sin_profesor_directo) > 0:
        for materia in materias_sin_profesor_directo:
            print(f"     * {materia.nombre}")
    
    print(f"\n✅ Verificación completada!")

if __name__ == '__main__':
    verificar_dashboard() 