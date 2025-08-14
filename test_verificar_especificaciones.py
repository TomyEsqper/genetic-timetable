#!/usr/bin/env python3
"""
TEST PARA VERIFICAR ESPECIFICACIONES REALES DE MATERIAS
=======================================================

Este script verifica:
1. Qué materias están realmente configuradas en la BD
2. Cuántos bloques requiere cada materia
3. Qué materias están asignadas a cada curso
4. Si hay inconsistencias en la configuración

Autor: Sistema de Verificación Automática
Fecha: 2025-08-14
"""

import os
import sys
from datetime import datetime

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'colegio.settings')
import django
django.setup()

from horarios.models import Horario, Curso, Materia, MateriaGrado, Profesor, Aula

def verificar_especificaciones_reales():
    print("🔍 VERIFICANDO ESPECIFICACIONES REALES DE MATERIAS")
    print("=" * 70)
    
    try:
        # 1. Verificar materias existentes
        print("\n📚 MATERIAS EN LA BASE DE DATOS:")
        print("-" * 40)
        materias = Materia.objects.all().order_by('nombre')
        for materia in materias:
            print(f"  • {materia.nombre} (ID: {materia.id})")
        
        # 2. Verificar cursos existentes
        print("\n🏫 CURSOS EN LA BASE DE DATOS:")
        print("-" * 40)
        cursos = Curso.objects.all().order_by('nombre')
        for curso in cursos:
            print(f"  • {curso.nombre} - Grado: {curso.grado.nombre}")
        
        # 3. Verificar MateriaGrado (asignación de materias a grados)
        print("\n🔗 ASIGNACIÓN DE MATERIAS A GRADOS (MateriaGrado):")
        print("-" * 40)
        materia_grados = MateriaGrado.objects.all().order_by('grado__nombre', 'materia__nombre')
        for mg in materia_grados:
            print(f"  • Grado {mg.grado.nombre}: {mg.materia.nombre}")
        
        # 4. Verificar bloques por materia
        print("\n⏰ BLOQUES REQUERIDOS POR MATERIA:")
        print("-" * 40)
        for materia in materias:
            # Buscar en MateriaGrado para ver si está asignada a algún grado
            asignada = MateriaGrado.objects.filter(materia=materia).exists()
            bloques = materia.bloques_por_semana
            if asignada:
                print(f"  • {materia.nombre}: {bloques} bloques/semana - Asignada a grados")
            else:
                print(f"  • {materia.nombre}: {bloques} bloques/semana - NO asignada a ningún grado")
        
        # 4.1 Verificar si hay materias con bloques_por_semana = 0
        print("\n⚠️ MATERIAS CON BLOQUES_POR_SEMANA = 0:")
        print("-" * 40)
        materias_sin_bloques = [m for m in materias if m.bloques_por_semana == 0]
        if materias_sin_bloques:
            for materia in materias_sin_bloques:
                print(f"  • {materia.nombre} (ID: {materia.id})")
            print(f"  Total: {len(materias_sin_bloques)} materias sin bloques configurados")
        else:
            print("  ✅ Todas las materias tienen bloques configurados")
        
        # 5. Verificar profesores
        print("\n👨‍🏫 PROFESORES EN LA BASE DE DATOS:")
        print("-" * 40)
        profesores = Profesor.objects.all().order_by('nombre')
        for prof in profesores:
            print(f"  • {prof.nombre} (ID: {prof.id})")
        
        # 6. Verificar aulas
        print("\n🏠 AULAS EN LA BASE DE DATOS:")
        print("-" * 40)
        aulas = Aula.objects.all().order_by('nombre')
        for aula in aulas:
            print(f"  • {aula.nombre} - Capacidad: {aula.capacidad}")
        
        # 7. Verificar horarios existentes
        print("\n📅 HORARIOS EXISTENTES:")
        print("-" * 40)
        horarios = Horario.objects.all()
        print(f"  • Total de horarios: {horarios.count()}")
        
        if horarios.exists():
            # Agrupar por curso
            horarios_por_curso = {}
            for h in horarios:
                curso_nombre = h.curso.nombre
                if curso_nombre not in horarios_por_curso:
                    horarios_por_curso[curso_nombre] = 0
                horarios_por_curso[curso_nombre] += 1
            
            for curso_nombre, count in horarios_por_curso.items():
                print(f"    - {curso_nombre}: {count} bloques")
        
        print("\n✅ VERIFICACIÓN COMPLETADA")
        return True
        
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    verificar_especificaciones_reales() 