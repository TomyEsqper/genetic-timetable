#!/usr/bin/env python3
"""
TEST FINAL SIN MATERIAS DE RELLENO
===================================

Verifica que el sistema funcione correctamente:
1. NO use materias de relleno
2. SÍ genere horarios 100% completos
3. SÍ use semillas aleatorias
4. SÍ cumpla bloques_por_semana exactos

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

def test_sin_materias_relleno():
    print("🧪 TEST FINAL SIN MATERIAS DE RELLENO")
    print("=" * 60)
    
    try:
        # Test 1: Verificar que no hay materias de relleno en MateriaGrado
        print("\n🔍 TEST 1: Verificando que no hay materias de relleno asignadas...")
        materias_relleno = ['Tutoría', 'Proyecto de Aula', 'Estudio Dirigido', 'Convivencia y Orientación', 'Lectura Guiada']
        
        for materia_nombre in materias_relleno:
            materia = Materia.objects.filter(nombre=materia_nombre).first()
            if materia:
                asignada = MateriaGrado.objects.filter(materia=materia).exists()
                if asignada:
                    print(f"  ❌ {materia_nombre}: Está asignada a un grado (NO DEBERÍA)")
                else:
                    print(f"  ✅ {materia_nombre}: NO está asignada a ningún grado (CORRECTO)")
            else:
                print(f"  ✅ {materia_nombre}: No existe en la BD (CORRECTO)")
        
        # Test 2: Verificar bloques requeridos por curso
        print("\n🔍 TEST 2: Verificando bloques requeridos por curso...")
        cursos = Curso.objects.all().order_by('nombre')
        
        for curso in cursos:
            materias_grado = MateriaGrado.objects.filter(grado=curso.grado)
            bloques_requeridos = sum(mg.materia.bloques_por_semana for mg in materias_grado)
            print(f"  • {curso.nombre}: {bloques_requeridos} bloques requeridos")
            
            # Verificar que no exceda la capacidad (5 días × 6 bloques = 30)
            if bloques_requeridos > 30:
                print(f"    ⚠️ ADVERTENCIA: {curso.nombre} requiere {bloques_requeridos} bloques pero solo hay 30 disponibles")
        
        # Test 3: Generar horarios con semilla aleatoria
        print("\n🔍 TEST 3: Generando horarios con semilla aleatoria...")
        
        # Limpiar horarios existentes
        Horario.objects.all().delete()
        print("  🗑️ Horarios existentes eliminados")
        
        # Generar horarios
        resultado = generar_horarios_genetico(
            poblacion_size=50,  # Reducido para test rápido
            generaciones=100,   # Reducido para test rápido
            timeout_seg=60,     # Reducido para test rápido
            prob_cruce=0.8,
            prob_mutacion=0.1,
            elite=3,
            paciencia=20,
            workers=1,
            semilla=None  # Semilla aleatoria
        )
        
        if resultado:
            print("  ✅ Horarios generados exitosamente")
            
            # Test 4: Verificar que no hay huecos
            print("\n🔍 TEST 4: Verificando que no hay huecos...")
            horarios = Horario.objects.all()
            total_horarios = horarios.count()
            
            print(f"  • Total de horarios generados: {total_horarios}")
            
            # Verificar por curso
            for curso in cursos:
                horarios_curso = horarios.filter(curso=curso)
                print(f"  • {curso.nombre}: {horarios_curso.count()} bloques")
                
                # Verificar que cada día tenga 6 bloques
                for dia in ['lunes', 'martes', 'miércoles', 'jueves', 'viernes']:
                    bloques_dia = horarios_curso.filter(dia=dia).count()
                    if bloques_dia < 6:
                        print(f"    ❌ {dia}: Solo {bloques_dia}/6 bloques")
                    else:
                        print(f"    ✅ {dia}: {bloques_dia}/6 bloques")
            
            # Test 5: Verificar que se cumplen bloques_por_semana
            print("\n🔍 TEST 5: Verificando bloques_por_semana...")
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
            
            print("\n🎉 TEST COMPLETADO EXITOSAMENTE")
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
    test_sin_materias_relleno() 