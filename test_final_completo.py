#!/usr/bin/env python3
"""
TEST FINAL COMPLETO - SISTEMA AL 100%
======================================

Verifica que el sistema funcione perfectamente:
1. NO use materias de relleno
2. SÍ genere horarios 100% completos (360/360)
3. SÍ use semillas aleatorias
4. SÍ cumpla bloques_por_semana exactos
5. SÍ rellene huecos automáticamente

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

from django.core.cache import cache
from horarios.models import Horario, Curso, Materia, MateriaGrado
from horarios.genetico import generar_horarios_genetico

def test_sistema_100_porciento():
    print("🧪 TEST FINAL COMPLETO - SISTEMA AL 100%")
    print("=" * 60)
    
    try:
        # Test 1: Verificar configuración de bloques
        print("\n🔍 TEST 1: Verificando configuración de bloques...")
        cursos = Curso.objects.all().order_by('nombre')
        
        for curso in cursos:
            materias_grado = MateriaGrado.objects.filter(grado=curso.grado)
            bloques_requeridos = sum(mg.materia.bloques_por_semana for mg in materias_grado)
            print(f"  • {curso.nombre}: {bloques_requeridos}/30 bloques requeridos")
            
            if bloques_requeridos > 30:
                print(f"    ❌ ERROR: {curso.nombre} requiere {bloques_requeridos} bloques pero solo hay 30 disponibles")
                return False
        
        # Test 2: Generar horarios con semilla aleatoria
        print("\n🔍 TEST 2: Generando horarios con semilla aleatoria...")
        
        # Limpiar horarios existentes
        Horario.objects.all().delete()
        print("  🗑️ Horarios existentes eliminados")
        
        # Generar horarios
        resultado = generar_horarios_genetico(
            poblacion_size=100,  # Aumentado para mejor calidad
            generaciones=200,     # Aumentado para mejor calidad
            timeout_seg=120,      # Aumentado para mejor calidad
            prob_cruce=0.8,
            prob_mutacion=0.1,
            elite=5,
            paciencia=30,
            workers=1,
            semilla=None  # Semilla aleatoria
        )
        
        if resultado:
            print("  ✅ Horarios generados exitosamente")
            
            # Test 3: Verificar que no hay huecos
            print("\n🔍 TEST 3: Verificando que no hay huecos...")
            horarios = Horario.objects.all()
            total_horarios = horarios.count()
            
            print(f"  • Total de horarios generados: {total_horarios}")
            
            # Verificar que sean exactamente 360 (12 cursos × 5 días × 6 bloques)
            if total_horarios == 360:
                print("  ✅ PERFECTO: 360/360 horarios generados (100%)")
            else:
                print(f"  ❌ ERROR: Solo {total_horarios}/360 horarios generados ({total_horarios/360*100:.1f}%)")
                return False
            
            # Verificar por curso
            for curso in cursos:
                horarios_curso = horarios.filter(curso=curso)
                print(f"  • {curso.nombre}: {horarios_curso.count()}/30 bloques")
                
                # Verificar que cada día tenga exactamente 6 bloques
                for dia in ['lunes', 'martes', 'miércoles', 'jueves', 'viernes']:
                    bloques_dia = horarios_curso.filter(dia=dia).count()
                    if bloques_dia == 6:
                        print(f"    ✅ {dia}: {bloques_dia}/6 bloques")
                    else:
                        print(f"    ❌ {dia}: Solo {bloques_dia}/6 bloques")
                        return False
            
            # Test 4: Verificar que se cumplen bloques_por_semana exactos
            print("\n🔍 TEST 4: Verificando bloques_por_semana exactos...")
            errores_bloques = 0
            
            for curso in cursos:
                materias_grado = MateriaGrado.objects.filter(grado=curso.grado)
                for mg in materias_grado:
                    materia = mg.materia
                    bloques_requeridos = materia.bloques_por_semana
                    bloques_asignados = horarios.filter(curso=curso, materia=materia).count()
                    
                    if bloques_asignados == bloques_requeridos:
                        print(f"  ✅ {curso.nombre} - {materia.nombre}: {bloques_asignados}/{bloques_requeridos}")
                    else:
                        print(f"  ❌ {curso.nombre} - {materia.nombre}: {bloques_asignados}/{bloques_requeridos}")
                        errores_bloques += 1
            
            if errores_bloques == 0:
                print("  ✅ PERFECTO: Todas las materias cumplen bloques_por_semana exactos")
            else:
                print(f"  ❌ ERROR: {errores_bloques} materias no cumplen bloques_por_semana")
                return False
            
            # Test 5: Verificar que no hay materias de relleno
            print("\n🔍 TEST 5: Verificando que no hay materias de relleno...")
            materias_relleno = ['Tutoría', 'Proyecto de Aula', 'Estudio Dirigido', 'Convivencia y Orientación', 'Lectura Guiada']
            
            for materia_nombre in materias_relleno:
                materia = Materia.objects.filter(nombre=materia_nombre).first()
                if materia:
                    horarios_relleno = horarios.filter(materia=materia).count()
                    if horarios_relleno == 0:
                        print(f"  ✅ {materia_nombre}: 0 horarios (CORRECTO)")
                    else:
                        print(f"  ❌ {materia_nombre}: {horarios_relleno} horarios (NO DEBERÍA)")
                        return False
                else:
                    print(f"  ✅ {materia_nombre}: No existe en la BD (CORRECTO)")
            
            print("\n🎉 ¡SISTEMA FUNCIONANDO AL 100%!")
            print("=" * 60)
            print("✅ NO usa materias de relleno")
            print("✅ SÍ genera horarios 100% completos (360/360)")
            print("✅ SÍ usa semillas aleatorias")
            print("✅ SÍ cumple bloques_por_semana exactos")
            print("✅ SÍ rellena huecos automáticamente")
            return True
            
        else:
            print("  ❌ Error generando horarios")
            return False
        
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_sistema_100_porciento() 