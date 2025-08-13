"""
Módulo de benchmarking y profiling para el algoritmo genético.

Este módulo implementa herramientas para medir el rendimiento
y identificar bottlenecks en el algoritmo genético.
"""

import time
import cProfile
import pstats
import io
import os
import json
from datetime import datetime
from typing import Dict, List, Any, Optional, Callable
from pathlib import Path
import numpy as np

from .genetico_funcion import generar_horarios_genetico
from .mascaras import precomputar_mascaras
from .fitness_optimizado import calcular_fitness_unificado, ConfiguracionFitness

class ProfilerGenetico:
    """Profiler especializado para el algoritmo genético"""
    
    def __init__(self, archivo_salida: str = "logs/profiling_results.txt"):
        self.archivo_salida = Path(archivo_salida)
        self.archivo_salida.parent.mkdir(parents=True, exist_ok=True)
        self.profiler = cProfile.Profile()
        self.stats = None
    
    def perfilar_funcion(self, func: Callable, *args, **kwargs) -> Dict[str, Any]:
        """
        Perfila una función específica usando cProfile.
        
        Args:
            func: Función a perfilar
            *args, **kwargs: Argumentos para la función
            
        Returns:
            Diccionario con métricas de profiling
        """
        print(f"🔍 Perfilando función: {func.__name__}")
        
        # Iniciar profiling
        self.profiler.enable()
        tiempo_inicio = time.time()
        
        try:
            resultado = func(*args, **kwargs)
            exito = True
        except Exception as e:
            resultado = None
            exito = False
            print(f"❌ Error durante profiling: {e}")
        
        tiempo_total = time.time() - tiempo_inicio
        self.profiler.disable()
        
        # Obtener estadísticas
        s = io.StringIO()
        ps = pstats.Stats(self.profiler, stream=s).sort_stats('cumulative')
        ps.print_stats(20)  # Top 20 funciones
        
        # Extraer métricas clave
        stats_dict = {}
        for func_name, (cc, nc, tt, ct, callers) in ps.stats.items():
            if isinstance(func_name, tuple):
                func_name = func_name[2]  # Nombre de la función
            
            stats_dict[func_name] = {
                'llamadas': nc,
                'tiempo_total': tt,
                'tiempo_acumulado': ct,
                'tiempo_por_llamada': tt / nc if nc > 0 else 0
            }
        
        # Guardar resultados
        resultados = {
            'funcion': func.__name__,
            'tiempo_total_s': tiempo_total,
            'exito': exito,
            'top_20_funciones': stats_dict,
            'estadisticas_completas': s.getvalue(),
            'timestamp': datetime.now().isoformat()
        }
        
        self._guardar_resultados(resultados)
        
        # Resetear profiler para siguiente uso
        self.profiler = cProfile.Profile()
        
        return resultados
    
    def _guardar_resultados(self, resultados: Dict[str, Any]) -> None:
        """Guarda los resultados del profiling"""
        try:
            with open(self.archivo_salida, 'w', encoding='utf-8') as f:
                json.dump(resultados, f, indent=2, ensure_ascii=False)
            
            print(f"📊 Resultados guardados en: {self.archivo_salida}")
            
        except Exception as e:
            print(f"❌ Error guardando resultados: {e}")

