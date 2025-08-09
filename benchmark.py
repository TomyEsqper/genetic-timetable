#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Script para ejecutar benchmarks del algoritmo genético de horarios.

Este script permite comparar el rendimiento del algoritmo genético
con diferentes configuraciones y librerías de optimización.
"""

import os
import sys
import time
import logging
import argparse
import django
from multiprocessing import cpu_count

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'genetic_timetable.settings')
django.setup()

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('benchmark_results.log')
    ]
)
logger = logging.getLogger('benchmark')

# Intentar importar librerías opcionales
def try_import(module_name):
    try:
        return __import__(module_name)
    except ImportError:
        return None

# Importar módulos del proyecto
from horarios.genetico import generar_horarios_genetico
from horarios.models import ConfiguracionColegio

# Importar librerías opcionales
numpy = try_import('numpy')
pandas = try_import('pandas')
matplotlib = try_import('matplotlib.pyplot')
seaborn = try_import('seaborn')


def ejecutar_benchmark(configuraciones, repeticiones=3):
    """
    Ejecuta benchmarks con diferentes configuraciones y reporta resultados.
    
    Args:
        configuraciones: Lista de diccionarios con parámetros de configuración
        repeticiones: Número de repeticiones para cada configuración
    """
    resultados = []
    
    # Verificar librerías disponibles
    libs_disponibles = []
    if numpy:
        libs_disponibles.append(f"NumPy {numpy.__version__}")
    if pandas:
        libs_disponibles.append(f"Pandas {pandas.__version__}")
    if try_import('numba'):
        numba = sys.modules['numba']
        libs_disponibles.append(f"Numba {numba.__version__}")
    if try_import('joblib'):
        joblib = sys.modules['joblib']
        libs_disponibles.append(f"Joblib {joblib.__version__}")
    if try_import('polars'):
        polars = sys.modules['polars']
        libs_disponibles.append(f"Polars {polars.__version__}")
    
    logger.info(f"Ejecutando benchmarks con {repeticiones} repeticiones por configuración")
    logger.info(f"Librerías disponibles: {', '.join(libs_disponibles)}")
    logger.info(f"Número de CPUs: {cpu_count()}")
    
    for i, config in enumerate(configuraciones):
        logger.info(f"\nBenchmark {i+1}/{len(configuraciones)}: {config}")
        
        tiempos = []
        for rep in range(repeticiones):
            logger.info(f"  Repetición {rep+1}/{repeticiones}")
            
            # Medir tiempo
            tiempo_inicio = time.time()
            
            # Ejecutar algoritmo genético
            try:
                generar_horarios_genetico(
                    config.get('colegio_id', 1),
                    max_generaciones=config.get('max_generaciones', 100),
                    tamano_poblacion=config.get('tamano_poblacion', 100),
                    tasa_mutacion=config.get('tasa_mutacion', 0.1),
                    elitismo=config.get('elitismo', 0.1)
                )
                
                tiempo_total = time.time() - tiempo_inicio
                tiempos.append(tiempo_total)
                logger.info(f"  Completado en {tiempo_total:.2f} segundos")
                
            except Exception as e:
                logger.error(f"Error en benchmark {i+1}, repetición {rep+1}: {e}")
        
        # Calcular estadísticas
        if tiempos:
            tiempo_promedio = sum(tiempos) / len(tiempos)
            tiempo_min = min(tiempos)
            tiempo_max = max(tiempos)
            
            logger.info(f"Resultados para configuración {i+1}:")
            logger.info(f"  Tiempo promedio: {tiempo_promedio:.2f} segundos")
            logger.info(f"  Tiempo mínimo: {tiempo_min:.2f} segundos")
            logger.info(f"  Tiempo máximo: {tiempo_max:.2f} segundos")
            
            resultados.append({
                'config_id': i,
                'config': config,
                'tiempo_promedio': tiempo_promedio,
                'tiempo_min': tiempo_min,
                'tiempo_max': tiempo_max,
                'tiempos': tiempos
            })
    
    return resultados


def generar_informe(resultados):
    """
    Genera un informe de los resultados del benchmark.
    
    Args:
        resultados: Lista de diccionarios con resultados de benchmarks
    """
    if not resultados:
        logger.warning("No hay resultados para generar informe")
        return
    
    logger.info("\n===== INFORME DE RESULTADOS =====\n")
    
    # Ordenar por tiempo promedio
    resultados_ordenados = sorted(resultados, key=lambda x: x['tiempo_promedio'])
    
    for i, resultado in enumerate(resultados_ordenados):
        config = resultado['config']
        logger.info(f"Posición #{i+1}: Configuración {resultado['config_id']+1}")
        logger.info(f"  Parámetros: {config}")
        logger.info(f"  Tiempo promedio: {resultado['tiempo_promedio']:.2f} segundos")
        logger.info(f"  Mejora respecto al peor: {(resultados_ordenados[-1]['tiempo_promedio'] / resultado['tiempo_promedio'] - 1) * 100:.1f}%")
        logger.info("")
    
    # Generar visualización si están disponibles las librerías
    if matplotlib and seaborn:
        import matplotlib.pyplot as plt
        import seaborn as sns
        
        # Configurar estilo
        sns.set_style("whitegrid")
        
        # Crear directorio para guardar visualizaciones
        directorio = 'benchmarks'
        if not os.path.exists(directorio):
            os.makedirs(directorio)
        
        # Preparar datos para visualización
        config_ids = [r['config_id'] for r in resultados_ordenados]
        tiempos = [r['tiempo_promedio'] for r in resultados_ordenados]
        
        # Generar gráfico de barras
        plt.figure(figsize=(12, 6))
        bars = plt.bar(config_ids, tiempos)
        
        # Añadir etiquetas
        plt.xlabel('ID de Configuración')
        plt.ylabel('Tiempo Promedio (segundos)')
        plt.title('Comparativa de Rendimiento por Configuración')
        
        # Añadir valores sobre las barras
        for bar in bars:
            height = bar.get_height()
            plt.text(bar.get_x() + bar.get_width()/2., height + 0.1,
                    f'{height:.1f}s', ha='center', va='bottom')
        
        # Guardar gráfico
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        plt.savefig(f"{directorio}/benchmark_comparativa_{timestamp}.png")
        logger.info(f"Visualización guardada en {directorio}/benchmark_comparativa_{timestamp}.png")
        plt.close()


def main():
    """
    Función principal para ejecutar benchmarks desde línea de comandos.
    """
    parser = argparse.ArgumentParser(description='Benchmark del algoritmo genético de horarios')
    parser.add_argument('--repeticiones', type=int, default=3,
                        help='Número de repeticiones para cada configuración')
    parser.add_argument('--colegio', type=int, default=1,
                        help='ID del colegio para pruebas')
    parser.add_argument('--modo', choices=['rapido', 'completo'], default='rapido',
                        help='Modo de benchmark: rápido o completo')
    
    args = parser.parse_args()
    
    # Verificar que el colegio existe
    try:
        colegio = ConfiguracionColegio.objects.get(pk=args.colegio)
        logger.info(f"Usando colegio: {colegio.nombre} (ID: {colegio.id})")
    except ConfiguracionColegio.DoesNotExist:
        logger.error(f"No existe un colegio con ID {args.colegio}")
        return
    
    # Definir configuraciones según el modo
    if args.modo == 'rapido':
        configuraciones = [
            # Configuración base
            {'colegio_id': args.colegio, 'tamano_poblacion': 50, 'max_generaciones': 50},
            
            # Variación de tamaño de población
            {'colegio_id': args.colegio, 'tamano_poblacion': 100, 'max_generaciones': 50},
            
            # Variación de tasa de mutación
            {'colegio_id': args.colegio, 'tamano_poblacion': 50, 'tasa_mutacion': 0.2, 'max_generaciones': 50},
        ]
    else:  # modo completo
        configuraciones = [
            # Variación de tamaño de población
            {'colegio_id': args.colegio, 'tamano_poblacion': 50, 'max_generaciones': 100},
            {'colegio_id': args.colegio, 'tamano_poblacion': 100, 'max_generaciones': 100},
            {'colegio_id': args.colegio, 'tamano_poblacion': 200, 'max_generaciones': 100},
            
            # Variación de tasa de mutación
            {'colegio_id': args.colegio, 'tamano_poblacion': 100, 'tasa_mutacion': 0.05, 'max_generaciones': 100},
            {'colegio_id': args.colegio, 'tamano_poblacion': 100, 'tasa_mutacion': 0.1, 'max_generaciones': 100},
            {'colegio_id': args.colegio, 'tamano_poblacion': 100, 'tasa_mutacion': 0.2, 'max_generaciones': 100},
            
            # Variación de elitismo
            {'colegio_id': args.colegio, 'tamano_poblacion': 100, 'elitismo': 0.05, 'max_generaciones': 100},
            {'colegio_id': args.colegio, 'tamano_poblacion': 100, 'elitismo': 0.1, 'max_generaciones': 100},
            {'colegio_id': args.colegio, 'tamano_poblacion': 100, 'elitismo': 0.2, 'max_generaciones': 100},
        ]
    
    # Ejecutar benchmarks
    resultados = ejecutar_benchmark(configuraciones, args.repeticiones)
    
    # Generar informe
    generar_informe(resultados)


if __name__ == "__main__":
    main()