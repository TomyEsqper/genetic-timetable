#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Módulo de diagnóstico para el algoritmo genético de generación de horarios.

Este módulo permite ejecutar pruebas de rendimiento y análisis del algoritmo
genético con diferentes configuraciones y tamaños de datos.
"""

import os
import time
import logging
import argparse
from typing import Dict, List, Tuple, Any

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('diagnostico')

# Intentar importar librerías opcionales
def try_import(module_name):
    try:
        return __import__(module_name)
    except ImportError:
        return None

# Importar módulos del proyecto
from horarios.genetico import (
    cargar_datos, inicializar_poblacion_guiada, evaluar_poblacion_paralelo,
    generar_horarios_genetico, calcular_diversidad_poblacion
)
from horarios.models import (
    ConfiguracionColegio, Profesor, DisponibilidadProfesor,
    Materia, MateriaProfesor, Grado, MateriaGrado, Curso, Aula,
    BloqueHorario, Horario
)

# Importar librerías opcionales
numpy = try_import('numpy')
pandas = try_import('pandas')
matplotlib = try_import('matplotlib.pyplot')
seaborn = try_import('seaborn')


def ejecutar_benchmark(configuraciones: List[Dict[str, Any]], repeticiones: int = 3) -> Dict[str, List[float]]:
    """
    Ejecuta benchmarks del algoritmo genético con diferentes configuraciones.
    
    Args:
        configuraciones: Lista de diccionarios con parámetros de configuración
        repeticiones: Número de repeticiones para cada configuración
        
    Returns:
        Diccionario con resultados de tiempos y métricas
    """
    resultados = {
        'config_id': [],
        'tiempo_total': [],
        'tiempo_por_generacion': [],
        'generaciones': [],
        'fitness_final': [],
        'conflictos_final': [],
        'diversidad_final': []
    }
    
    for i, config in enumerate(configuraciones):
        logger.info(f"Ejecutando benchmark {i+1}/{len(configuraciones)}: {config}")
        
        tiempos = []
        fitness = []
        conflictos = []
        generaciones = []
        diversidad = []
        
        for rep in range(repeticiones):
            logger.info(f"Repetición {rep+1}/{repeticiones}")
            
            # Medir tiempo
            tiempo_inicio = time.time()
            
            # Ejecutar algoritmo genético con esta configuración
            resultado = generar_horarios_genetico(
                config.get('colegio_id', 1),
                max_generaciones=config.get('max_generaciones', 100),
                tamano_poblacion=config.get('tamano_poblacion', 100),
                tasa_mutacion=config.get('tasa_mutacion', 0.1),
                elitismo=config.get('elitismo', 0.1)
            )
            
            tiempo_total = time.time() - tiempo_inicio
            tiempos.append(tiempo_total)
            
            # Obtener métricas del resultado
            # Estas métricas deberían ser retornadas por generar_horarios_genetico
            # o calculadas a partir del resultado
            
            # Ejemplo (ajustar según la implementación real):
            # fitness.append(resultado.get('fitness_final', 0))
            # conflictos.append(resultado.get('conflictos_final', 0))
            # generaciones.append(resultado.get('generaciones', 0))
            # diversidad.append(resultado.get('diversidad_final', 0))
            
        # Promediar resultados de las repeticiones
        resultados['config_id'].append(i)
        resultados['tiempo_total'].append(sum(tiempos) / len(tiempos))
        
        # Calcular tiempo promedio por generación si tenemos datos de generaciones
        if generaciones and all(g > 0 for g in generaciones):
            tiempo_por_gen = [t/g for t, g in zip(tiempos, generaciones)]
            resultados['tiempo_por_generacion'].append(sum(tiempo_por_gen) / len(tiempo_por_gen))
        else:
            resultados['tiempo_por_generacion'].append(None)
        
        # Agregar el resto de métricas si están disponibles
        if fitness:
            resultados['fitness_final'].append(sum(fitness) / len(fitness))
        else:
            resultados['fitness_final'].append(None)
            
        if conflictos:
            resultados['conflictos_final'].append(sum(conflictos) / len(conflictos))
        else:
            resultados['conflictos_final'].append(None)
            
        if generaciones:
            resultados['generaciones'].append(sum(generaciones) / len(generaciones))
        else:
            resultados['generaciones'].append(None)
            
        if diversidad:
            resultados['diversidad_final'].append(sum(diversidad) / len(diversidad))
        else:
            resultados['diversidad_final'].append(None)
    
    return resultados


def visualizar_resultados(resultados: Dict[str, List[float]], configuraciones: List[Dict[str, Any]]) -> None:
    """
    Genera visualizaciones de los resultados del benchmark.
    
    Args:
        resultados: Diccionario con resultados de tiempos y métricas
        configuraciones: Lista de diccionarios con parámetros de configuración
    """
    if not matplotlib or not seaborn:
        logger.warning("Matplotlib o Seaborn no están disponibles. No se pueden generar visualizaciones.")
        return
    
    import matplotlib.pyplot as plt
    import seaborn as sns
    
    # Configurar estilo
    sns.set_style("whitegrid")
    
    # Crear directorio para guardar visualizaciones
    directorio = 'diagnosticos'
    if not os.path.exists(directorio):
        os.makedirs(directorio)
    
    # Convertir resultados a DataFrame si pandas está disponible
    if pandas:
        import pandas as pd
        df_resultados = pd.DataFrame(resultados)
        
        # Añadir información de configuración
        for i, config in enumerate(configuraciones):
            for key, value in config.items():
                if key not in df_resultados.columns:
                    df_resultados[key] = None
                df_resultados.loc[df_resultados['config_id'] == i, key] = value
        
        # Guardar resultados en CSV
        df_resultados.to_csv(f"{directorio}/benchmark_resultados.csv", index=False)
        logger.info(f"Resultados guardados en {directorio}/benchmark_resultados.csv")
        
        # Generar visualizaciones
        plt.figure(figsize=(12, 8))
        
        # 1. Tiempo total vs tamaño de población
        if 'tamano_poblacion' in df_resultados.columns:
            plt.subplot(2, 2, 1)
            sns.lineplot(x='tamano_poblacion', y='tiempo_total', data=df_resultados)
            plt.title('Tiempo Total vs Tamaño de Población')
            plt.xlabel('Tamaño de Población')
            plt.ylabel('Tiempo Total (s)')
        
        # 2. Fitness final vs tasa de mutación
        if 'tasa_mutacion' in df_resultados.columns and 'fitness_final' in df_resultados.columns:
            plt.subplot(2, 2, 2)
            sns.lineplot(x='tasa_mutacion', y='fitness_final', data=df_resultados)
            plt.title('Fitness Final vs Tasa de Mutación')
            plt.xlabel('Tasa de Mutación')
            plt.ylabel('Fitness Final')
        
        # 3. Conflictos finales vs elitismo
        if 'elitismo' in df_resultados.columns and 'conflictos_final' in df_resultados.columns:
            plt.subplot(2, 2, 3)
            sns.lineplot(x='elitismo', y='conflictos_final', data=df_resultados)
            plt.title('Conflictos Finales vs Elitismo')
            plt.xlabel('Elitismo')
            plt.ylabel('Conflictos Finales')
        
        # 4. Tiempo por generación vs tamaño de población
        if 'tamano_poblacion' in df_resultados.columns and 'tiempo_por_generacion' in df_resultados.columns:
            plt.subplot(2, 2, 4)
            sns.lineplot(x='tamano_poblacion', y='tiempo_por_generacion', data=df_resultados)
            plt.title('Tiempo por Generación vs Tamaño de Población')
            plt.xlabel('Tamaño de Población')
            plt.ylabel('Tiempo por Generación (s)')
        
        plt.tight_layout()
        plt.savefig(f"{directorio}/benchmark_visualizacion.png")
        logger.info(f"Visualización guardada en {directorio}/benchmark_visualizacion.png")
        plt.close()
    else:
        # Visualización básica sin pandas
        plt.figure(figsize=(10, 6))
        plt.bar(range(len(resultados['config_id'])), resultados['tiempo_total'])
        plt.xlabel('Configuración ID')
        plt.ylabel('Tiempo Total (s)')
        plt.title('Tiempo Total por Configuración')
        plt.savefig(f"{directorio}/benchmark_tiempo_total.png")
        plt.close()
        
        if all(x is not None for x in resultados['fitness_final']):
            plt.figure(figsize=(10, 6))
            plt.bar(range(len(resultados['config_id'])), resultados['fitness_final'])
            plt.xlabel('Configuración ID')
            plt.ylabel('Fitness Final')
            plt.title('Fitness Final por Configuración')
            plt.savefig(f"{directorio}/benchmark_fitness.png")
            plt.close()


def main():
    """
    Función principal para ejecutar diagnósticos desde línea de comandos.
    """
    parser = argparse.ArgumentParser(description='Diagnóstico del algoritmo genético de horarios')
    parser.add_argument('--modo', choices=['benchmark', 'analisis'], default='benchmark',
                        help='Modo de ejecución: benchmark o análisis')
    parser.add_argument('--repeticiones', type=int, default=3,
                        help='Número de repeticiones para cada configuración')
    parser.add_argument('--poblacion', type=int, default=100,
                        help='Tamaño de población base para pruebas')
    parser.add_argument('--generaciones', type=int, default=100,
                        help='Número máximo de generaciones')
    parser.add_argument('--colegio', type=int, default=1,
                        help='ID del colegio para pruebas')
    
    args = parser.parse_args()
    
    if args.modo == 'benchmark':
        # Configuraciones para benchmark
        configuraciones = [
            # Variación de tamaño de población
            {'colegio_id': args.colegio, 'tamano_poblacion': 50, 'max_generaciones': args.generaciones},
            {'colegio_id': args.colegio, 'tamano_poblacion': 100, 'max_generaciones': args.generaciones},
            {'colegio_id': args.colegio, 'tamano_poblacion': 200, 'max_generaciones': args.generaciones},
            
            # Variación de tasa de mutación
            {'colegio_id': args.colegio, 'tamano_poblacion': args.poblacion, 'tasa_mutacion': 0.05},
            {'colegio_id': args.colegio, 'tamano_poblacion': args.poblacion, 'tasa_mutacion': 0.1},
            {'colegio_id': args.colegio, 'tamano_poblacion': args.poblacion, 'tasa_mutacion': 0.2},
            
            # Variación de elitismo
            {'colegio_id': args.colegio, 'tamano_poblacion': args.poblacion, 'elitismo': 0.05},
            {'colegio_id': args.colegio, 'tamano_poblacion': args.poblacion, 'elitismo': 0.1},
            {'colegio_id': args.colegio, 'tamano_poblacion': args.poblacion, 'elitismo': 0.2},
        ]
        
        # Ejecutar benchmark
        resultados = ejecutar_benchmark(configuraciones, args.repeticiones)
        
        # Visualizar resultados
        visualizar_resultados(resultados, configuraciones)
        
    elif args.modo == 'analisis':
        # Ejecutar análisis detallado de una configuración específica
        logger.info("Modo análisis no implementado completamente. Ejecutando configuración básica.")
        
        # Ejemplo de configuración para análisis
        config = {
            'colegio_id': args.colegio,
            'tamano_poblacion': args.poblacion,
            'max_generaciones': args.generaciones,
            'tasa_mutacion': 0.1,
            'elitismo': 0.1
        }
        
        # Ejecutar algoritmo genético con esta configuración
        tiempo_inicio = time.time()
        resultado = generar_horarios_genetico(**config)
        tiempo_total = time.time() - tiempo_inicio
        
        logger.info(f"Análisis completado en {tiempo_total:.2f} segundos")


if __name__ == "__main__":
    main()