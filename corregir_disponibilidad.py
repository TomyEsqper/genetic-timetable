#!/usr/bin/env python3
"""
Script para corregir la disponibilidad de profesores.

Este script extiende la disponibilidad de todos los profesores para que
puedan trabajar en todos los bloques disponibles (1-6).
"""

import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'colegio.settings')
django.setup()

from horarios.models import Profesor, DisponibilidadProfesor, BloqueHorario

def corregir_disponibilidad_profesores():
    """Corrige la disponibilidad de todos los profesores."""
    print("🔧 CORRIGIENDO DISPONIBILIDAD DE PROFESORES")
    print("=" * 60)
    
    # Obtener todos los bloques disponibles
    bloques_disponibles = list(BloqueHorario.objects.filter(tipo='clase').order_by('numero').values_list('numero', flat=True))
    dias = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes']
    
    print(f"Bloques disponibles: {bloques_disponibles}")
    print(f"Días de la semana: {dias}")
    
    # Obtener todos los profesores
    profesores = Profesor.objects.all()
    print(f"Total de profesores: {profesores.count()}")
    
    # Contadores
    profesores_corregidos = 0
    disponibilidades_creadas = 0
    disponibilidades_actualizadas = 0
    
    for profesor in profesores:
        print(f"\nProcesando profesor: {profesor.nombre} (ID: {profesor.id})")
        
        # Obtener disponibilidad actual
        disponibilidad_actual = DisponibilidadProfesor.objects.filter(profesor=profesor)
        
        if disponibilidad_actual.exists():
            print(f"  Disponibilidad actual:")
            for disp in disponibilidad_actual:
                print(f"    {disp.dia}: bloques {disp.bloque_inicio}-{disp.bloque_fin}")
            
            # Verificar si necesita corrección
            necesita_correccion = any(disp.bloque_fin < max(bloques_disponibles) or disp.bloque_inicio > min(bloques_disponibles) for disp in disponibilidad_actual)
            
            if necesita_correccion:
                print(f"  ⚠️ Necesita corrección - extendiendo a todos los bloques")
                
                # Actualizar disponibilidad existente
                for disp in disponibilidad_actual:
                    if disp.bloque_inicio > min(bloques_disponibles):
                        disp.bloque_inicio = min(bloques_disponibles)
                    if disp.bloque_fin < max(bloques_disponibles):
                        disp.bloque_fin = max(bloques_disponibles)
                    disp.save()
                    disponibilidades_actualizadas += 1
                    print(f"    Actualizado {disp.dia}: bloques {disp.bloque_inicio}-{disp.bloque_fin}")
                
                profesores_corregidos += 1
            else:
                print(f"  ✅ Disponibilidad correcta")
        else:
            print(f"  ❌ Sin disponibilidad definida - creando nueva")
            
            # Crear disponibilidad completa para este profesor
            for dia in dias:
                disp = DisponibilidadProfesor.objects.create(
                    profesor=profesor,
                    dia=dia,
                    bloque_inicio=min(bloques_disponibles),
                    bloque_fin=max(bloques_disponibles)
                )
                disponibilidades_creadas += 1
                print(f"    Creada {dia}: bloques {disp.bloque_inicio}-{disp.bloque_fin}")
            
            profesores_corregidos += 1
    
    # Resumen
    print("\n" + "=" * 60)
    print("📊 RESUMEN DE CORRECCIONES")
    print("=" * 60)
    print(f"✅ Profesores corregidos: {profesores_corregidos}")
    print(f"✅ Disponibilidades creadas: {disponibilidades_creadas}")
    print(f"✅ Disponibilidades actualizadas: {disponibilidades_actualizadas}")
    
    if profesores_corregidos > 0:
        print(f"\n🎯 La disponibilidad de los profesores ha sido corregida.")
        print(f"   Ahora todos pueden trabajar en los bloques {min(bloques_disponibles)}-{max(bloques_disponibles)}")
        print(f"   Intente generar horarios nuevamente.")
    else:
        print(f"\n✅ No se requirieron correcciones.")
    
    return profesores_corregidos

def verificar_disponibilidad_corregida():
    """Verifica que la disponibilidad haya sido corregida correctamente (dinámico)."""
    print("\n🔍 VERIFICANDO DISPONIBILIDAD CORREGIDA")
    print("=" * 60)
    
    # Obtener bloques disponibles
    bloques_disponibles = list(BloqueHorario.objects.filter(tipo='clase').order_by('numero').values_list('numero', flat=True))
    max_bloque = max(bloques_disponibles) if bloques_disponibles else 0
    
    # Verificar todos los profesores
    for profesor in Profesor.objects.all():
        disponibilidad = DisponibilidadProfesor.objects.filter(profesor=profesor)
        
        print(f"\nProfesor {profesor.id} ({profesor.nombre}):")
        
        if disponibilidad.exists():
            print("   Disponibilidad actualizada:")
            for disp in disponibilidad:
                print(f"     {disp.dia}: bloques {disp.bloque_inicio}-{disp.bloque_fin}")
            
            # Verificar si puede trabajar en todos los bloques
            puede_trabajar_todos = all(disp.bloque_inicio <= min(bloques_disponibles) and disp.bloque_fin >= max_bloque for disp in disponibilidad) if max_bloque else True
            if puede_trabajar_todos:
                print(f"   ✅ Puede trabajar en todos los bloques (1-{max_bloque})")
            else:
                print(f"   ❌ Aún no puede trabajar en todos los bloques")
        else:
            print("   ❌ SIN DISPONIBILIDAD DEFINIDA")

if __name__ == "__main__":
    try:
        print("🚀 Iniciando corrección de disponibilidad de profesores...")
        
        # Ejecutar corrección
        profesores_corregidos = corregir_disponibilidad_profesores()
        
        # Verificar corrección
        verificar_disponibilidad_corregida()
        
        if profesores_corregidos > 0:
            print(f"\n🎉 Corrección completada exitosamente!")
            print(f"   {profesores_corregidos} profesores han sido corregidos.")
        else:
            print(f"\n✅ No se requirieron correcciones.")
            
    except Exception as e:
        print(f"❌ Error durante la corrección: {e}")
        import traceback
        traceback.print_exc() 