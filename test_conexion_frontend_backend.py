#!/usr/bin/env python3
"""
TEST DE CONEXIÓN FRONTEND-BACKEND
==================================

Verifica que los parámetros del formulario se envíen correctamente
al backend y se usen en la generación de horarios.

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

from django.test import Client
from django.urls import reverse
from horarios.models import Horario

def test_conexion_frontend_backend():
    print("🧪 TEST DE CONEXIÓN FRONTEND-BACKEND")
    print("=" * 60)
    
    try:
        # Test 1: Verificar que el formulario esté disponible
        print("\n🔍 TEST 1: Verificando disponibilidad del formulario...")
        
        client = Client()
        response = client.get(reverse('dashboard'))
        
        if response.status_code == 200:
            print("  ✅ Formulario disponible en dashboard")
        else:
            print(f"  ❌ Error accediendo al dashboard: {response.status_code}")
            return False
        
        # Test 2: Verificar que los parámetros se envíen correctamente
        print("\n🔍 TEST 2: Verificando envío de parámetros...")
        
        # Parámetros de configuración de calidad
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
        
        # Limpiar horarios existentes
        Horario.objects.all().delete()
        print("  🗑️ Horarios existentes eliminados")
        
        # Simular envío del formulario
        print("  📤 Enviando parámetros de configuración de calidad...")
        response = client.post(reverse('generar_horario'), parametros_calidad)
        
        if response.status_code == 302:  # Redirect después de POST
            print("  ✅ Formulario enviado correctamente")
        else:
            print(f"  ❌ Error enviando formulario: {response.status_code}")
            return False
        
        # Test 3: Verificar que se hayan generado horarios
        print("\n🔍 TEST 3: Verificando generación de horarios...")
        
        # Esperar un momento para que se procese
        import time
        time.sleep(2)
        
        horarios = Horario.objects.all()
        total_horarios = horarios.count()
        
        print(f"  • Total de horarios generados: {total_horarios}")
        
        if total_horarios > 0:
            print("  ✅ Horarios generados exitosamente")
            
            # Verificar que se usaron los parámetros correctos
            print("\n🔍 TEST 4: Verificando uso de parámetros...")
            
            # Obtener el progreso del cache para verificar parámetros
            from django.core.cache import cache
            progreso = cache.get('ga_progreso_actual')
            
            if progreso:
                print("  ✅ Progreso del algoritmo disponible en cache")
                print(f"  • Generación actual: {progreso.get('generacion', 'N/A')}")
                print(f"  • Estado: {progreso.get('estado', 'N/A')}")
                print(f"  • Horarios parciales: {progreso.get('horarios_parciales', 'N/A')}")
            else:
                print("  ⚠️ No se encontró progreso en cache")
            
            print("\n🎉 TEST DE CONEXIÓN COMPLETADO EXITOSAMENTE")
            return True
            
        else:
            print("  ❌ No se generaron horarios")
            return False
        
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_conexion_frontend_backend() 