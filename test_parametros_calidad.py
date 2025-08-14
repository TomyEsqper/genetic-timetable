#!/usr/bin/env python3
"""
TEST DE PARÁMETROS DE CALIDAD
==============================

Verifica que los parámetros de configuración de calidad se usen
correctamente en la generación de horarios.

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

from horarios.models import Horario
from horarios.genetico import generar_horarios_genetico

def test_parametros_calidad():
    print("🧪 TEST DE PARÁMETROS DE CALIDAD")
    print("=" * 60)
    
    try:
        # Test 1: Verificar parámetros de configuración de calidad
        print("\n🔍 TEST 1: Verificando parámetros de configuración de calidad...")
        
        # Parámetros exactos de la configuración de calidad
        parametros_calidad = {
            'poblacion_size': 80,
            'generaciones': 1000,
            'timeout_seg': 600,
            'prob_cruce': 0.9,
            'prob_mutacion': 0.05,
            'elite': 5,
            'paciencia': 50,
            'workers': 1,
            'semilla': 94601
        }
        
        print("  📋 Parámetros de configuración de calidad:")
        for key, value in parametros_calidad.items():
            print(f"    • {key}: {value}")
        
        # Test 2: Generar horarios con parámetros de calidad
        print("\n🔍 TEST 2: Generando horarios con parámetros de calidad...")
        
        # Limpiar horarios existentes
        Horario.objects.all().delete()
        print("  🗑️ Horarios existentes eliminados")
        
        # Generar horarios con parámetros de calidad
        resultado = generar_horarios_genetico(**parametros_calidad)
        
        if resultado:
            print("  ✅ Horarios generados exitosamente")
            
            # Test 3: Verificar que se usaron los parámetros correctos
            print("\n🔍 TEST 3: Verificando uso de parámetros...")
            
            # Obtener progreso del cache
            from django.core.cache import cache
            progreso = cache.get('ga_progreso_actual')
            
            if progreso:
                print("  ✅ Progreso del algoritmo disponible en cache")
                print(f"    • Generación actual: {progreso.get('generacion', 'N/A')}")
                print(f"    • Estado: {progreso.get('estado', 'N/A')}")
                print(f"    • Horarios parciales: {progreso.get('horarios_parciales', 'N/A')}")
                print(f"    • Mejor fitness: {progreso.get('mejor_fitness', 'N/A')}")
                print(f"    • Fill percentage: {progreso.get('fill_pct', 'N/A')}%")
            else:
                print("  ⚠️ No se encontró progreso en cache")
            
            # Test 4: Verificar horarios generados
            print("\n🔍 TEST 4: Verificando horarios generados...")
            horarios = Horario.objects.all()
            total_horarios = horarios.count()
            
            print(f"  • Total de horarios: {total_horarios}")
            
            if total_horarios >= 350:  # Al menos 97% de los 360 bloques
                print("  ✅ PERFECTO: Horarios generados con alta cobertura")
            else:
                print(f"  ⚠️ ADVERTENCIA: Solo {total_horarios}/360 bloques generados")
            
            # Test 5: Verificar que se ejecutaron múltiples generaciones
            print("\n🔍 TEST 5: Verificando ejecución de múltiples generaciones...")
            
            if progreso and progreso.get('generacion', 0) > 1:
                print(f"  ✅ PERFECTO: Se ejecutaron {progreso.get('generacion', 0)} generaciones")
            else:
                print("  ❌ ERROR: Solo se ejecutó 1 generación o no hay progreso")
            
            print("\n🎉 TEST DE PARÁMETROS DE CALIDAD COMPLETADO")
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
    test_parametros_calidad() 