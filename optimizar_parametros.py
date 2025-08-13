#!/usr/bin/env python3
"""
Script para optimizar automáticamente los parámetros del algoritmo genético
basándose en el análisis de los errores de factibilidad.
"""

import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'colegio.settings')
django.setup()

from horarios.models import Curso, Profesor, Aula, MateriaGrado, MateriaProfesor, DisponibilidadProfesor, BloqueHorario
from horarios.genetico_funcion import generar_horarios_genetico

def analizar_factibilidad():
    """Analiza la factibilidad del problema antes de generar horarios"""
    print("🔍 ANALIZANDO FACTIBILIDAD DEL PROBLEMA")
    print("=" * 50)
    
    # Contar recursos disponibles
    total_cursos = Curso.objects.count()
    total_profesores = Profesor.objects.count()
    total_aulas = Aula.objects.count()
    
    # Contar materias por grado
    materias_por_grado = {}
    for mg in MateriaGrado.objects.all():
        grado = mg.grado.nombre
        if grado not in materias_por_grado:
            materias_por_grado[grado] = []
        materias_por_grado[grado].append(mg.materia.nombre)
    
    # Contar profesores por materia
    profesores_por_materia = {}
    for mp in MateriaProfesor.objects.all():
        materia = mp.materia.nombre
        if materia not in profesores_por_materia:
            profesores_por_materia[materia] = []
        profesores_por_materia[materia].append(mp.profesor.nombre)
    
    # Contar disponibilidades
    profesores_con_disponibilidad = DisponibilidadProfesor.objects.values('profesor').distinct().count()
    
    print(f"📊 RECURSOS DISPONIBLES:")
    print(f"   • Cursos: {total_cursos}")
    print(f"   • Profesores: {total_profesores}")
    print(f"   • Aulas: {total_aulas}")
    print(f"   • Profesores con disponibilidad: {profesores_con_disponibilidad}")
    
    print(f"\n📚 MATERIAS POR GRADO:")
    for grado, materias in materias_por_grado.items():
        print(f"   • {grado}: {', '.join(materias)}")
    
    print(f"\n👨‍🏫 PROFESORES POR MATERIA:")
    for materia, profesores in profesores_por_materia.items():
        print(f"   • {materia}: {', '.join(profesores)}")
    
    # Calcular horas totales requeridas
    total_horas_requeridas = 0
    for mg in MateriaGrado.objects.all():
        total_horas_requeridas += mg.materia.bloques_por_semana
    
    # Calcular capacidad total disponible
    dias_clase = 5  # lunes a viernes
    bloques_por_dia = 6  # bloques 1-6
    capacidad_total = total_aulas * dias_clase * bloques_por_dia
    
    print(f"\n⏰ CAPACIDAD vs REQUERIMIENTOS:")
    print(f"   • Horas totales requeridas: {total_horas_requeridas}")
    print(f"   • Capacidad total disponible: {capacidad_total}")
    print(f"   • Factor de ocupación: {total_horas_requeridas/capacidad_total:.2%}")
    
    return {
        'total_cursos': total_cursos,
        'total_profesores': total_profesores,
        'total_aulas': total_aulas,
        'profesores_con_disponibilidad': profesores_con_disponibilidad,
        'total_horas_requeridas': total_horas_requeridas,
        'capacidad_total': capacidad_total
    }

def generar_configuracion_optimizada(analisis):
    """Genera una configuración optimizada basada en el análisis"""
    print(f"\n⚙️ GENERANDO CONFIGURACIÓN OPTIMIZADA")
    print("=" * 50)
    
    # Configuración base según el tamaño del problema
    if analisis['total_horas_requeridas'] > 100:
        # Problema grande - usar configuración de alta calidad
        config = {
            'poblacion_size': 150,
            'generaciones': 500,
            'timeout_seg': 600,
            'prob_cruce': 0.9,
            'prob_mutacion': 0.15,
            'elite': 8,
            'paciencia': 40,
            'workers': 2,
            'semilla': 42
        }
        print("🎯 Configuración: ALTA CALIDAD (problema grande)")
    elif analisis['total_horas_requeridas'] > 50:
        # Problema mediano - usar configuración equilibrada
        config = {
            'poblacion_size': 100,
            'generaciones': 300,
            'timeout_seg': 300,
            'prob_cruce': 0.85,
            'prob_mutacion': 0.2,
            'elite': 5,
            'paciencia': 25,
            'workers': 2,
            'semilla': 42
        }
        print("⚖️ Configuración: EQUILIBRADA (problema mediano)")
    else:
        # Problema pequeño - usar configuración rápida
        config = {
            'poblacion_size': 80,
            'generaciones': 200,
            'timeout_seg': 180,
            'prob_cruce': 0.8,
            'prob_mutacion': 0.25,
            'elite': 4,
            'paciencia': 20,
            'workers': 1,
            'semilla': 42
        }
        print("🚀 Configuración: RÁPIDA (problema pequeño)")
    
    print(f"\n📋 PARÁMETROS RECOMENDADOS:")
    for key, value in config.items():
        print(f"   • {key}: {value}")
    
    return config

def ejecutar_generacion_optimizada(config):
    """Ejecuta la generación con parámetros optimizados"""
    print(f"\n🚀 EJECUTANDO GENERACIÓN OPTIMIZADA")
    print("=" * 50)
    
    try:
        resultado = generar_horarios_genetico(
            poblacion_size=config['poblacion_size'],
            generaciones=config['generaciones'],
            timeout_seg=config['timeout_seg'],
            prob_cruce=config['prob_cruce'],
            prob_mutacion=config['prob_mutacion'],
            elite=config['elite'],
            paciencia=config['paciencia'],
            workers=config['workers'],
            semilla=config['semilla']
        )
        
        if resultado['exito']:
            print("✅ GENERACIÓN EXITOSA!")
            print(f"   • Horarios generados: {resultado.get('total_horarios', 0)}")
            print(f"   • Tiempo de ejecución: {resultado.get('tiempo_ejecucion', 0):.2f} segundos")
            print(f"   • Generaciones completadas: {resultado.get('generaciones_completadas', 0)}")
            print(f"   • Mejor fitness: {resultado.get('mejor_fitness', 0):.4f}")
        else:
            print("❌ GENERACIÓN FALLIDA")
            print(f"   • Error: {resultado.get('error', 'Desconocido')}")
            
    except Exception as e:
        print(f"❌ ERROR EN LA GENERACIÓN: {str(e)}")

def main():
    """Función principal"""
    print("🎯 OPTIMIZADOR AUTOMÁTICO DE PARÁMETROS GENÉTICOS")
    print("=" * 60)
    
    # Paso 1: Analizar factibilidad
    analisis = analizar_factibilidad()
    
    # Paso 2: Generar configuración optimizada
    config = generar_configuracion_optimizada(analisis)
    
    # Paso 3: Preguntar si ejecutar
    print(f"\n❓ ¿Deseas ejecutar la generación con estos parámetros optimizados?")
    respuesta = input("   Escribe 'si' para continuar, o cualquier otra cosa para salir: ").lower().strip()
    
    if respuesta == 'si':
        ejecutar_generacion_optimizada(config)
    else:
        print("👋 Configuración generada pero no ejecutada.")
        print("   Puedes usar estos parámetros en el dashboard manualmente.")

if __name__ == "__main__":
    main() 