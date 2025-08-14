#!/usr/bin/env python3
"""
TEST DE VERIFICACIÓN FINAL - ANÁLISIS DETALLADO
================================================

Analiza exactamente por qué no se rellenan los huecos:
1. Cuántos bloques requiere cada curso
2. Cuántos bloques se asignan realmente
3. Dónde están los huecos exactamente
4. Por qué no se rellenan automáticamente

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

from horarios.models import Horario, Curso, Materia, MateriaGrado

def analisis_detallado_huecos():
    print("🔍 ANÁLISIS DETALLADO DE HUECOS")
    print("=" * 60)
    
    try:
        # Análisis 1: Bloques requeridos vs disponibles
        print("\n📊 ANÁLISIS 1: BLOQUES REQUERIDOS VS DISPONIBLES")
        print("-" * 60)
        
        cursos = Curso.objects.all().order_by('nombre')
        total_requerido = 0
        total_disponible = 0
        
        for curso in cursos:
            materias_grado = MateriaGrado.objects.filter(grado=curso.grado)
            bloques_requeridos = sum(mg.materia.bloques_por_semana for mg in materias_grado)
            bloques_disponibles = 5 * 6  # 5 días × 6 bloques
            
            total_requerido += bloques_requeridos
            total_disponible += bloques_disponibles
            
            print(f"  • {curso.nombre}: {bloques_requeridos}/{bloques_disponibles} bloques")
            print(f"    - Huecos: {bloques_disponibles - bloques_requeridos}")
            
            # Mostrar materias y sus bloques
            for mg in materias_grado:
                materia = mg.materia
                print(f"      - {materia.nombre}: {materia.bloques_por_semana} bloques")
        
        print(f"\n📈 RESUMEN TOTAL:")
        print(f"  • Bloques requeridos: {total_requerido}")
        print(f"  • Bloques disponibles: {total_disponible}")
        print(f"  • Huecos totales: {total_disponible - total_requerido}")
        
        # Análisis 2: Horarios actuales
        print("\n📅 ANÁLISIS 2: HORARIOS ACTUALES")
        print("-" * 60)
        
        horarios = Horario.objects.all()
        total_horarios = horarios.count()
        
        print(f"  • Total de horarios en BD: {total_horarios}")
        print(f"  • Diferencia con requeridos: {total_horarios - total_requerido}")
        print(f"  • Diferencia con disponibles: {total_horarios - total_disponible}")
        
        # Análisis 3: Huecos por curso y día
        print("\n🔍 ANÁLISIS 3: HUECOS POR CURSO Y DÍA")
        print("-" * 60)
        
        for curso in cursos:
            print(f"\n  📚 {curso.nombre}:")
            horarios_curso = horarios.filter(curso=curso)
            
            for dia in ['lunes', 'martes', 'miércoles', 'jueves', 'viernes']:
                bloques_dia = horarios_curso.filter(dia=dia).count()
                huecos_dia = 6 - bloques_dia
                
                if huecos_dia > 0:
                    print(f"    ❌ {dia}: {bloques_dia}/6 bloques ({huecos_dia} huecos)")
                    
                    # Mostrar qué bloques están ocupados
                    bloques_ocupados = set(horarios_curso.filter(dia=dia).values_list('bloque', flat=True))
                    bloques_faltantes = set(range(1, 7)) - bloques_ocupados
                    print(f"      - Bloques ocupados: {sorted(bloques_ocupados)}")
                    print(f"      - Bloques faltantes: {sorted(bloques_faltantes)}")
                else:
                    print(f"    ✅ {dia}: {bloques_dia}/6 bloques")
        
        # Análisis 4: Por qué no se rellenan los huecos
        print("\n🤔 ANÁLISIS 4: ¿POR QUÉ NO SE RELLENAN LOS HUECOS?")
        print("-" * 60)
        
        print("  El problema es que el algoritmo:")
        print("  1. ✅ Asigna TODOS los bloques requeridos por cada materia")
        print("  2. ❌ NO rellena los huecos restantes automáticamente")
        print("  3. ❌ Considera que 'está completo' cuando cumple bloques_por_semana")
        print("  4. ❌ No entiende que debe rellenar TODOS los 360 bloques disponibles")
        
        print(f"\n  Solución necesaria:")
        print(f"  - Rellenar {total_disponible - total_requerido} huecos con materias del curso")
        print(f"  - Usar materias que no hayan alcanzado su máximo de bloques")
        print(f"  - Distribuir los huecos de manera equilibrada entre cursos")
        
        return True
        
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    analisis_detallado_huecos() 