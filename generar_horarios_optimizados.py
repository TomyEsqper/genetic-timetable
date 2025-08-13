#!/usr/bin/env python3
"""
Script para generar horarios con parámetros optimizados automáticamente
"""

import os
import django
import time

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'colegio.settings')
django.setup()

from horarios.genetico_funcion import generar_horarios_genetico

def generar_horarios_optimizados():
    """Genera horarios con parámetros optimizados"""
    print("🚀 GENERANDO HORARIOS CON PARÁMETROS OPTIMIZADOS")
    print("=" * 60)
    
    # Configuración optimizada para problema de 230 bloques
    config_optimizada = {
        'poblacion_size': 200,      # Población grande para mejor exploración
        'generaciones': 800,        # Muchas generaciones para convergencia
        'timeout_seg': 900,         # 15 minutos máximo
        'prob_cruce': 0.9,          # Alta probabilidad de cruce
        'prob_mutacion': 0.15,      # Mutación moderada
        'elite': 10,                # Preservar más individuos buenos
        'paciencia': 50,            # Más paciencia antes de parar
        'workers': 2,               # 2 workers para paralelización
        'semilla': 42               # Semilla fija para reproducibilidad
    }
    
    print("📋 CONFIGURACIÓN OPTIMIZADA:")
    for key, value in config_optimizada.items():
        print(f"   • {key}: {value}")
    
    print(f"\n⏰ INICIANDO GENERACIÓN...")
    print(f"   • Tiempo máximo estimado: {config_optimizada['timeout_seg']} segundos")
    print(f"   • Generaciones máximas: {config_optimizada['generaciones']}")
    print(f"   • Población: {config_optimizada['poblacion_size']} individuos")
    
    # Iniciar temporizador
    inicio = time.time()
    
    try:
        resultado = generar_horarios_genetico(**config_optimizada)
        
        tiempo_total = time.time() - inicio
        
        if resultado['exito']:
            print(f"\n✅ GENERACIÓN EXITOSA!")
            print(f"   • Horarios generados: {resultado.get('total_horarios', 0)}")
            print(f"   • Tiempo de ejecución: {tiempo_total:.2f} segundos")
            print(f"   • Generaciones completadas: {resultado.get('generaciones_completadas', 0)}")
            print(f"   • Mejor fitness: {resultado.get('mejor_fitness', 0):.4f}")
            
            # Verificar si hay horarios en la base de datos
            from horarios.models import Horario
            total_horarios_bd = Horario.objects.count()
            print(f"   • Horarios en BD: {total_horarios_bd}")
            
            if total_horarios_bd > 0:
                print(f"\n🎉 ¡HORARIOS GENERADOS EXITOSAMENTE!")
                print(f"   • Puedes verlos en el dashboard")
                print(f"   • Total de asignaciones: {total_horarios_bd}")
            else:
                print(f"\n⚠️ Generación exitosa pero no hay horarios en BD")
                print(f"   • Revisar si hay problemas de guardado")
                
        else:
            print(f"\n❌ GENERACIÓN FALLIDA")
            print(f"   • Error: {resultado.get('error', 'Desconocido')}")
            print(f"   • Tiempo transcurrido: {tiempo_total:.2f} segundos")
            
            # Análisis del error
            if 'choques' in resultado:
                print(f"\n🔍 ANÁLISIS DE ERRORES:")
                choques = resultado['choques']
                print(f"   • Choques de profesores: {len(choques)}")
                
                # Agrupar choques por profesor
                choques_por_profesor = {}
                for choque in choques:
                    prof_id = choque['profesor_id']
                    if prof_id not in choques_por_profesor:
                        choques_por_profesor[prof_id] = []
                    choques_por_profesor[prof_id].append(choque)
                
                print(f"   • Profesores con conflictos:")
                for prof_id, conflictos in choques_por_profesor.items():
                    print(f"     - Profesor {prof_id}: {len(conflictos)} conflictos")
            
            if 'asignaciones_invalidas' in resultado:
                asignaciones_inv = resultado['asignaciones_invalidas']
                print(f"   • Asignaciones inválidas: {len(asignaciones_inv)}")
                
            if 'diferencias' in resultado:
                diferencias = resultado['diferencias']
                print(f"   • Diferencias en horas: {len(diferencias)}")
                
    except Exception as e:
        tiempo_total = time.time() - inicio
        print(f"\n❌ ERROR EN LA GENERACIÓN: {str(e)}")
        print(f"   • Tiempo transcurrido: {tiempo_total:.2f} segundos")
        
        # Sugerencias de solución
        print(f"\n💡 SUGERENCIAS DE SOLUCIÓN:")
        print(f"   • Verificar que todos los profesores tengan disponibilidad")
        print(f"   • Revisar que no haya conflictos en MateriaProfesor")
        print(f"   • Comprobar que las aulas estén disponibles")
        print(f"   • Verificar la configuración de bloques por día")

if __name__ == "__main__":
    generar_horarios_optimizados() 