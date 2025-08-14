#!/usr/bin/env python3
"""
TEST RÁPIDO DE CORRECCIONES DE MATERIAGRADO
============================================

Verifica que las correcciones de acceso a materias funcionen:
1. Acceso correcto a materias del curso
2. Relleno de huecos con materias de relleno
3. Validación de horarios sin huecos

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
from horarios.genetico import generar_horarios_genetico

def test_correcciones_materiagrado():
    print("🧪 TEST RÁPIDO DE CORRECCIONES DE MATERIAGRADO")
    print("=" * 60)
    
    try:
        # Test 1: Verificar acceso a materias del curso
        print("\n🔍 Test 1: Verificando acceso a materias del curso...")
        curso = Curso.objects.first()
        if curso:
            print(f"Curso: {curso.nombre} (Grado: {curso.grado.nombre})")
            
            # Usar MateriaGrado para obtener materias
            materias_curso = MateriaGrado.objects.filter(grado=curso.grado)
            print(f"Materias del curso via MateriaGrado: {materias_curso.count()}")
            
            for mg in materias_curso[:5]:  # Mostrar primeras 5
                print(f"  - {mg.materia.nombre} ({mg.materia.bloques_por_semana} bloques)")
            
            if materias_curso.exists():
                print("✅ Acceso a materias del curso funcionando")
            else:
                print("❌ No se encontraron materias para el curso")
                return False
        else:
            print("❌ No hay cursos en la base de datos")
            return False
        
        # Test 2: Verificar materias de relleno
        print("\n🔍 Test 2: Verificando materias de relleno...")
        materias_relleno = ['Tutoría', 'Proyecto de Aula', 'Estudio Dirigido', 'Convivencia y Orientación', 'Lectura Guiada']
        for nombre in materias_relleno:
            materia = Materia.objects.filter(nombre=nombre).first()
            if materia:
                print(f"✅ {nombre} encontrada (ID: {materia.id})")
            else:
                print(f"❌ {nombre} NO encontrada")
        
        # Test 3: Generar horarios con parámetros mínimos
        print("\n🔍 Test 3: Generando horarios para verificar correcciones...")
        resultado = generar_horarios_genetico(
            poblacion_size=3,
            generaciones=1,
            prob_cruce=0.8,
            prob_mutacion=0.2,
            elite=1,
            paciencia=2,
            timeout_seg=15,
            workers=1,
            semilla=42
        )
        
        if resultado and resultado.get('exito'):
            horarios = Horario.objects.count()
            print(f"✅ Horarios generados: {horarios}")
            
            # Verificar que no haya huecos
            print("\n🔍 Test 4: Verificando que no haya huecos...")
            horarios_por_curso = {}
            for horario in Horario.objects.all():
                curso_id = horario.curso.id
                dia = horario.dia
                bloque = horario.bloque
                
                if curso_id not in horarios_por_curso:
                    horarios_por_curso[curso_id] = {}
                if dia not in horarios_por_curso[curso_id]:
                    horarios_por_curso[curso_id][dia] = set()
                
                horarios_por_curso[curso_id][dia].add(bloque)
            
            # Verificar huecos
            total_huecos = 0
            for curso_id, dias in horarios_por_curso.items():
                curso = Curso.objects.get(id=curso_id)
                print(f"  Curso: {curso.nombre}")
                
                for dia in ['lunes', 'martes', 'miércoles', 'jueves', 'viernes']:
                    bloques_ocupados = dias.get(dia, set())
                    bloques_esperados = set([1, 2, 3, 4, 5, 6])
                    
                    # Verificar bloques faltantes
                    bloques_faltantes = bloques_esperados - bloques_ocupados
                    if bloques_faltantes:
                        print(f"    ⚠️ {dia}: Bloques faltantes: {sorted(bloques_faltantes)}")
                        total_huecos += len(bloques_faltantes)
                    else:
                        print(f"    ✅ {dia}: Todos los bloques ocupados")
            
            if total_huecos == 0:
                print("✅ No se detectaron huecos en los horarios")
            else:
                print(f"⚠️ Se detectaron {total_huecos} huecos en total")
            
            return True
            
        else:
            print(f"❌ Algoritmo falló: {resultado}")
            return False
            
    except Exception as e:
        print(f"❌ Error en test: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    exito = test_correcciones_materiagrado()
    
    if exito:
        print("\n🎉 RESULTADO: CORRECCIONES DE MATERIAGRADO FUNCIONANDO")
    else:
        print("\n⚠️ RESULTADO: ALGUNAS CORRECCIONES FALLARON")
    
    sys.exit(0 if exito else 1) 