class BenchmarkGenetico:
    """Benchmark especializado para el algoritmo genético"""
    
    def __init__(self, archivo_salida: str = "logs/benchmark_results.json"):
        self.archivo_salida = Path(archivo_salida)
        self.archivo_salida.parent.mkdir(parents=True, exist_ok=True)
        self.resultados = []
    
    def benchmark_configuracion(self, 
                               configs: List[Dict[str, Any]], 
                               num_ejecuciones: int = 3) -> List[Dict[str, Any]]:
        """
        Ejecuta benchmark con diferentes configuraciones.
        
        Args:
            configs: Lista de configuraciones a probar
            num_ejecuciones: Número de ejecuciones por configuración
            
        Returns:
            Lista de resultados del benchmark
        """
        print(f"🚀 Iniciando benchmark con {len(configs)} configuraciones")
        
        for i, config in enumerate(configs):
            print(f"\n📋 Configuración {i+1}/{len(configs)}: {config}")
            
            resultados_config = []
            
            for ejecucion in range(num_ejecuciones):
                print(f"  🔄 Ejecución {ejecucion+1}/{num_ejecuciones}")
                
                try:
                    resultado = self._ejecutar_configuracion(config)
                    resultados_config.append(resultado)
                    
                except Exception as e:
                    print(f"    ❌ Error en ejecución {ejecucion+1}: {e}")
                    resultado = {
                        'configuracion': config,
                        'ejecucion': ejecucion + 1,
                        'exito': False,
                        'error': str(e),
                        'timestamp': datetime.now().isoformat()
                    }
                    resultados_config.append(resultado)
            
            # Calcular estadísticas de la configuración
            estadisticas = self._calcular_estadisticas_configuracion(resultados_config)
            self.resultados.append({
                'configuracion': config,
                'ejecuciones': resultados_config,
                'estadisticas': estadisticas
            })
        
        # Guardar resultados completos
        self._guardar_resultados()
        
        return self.resultados
    
    def _ejecutar_configuracion(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Ejecuta una configuración específica y mide métricas"""
        tiempo_inicio = time.time()
        
        # Ejecutar algoritmo genético
        resultado = generar_horarios_genetico(**config)
        
        tiempo_total = time.time() - tiempo_inicio
        
        # Extraer métricas clave
        metricas = {
            'configuracion': config,
            'tiempo_total_s': tiempo_total,
            'exito': resultado.get('exito', False),
            'fitness_final': resultado.get('mejor_fitness', 0.0),
            'generaciones_completadas': resultado.get('generaciones_completadas', 0),
            'convergencia': resultado.get('convergencia', False),
            'timestamp': datetime.now().isoformat()
        }
        
        # Agregar métricas adicionales si están disponibles
        if 'metricas' in resultado:
            metricas.update(resultado['metricas'])
        
        return metricas
    
    def _calcular_estadisticas_configuracion(self, resultados: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calcula estadísticas para una configuración"""
        if not resultados:
            return {}
        
        # Filtrar ejecuciones exitosas
        exitosas = [r for r in resultados if r.get('exito', False)]
        
        if not exitosas:
            return {
                'exito_rate': 0.0,
                'error': 'Ninguna ejecución exitosa'
            }
        
        # Métricas de tiempo
        tiempos = [r['tiempo_total_s'] for r in exitosas]
        metricas_tiempo = {
            'tiempo_promedio_s': np.mean(tiempos),
            'tiempo_mediana_s': np.median(tiempos),
            'tiempo_min_s': np.min(tiempos),
            'tiempo_max_s': np.max(tiempos),
            'tiempo_std_s': np.std(tiempos)
        }
        
        # Métricas de fitness
        fitness_values = [r.get('fitness_final', 0.0) for r in exitosas]
        metricas_fitness = {
            'fitness_promedio': np.mean(fitness_values),
            'fitness_mediana': np.median(fitness_values),
            'fitness_min': np.min(fitness_values),
            'fitness_max': np.max(fitness_values),
            'fitness_std': np.std(fitness_values)
        }
        
        # Métricas de generaciones
        generaciones = [r.get('generaciones_completadas', 0) for r in exitosas]
        metricas_generaciones = {
            'generaciones_promedio': np.mean(generaciones),
            'generaciones_mediana': np.median(generaciones),
            'generaciones_min': np.min(generaciones),
            'generaciones_max': np.max(generaciones)
        }
        
        return {
            'exito_rate': len(exitosas) / len(resultados),
            'num_ejecuciones': len(resultados),
            'num_exitosas': len(exitosas),
            'metricas_tiempo': metricas_tiempo,
            'metricas_fitness': metricas_fitness,
            'metricas_generaciones': metricas_generaciones
        }
    
    def _guardar_resultados(self) -> None:
        """Guarda los resultados del benchmark"""
        try:
            with open(self.archivo_salida, 'w', encoding='utf-8') as f:
                json.dump(self.resultados, f, indent=2, ensure_ascii=False)
            
            print(f"📊 Resultados del benchmark guardados en: {self.archivo_salida}")
            
        except Exception as e:
            print(f"❌ Error guardando resultados del benchmark: {e}")
    
    def generar_reporte_comparativo(self) -> str:
        """Genera un reporte comparativo de los resultados"""
        if not self.resultados:
            return "No hay resultados para comparar"
        
        reporte = []
        reporte.append("=" * 80)
        reporte.append("REPORTE COMPARATIVO DE BENCHMARK")
        reporte.append("=" * 80)
        reporte.append("")
        
        for i, resultado in enumerate(self.resultados):
            config = resultado['configuracion']
            stats = resultado['estadisticas']
            
            reporte.append(f"CONFIGURACIÓN {i+1}:")
            reporte.append(f"  Población: {config.get('poblacion_size', 'N/A')}")
            reporte.append(f"  Generaciones: {config.get('generaciones', 'N/A')}")
            reporte.append(f"  Workers: {config.get('workers', 'N/A')}")
            reporte.append(f"  Prob. Cruce: {config.get('prob_cruce', 'N/A')}")
            reporte.append(f"  Prob. Mutación: {config.get('prob_mutacion', 'N/A')}")
            reporte.append("")
            
            if 'error' in stats:
                reporte.append(f"  ❌ ERROR: {stats['error']}")
            else:
                reporte.append(f"  ✅ Tasa de éxito: {stats['exito_rate']:.1%}")
                reporte.append(f"  ⏱️  Tiempo promedio: {stats['metricas_tiempo']['tiempo_promedio_s']:.2f}s")
                reporte.append(f"  🎯 Fitness promedio: {stats['metricas_fitness']['fitness_promedio']:.2f}")
                reporte.append(f"  🔄 Generaciones promedio: {stats['metricas_generaciones']['generaciones_promedio']:.1f}")
            
            reporte.append("")
        
        # Identificar mejor configuración
        configs_exitosas = [r for r in self.resultados if 'error' not in r['estadisticas']]
        if configs_exitosas:
            mejor_config = min(configs_exitosas, 
                             key=lambda x: x['estadisticas']['metricas_tiempo']['tiempo_promedio_s'])
            
            reporte.append("🏆 MEJOR CONFIGURACIÓN:")
            reporte.append(f"  Configuración {self.resultados.index(mejor_config) + 1}")
            reporte.append(f"  Tiempo promedio: {mejor_config['estadisticas']['metricas_tiempo']['tiempo_promedio_s']:.2f}s")
            reporte.append(f"  Fitness promedio: {mejor_config['estadisticas']['metricas_fitness']['fitness_promedio']:.2f}")
        
        return "\n".join(reporte)

def ejecutar_benchmark_rapido():
    """Ejecuta un benchmark rápido con configuraciones básicas"""
    print("🚀 Ejecutando benchmark rápido...")
    
    # Configuraciones a probar
    configs = [
        {
            'poblacion_size': 50,
            'generaciones': 100,
            'workers': 1,
            'semilla': 42
        },
        {
            'poblacion_size': 100,
            'generaciones': 200,
            'workers': 2,
            'semilla': 42
        },
        {
            'poblacion_size': 200,
            'generaciones': 400,
            'workers': 2,
            'semilla': 42
        }
    ]
    
    # Crear benchmark
    benchmark = BenchmarkGenetico()
    
    # Ejecutar benchmark
    resultados = benchmark.benchmark_configuracion(configs, num_ejecuciones=2)
    
    # Generar reporte
    reporte = benchmark.generar_reporte_comparativo()
    print(reporte)
    
    return resultados

def perfilar_funciones_criticas():
    """Perfila las funciones críticas del algoritmo genético"""
    print("🔍 Perfilando funciones críticas...")
    
    # Crear profiler
    profiler = ProfilerGenetico()
    
    # Perfilar precomputación de máscaras
    print("\n1. Perfilando precomputación de máscaras...")
    resultado_mascaras = profiler.perfilar_funcion(precomputar_mascaras)
    
    # Perfilar cálculo de fitness (con datos de prueba)
    print("\n2. Perfilando cálculo de fitness...")
    try:
        mascaras = precomputar_mascaras()
        config_fitness = ConfiguracionFitness()
        
        # Crear cromosoma de prueba
        cromosoma_prueba = {
            (1, 'lunes', 1): (1, 1),
            (1, 'martes', 1): (1, 1),
            (1, 'miércoles', 1): (1, 1)
        }
        
        resultado_fitness = profiler.perfilar_funcion(
            calcular_fitness_unificado,
            cromosoma_prueba, mascaras, config_fitness
        )
        
    except Exception as e:
        print(f"❌ Error perfilando fitness: {e}")
    
    print("\n✅ Profiling completado. Revisa los archivos de salida.")

if __name__ == "__main__":
    # Ejecutar benchmark rápido
    ejecutar_benchmark_rapido()
    
    # Perfilar funciones críticas
    perfilar_funciones_criticas() 