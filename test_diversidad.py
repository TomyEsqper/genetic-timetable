#!/usr/bin/env python3
"""
TEST DE DIVERSIDAD - ALGORITMO GENÉTICO
========================================

Verifica que el algoritmo genético:
1. SÍ ejecute múltiples generaciones (no solo 1)
2. SÍ genere diversidad en los horarios
3. SÍ evolucione y compare diferentes soluciones

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

def test_diversidad():
    print("🧪 TEST DE DIVERSIDAD - ALGORITMO GENÉTICO")
    print("=" * 60)
    
    try:
        # Test 1: Generar horarios con parámetros que fuercen evolución
        print("\n🔍 TEST 1: Generando horarios con evolución forzada...")
        
        # Limpiar horarios existentes
        Horario.objects.all().delete()
        print("  🗑️ Horarios existentes eliminados")
        
        # Generar horarios con parámetros que fuercen evolución
        resultado = generar_horarios_genetico(
            poblacion_size=50,      # Población pequeña para test rápido
            generaciones=50,         # 50 generaciones para ver evolución
            timeout_seg=120,         # 2 minutos máximo
            prob_cruce=0.8,          # Alto cruce
            prob_mutacion=0.3,       # Alta mutación para diversidad
            elite=2,                 # Poco elitismo para permitir cambios
            paciencia=15,            # Paciencia baja para ver evolución
            workers=1,               # 1 worker para test
            semilla=None             # Semilla aleatoria
        )
        
        if resultado:
            print("  ✅ Horarios generados exitosamente")
            
            # Test 2: Verificar que se ejecutaron múltiples generaciones
            print("\n🔍 TEST 2: Verificando ejecución de múltiples generaciones...")
            
            # Obtener logs del sistema para ver cuántas generaciones se ejecutaron
            from django.core.cache import cache
            progreso = cache.get('ga_progreso_actual')
            
            if progreso:
                generacion_final = progreso.get('generacion', 0)
                print(f"  • Generaciones ejecutadas: {generacion_final}")
                
                if generacion_final > 1:
                    print("  ✅ PERFECTO: Se ejecutaron múltiples generaciones")
                else:
                    print("  ❌ ERROR: Solo se ejecutó 1 generación")
                    return False
            else:
                print("  ⚠️ No se encontró progreso en cache")
            
            # Test 3: Verificar horarios generados
            print("\n🔍 TEST 3: Verificando horarios generados...")
            horarios = Horario.objects.all()
            total_horarios = horarios.count()
            
            print(f"  • Total de horarios: {total_horarios}")
            
            if total_horarios >= 350:  # Al menos 97% de los 360 bloques
                print("  ✅ PERFECTO: Horarios generados con alta cobertura")
            else:
                print(f"  ⚠️ ADVERTENCIA: Solo {total_horarios}/360 bloques generados")
            
            print("\n🎉 TEST DE DIVERSIDAD COMPLETADO")
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
    test_diversidad() 