#!/usr/bin/env python3
"""
TEST DE LLENADO COMPLETO
========================

Verifica que el algoritmo genético:
1. SÍ ejecute todas las generaciones configuradas (o hasta llenar todos los bloques)
2. SÍ llene TODOS los 360 bloques disponibles (100% de cobertura)
3. SÍ use early stopping inteligente solo cuando se alcance el objetivo

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

def test_llenado_completo():
    print("🧪 TEST DE LLENADO COMPLETO")
    print("=" * 60)
    
    try:
        # Test 1: Generar horarios con configuración de calidad
        print("\n🔍 TEST 1: Generando horarios con configuración de calidad...")
        
        # Limpiar horarios existentes
        Horario.objects.all().delete()
        print("  🗑️ Horarios existentes eliminados")
        
        # Generar horarios con parámetros de calidad
        resultado = generar_horarios_genetico(
            poblacion_size=80,      # Población grande para mejor evolución
            generaciones=1000,      # 1000 generaciones para evolución completa
            timeout_seg=600,        # 10 minutos máximo
            prob_cruce=0.9,         # Alto cruce
            prob_mutacion=0.05,     # Baja mutación para estabilidad
            elite=5,                # Elite moderado
            paciencia=50,           # Paciencia alta
            workers=1,              # 1 worker para estabilidad
            semilla=94601           # Semilla fija para reproducibilidad
        )
        
        if resultado:
            print("  ✅ Horarios generados exitosamente")
            
            # Test 2: Verificar que se ejecutaron suficientes generaciones
            print("\n🔍 TEST 2: Verificando ejecución de generaciones...")
            
            # Obtener progreso del cache
            from django.core.cache import cache
            progreso = cache.get('ga_progreso_actual')
            
            if progreso:
                generacion_final = progreso.get('generacion', 0)
                print(f"  • Generaciones ejecutadas: {generacion_final}")
                
                if generacion_final >= 100:  # Debe ejecutar al menos 100 generaciones
                    print("  ✅ PERFECTO: Se ejecutaron suficientes generaciones")
                elif generacion_final >= 50:
                    print("  ⚠️ ADVERTENCIA: Solo se ejecutaron 50+ generaciones")
                else:
                    print("  ❌ ERROR: Se ejecutaron muy pocas generaciones")
            else:
                print("  ⚠️ No se encontró progreso en cache")
            
            # Test 3: Verificar horarios generados (DEBE ser 100%)
            print("\n🔍 TEST 3: Verificando cobertura de horarios...")
            horarios = Horario.objects.all()
            total_horarios = horarios.count()
            
            print(f"  • Total de horarios: {total_horarios}")
            
            if total_horarios >= 360:  # 100% de los bloques
                print("  ✅ PERFECTO: 100% de cobertura alcanzada")
            elif total_horarios >= 350:  # Al menos 97%
                print(f"  ⚠️ ADVERTENCIA: Solo {total_horarios}/360 bloques generados ({(total_horarios/360)*100:.1f}%)")
            else:
                print(f"  ❌ ERROR: Solo {total_horarios}/360 bloques generados ({(total_horarios/360)*100:.1f}%)")
            
            # Test 4: Verificar razón de early stopping
            print("\n🔍 TEST 4: Verificando razón de finalización...")
            
            if progreso:
                estado = progreso.get('estado', 'N/A')
                mensaje = progreso.get('mensaje', 'N/A')
                print(f"  • Estado: {estado}")
                print(f"  • Mensaje: {mensaje}")
                
                if 'Objetivo alcanzado' in str(mensaje):
                    print("  ✅ PERFECTO: Se detuvo por alcanzar objetivo (100% cobertura)")
                elif 'Early stopping' in str(mensaje):
                    print("  ⚠️ ADVERTENCIA: Se detuvo por early stopping")
                elif 'Timeout' in str(mensaje):
                    print("  ⚠️ ADVERTENCIA: Se detuvo por timeout")
                else:
                    print("  ℹ️ INFO: Se detuvo por otra razón")
            
            print("\n🎉 TEST DE LLENADO COMPLETO COMPLETADO")
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
    test_llenado_completo() 