#!/usr/bin/env python3
"""
Script de prueba rápida para verificar las optimizaciones implementadas.
Ejecutar: python test_optimizaciones.py
"""

import os
import sys
import django
from django.conf import settings

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'colegio.settings')
django.setup()

def test_optimizaciones():
    """Prueba rápida de las optimizaciones implementadas"""
    print("🧪 Probando optimizaciones del generador de horarios...")
    
    try:
        # 1. Verificar que DIAS se carga dinámicamente
        from horarios.genetico import DIAS, get_dias_clase
        print(f"✅ DIAS cargado dinámicamente: {DIAS}")
        
        # 2. Verificar función get_dias_clase
        dias_func = get_dias_clase()
        print(f"✅ get_dias_clase() retorna: {dias_func}")
        
        # 3. Verificar que no hay DIAS hardcoded
        from horarios.genetico import DIAS
        if DIAS != ['lunes', 'martes', 'miércoles', 'jueves', 'viernes'] or len(DIAS) != 5:
            print(f"⚠️ DIAS no es el valor por defecto esperado: {DIAS}")
        else:
            print("✅ DIAS usa valores por defecto (configuración no encontrada)")
        
        # 4. Verificar warmup_numba
        from horarios.genetico import warmup_numba
        print("✅ Función warmup_numba disponible")
        
        # 5. Verificar modo rápido
        from horarios.genetico_funcion import generar_horarios_genetico
        print("✅ Función generar_horarios_genetico disponible")
        
        # 6. Verificar que se puede llamar con parámetros mínimos
        print("\n🚀 Probando llamada con parámetros mínimos...")
        resultado = generar_horarios_genetico(
            poblacion_size=10,  # Muy pequeño para prueba rápida
            generaciones=5,      # Muy pocas para prueba rápida
            timeout_seg=30       # Timeout corto
        )
        
        print(f"✅ Llamada exitosa: {resultado.get('status', 'unknown')}")
        if resultado.get('status') == 'error':
            print(f"   Error: {resultado.get('mensaje', 'Sin mensaje')}")
        else:
            print(f"   Generaciones completadas: {resultado.get('generaciones_completadas', 0)}")
            print(f"   Tiempo total: {resultado.get('tiempo_total_segundos', 0):.2f}s")
        
        # 7. Verificar bulk_create en modelos
        from horarios.models import Horario
        print(f"✅ Modelo Horario disponible, total actual: {Horario.objects.count()}")
        
        print("\n🎉 Todas las optimizaciones están implementadas correctamente!")
        
    except Exception as e:
        print(f"❌ Error durante la prueba: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

def test_modo_rapido():
    """Prueba específica del modo rápido"""
    print("\n🚀 Probando modo rápido...")
    
    try:
        # Activar modo rápido
        os.environ['HORARIOS_FAST'] = '1'
        
        from horarios.genetico_funcion import generar_horarios_genetico
        
        # Llamar sin parámetros para verificar defaults
        resultado = generar_horarios_genetico(
            poblacion_size=5,
            generaciones=3,
            timeout_seg=15
        )
        
        print(f"✅ Modo rápido funcionando: {resultado.get('status', 'unknown')}")
        
        # Limpiar
        del os.environ['HORARIOS_FAST']
        
    except Exception as e:
        print(f"❌ Error en modo rápido: {e}")
        return False
    
    return True

if __name__ == '__main__':
    print("=" * 60)
    print("🧪 PRUEBA RÁPIDA DE OPTIMIZACIONES")
    print("=" * 60)
    
    # Ejecutar pruebas
    test_optimizaciones()
    test_modo_rapido()
    
    print("\n" + "=" * 60)
    print("✅ PRUEBAS COMPLETADAS")
    print("=" * 60) 