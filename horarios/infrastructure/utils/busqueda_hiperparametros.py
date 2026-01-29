"""
Sistema de búsqueda de hiperparámetros para el algoritmo genético.

Implementa búsqueda en rejilla y random search para optimizar
la configuración del algoritmo genético.
"""

import random
import time
import uuid
from typing import Dict, List, Tuple, Any, Optional
from dataclasses import dataclass
import numpy as np
from concurrent.futures import ProcessPoolExecutor, as_completed
import json

from .genetico_funcion import generar_horarios_genetico
from horarios.models import TrackerCorrida
from .fitness_optimizado import ConfiguracionFitness

@dataclass
class ConfiguracionBusqueda:
    """Configuración para la búsqueda de hiperparámetros"""
    
    # Rango de parámetros a explorar
    poblacion_size_range: Tuple[int, int] = (50, 300)
    generaciones_range: Tuple[int, int] = (100, 1000)
    prob_cruce_range: Tuple[float, float] = (0.7, 0.95)
    prob_mutacion_range: Tuple[float, float] = (0.1, 0.4)
    elite_range: Tuple[int, int] = (5, 20)
    paciencia_range: Tuple[int, int] = (30, 100)
    workers_range: Tuple[int, int] = (1, 4)
    tournament_size_range: Tuple[int, int] = (2, 6)
    random_immigrants_rate_range: Tuple[float, float] = (0.02, 0.15)
    
    # Pesos del fitness a explorar
    peso_huecos_range: Tuple[float, float] = (5.0, 20.0)
    peso_primeras_ultimas_range: Tuple[float, float] = (3.0, 10.0)
    peso_balance_dia_range: Tuple[float, float] = (2.0, 8.0)
    peso_bloques_semana_range: Tuple[float, float] = (10.0, 25.0)
    
    # Configuración de búsqueda
    max_iteraciones: int = 50
    timeout_por_corrida: int = 300  # 5 minutos por corrida
    semilla_base: int = 42
    num_workers: int = 2
    
    # Criterios de parada
    mejora_minima: float = 0.10  # 10% de mejora mínima
    max_corridas_sin_mejora: int = 10

@dataclass
class ResultadoBusqueda:
    """Resultado de una búsqueda de hiperparámetros"""
    
    configuracion: Dict[str, Any]
    fitness: float
    tiempo_s: float
    generaciones: int
    convergencia: bool
    kpis: Dict[str, Any]
    run_id: str
    timestamp: str

class BuscadorHiperparametros:
    """Buscador de hiperparámetros para el algoritmo genético"""
    
    def __init__(self, config: ConfiguracionBusqueda = None):
        self.config = config or ConfiguracionBusqueda()
        self.resultados: List[ResultadoBusqueda] = []
        self.mejor_resultado: Optional[ResultadoBusqueda] = None
        self.historial_mejoras: List[Tuple[int, float]] = []
    
    def generar_configuracion_aleatoria(self) -> Dict[str, Any]:
        """Genera una configuración aleatoria dentro de los rangos definidos"""
        return {
            'poblacion_size': random.randint(*self.config.poblacion_size_range),
            'generaciones': random.randint(*self.config.generaciones_range),
            'prob_cruce': random.uniform(*self.config.prob_cruce_range),
            'prob_mutacion': random.uniform(*self.config.prob_mutacion_range),
            'elite': random.randint(*self.config.elite_range),
            'paciencia': random.randint(*self.config.paciencia_range),
            'workers': random.randint(*self.config.workers_range),
            'tournament_size': random.randint(*self.config.tournament_size_range),
            'random_immigrants_rate': random.uniform(*self.config.random_immigrants_rate_range),
            'peso_huecos': random.uniform(*self.config.peso_huecos_range),
            'peso_primeras_ultimas': random.uniform(*self.config.peso_primeras_ultimas_range),
            'peso_balance_dia': random.uniform(*self.config.peso_balance_dia_range),
            'peso_bloques_semana': random.uniform(*self.config.peso_bloques_semana_range),
            'semilla': self.config.semilla_base + random.randint(0, 1000),
        }
    
    def generar_configuracion_rejilla(self, paso: float = 0.5) -> List[Dict[str, Any]]:
        """Genera configuraciones en rejilla para exploración sistemática"""
        configuraciones = []
        
        # Parámetros discretos
        poblaciones = list(range(self.config.poblacion_size_range[0], 
                                self.config.poblacion_size_range[1] + 1, 50))
        generaciones = list(range(self.config.generaciones_range[0], 
                                 self.config.generaciones_range[1] + 1, 200))
        elites = list(range(self.config.elite_range[0], 
                           self.config.elite_range[1] + 1, 5))
        workers = list(range(self.config.workers_range[0], 
                            self.config.workers_range[1] + 1, 1))
        tournament_sizes = list(range(self.config.tournament_size_range[0], 
                                     self.config.tournament_size_range[1] + 1, 1))
        
        # Parámetros continuos
        prob_cruces = np.arange(self.config.prob_cruce_range[0], 
                               self.config.prob_cruce_range[1] + paso, paso)
        prob_mutaciones = np.arange(self.config.prob_mutacion_range[0], 
                                   self.config.prob_mutacion_range[1] + paso, paso)
        
        # Generar combinaciones
        for poblacion in poblaciones:
            for generacion in generaciones:
                for elite in elites:
                    for worker in workers:
                        for tournament_size in tournament_sizes:
                            for prob_cruce in prob_cruces:
                                for prob_mutacion in prob_mutaciones:
                                    config = {
                                        'poblacion_size': poblacion,
                                        'generaciones': generacion,
                                        'prob_cruce': prob_cruce,
                                        'prob_mutacion': prob_mutacion,
                                        'elite': elite,
                                        'paciencia': elite * 5,  # Relacionado con elite
                                        'workers': worker,
                                        'tournament_size': tournament_size,
                                        'random_immigrants_rate': 0.05,  # Fijo para rejilla
                                        'peso_huecos': 10.0,  # Pesos fijos para rejilla
                                        'peso_primeras_ultimas': 5.0,
                                        'peso_balance_dia': 3.0,
                                        'peso_bloques_semana': 15.0,
                                        'semilla': self.config.semilla_base,
                                    }
                                    configuraciones.append(config)
        
        return configuraciones
    
    def evaluar_configuracion(self, config: Dict[str, Any]) -> ResultadoBusqueda:
        """Evalúa una configuración específica"""
        inicio = time.time()
        run_id = str(uuid.uuid4())[:8]
        
        try:
            # Crear tracker de corrida
            tracker = TrackerCorrida(
                run_id=run_id,
                semilla=config['semilla'],
                poblacion_size=config['poblacion_size'],
                generaciones=config['generaciones'],
                prob_cruce=config['prob_cruce'],
                prob_mutacion=config['prob_mutacion'],
                elite=config['elite'],
                paciencia=config['paciencia'],
                workers=config['workers'],
                tournament_size=config['tournament_size'],
                random_immigrants_rate=config['random_immigrants_rate'],
                peso_huecos=config['peso_huecos'],
                peso_primeras_ultimas=config['peso_primeras_ultimas'],
                peso_balance_dia=config['peso_balance_dia'],
                peso_bloques_semana=config['peso_bloques_semana'],
            )
            tracker.actualizar_estado_sistema()
            tracker.save()
            
            # Ejecutar algoritmo genético
            resultado = generar_horarios_genetico(
                poblacion_size=config['poblacion_size'],
                generaciones=config['generaciones'],
                prob_cruce=config['prob_cruce'],
                prob_mutacion=config['prob_mutacion'],
                elite=config['elite'],
                paciencia=config['paciencia'],
                workers=config['workers'],
                tournament_size=config['tournament_size'],
                random_immigrants_rate=config['random_immigrants_rate'],
                semilla=config['semilla']
            )
            
            tiempo_total = time.time() - inicio
            
            # Crear resultado de búsqueda
            resultado_busqueda = ResultadoBusqueda(
                configuracion=config,
                fitness=resultado.get('mejor_fitness', float('-inf')),
                tiempo_s=tiempo_total,
                generaciones=resultado.get('generaciones_completadas', 0),
                convergencia=resultado.get('convergencia', False),
                kpis={
                    'num_solapes': resultado.get('metricas', {}).get('num_solapes', 0),
                    'num_huecos': resultado.get('metricas', {}).get('num_huecos', 0),
                    'porcentaje_primeras_ultimas': resultado.get('metricas', {}).get('porcentaje_primeras_ultimas', 0.0),
                    'desviacion_balance_dia': resultado.get('metricas', {}).get('desviacion_balance_dia', 0.0),
                },
                run_id=run_id,
                timestamp=tracker.timestamp_inicio.isoformat()
            )
            
            # Actualizar tracker
            if resultado.get('exito'):
                tracker.marcar_como_exitosa(resultado)
            else:
                tracker.marcar_como_fallida(str(resultado), tiempo_total)
            
            return resultado_busqueda
            
        except Exception as e:
            tiempo_total = time.time() - inicio
            return ResultadoBusqueda(
                configuracion=config,
                fitness=float('-inf'),
                tiempo_s=tiempo_total,
                generaciones=0,
                convergencia=False,
                kpis={},
                run_id=run_id,
                timestamp=time.strftime('%Y-%m-%dT%H:%M:%S'),
            )
    
    def buscar_random(self) -> List[ResultadoBusqueda]:
        """Ejecuta búsqueda aleatoria de hiperparámetros"""
        print(f"🔍 Iniciando búsqueda aleatoria con {self.config.max_iteraciones} iteraciones...")
        
        for i in range(self.config.max_iteraciones):
            print(f"  Iteración {i+1}/{self.config.max_iteraciones}")
            
            # Generar configuración aleatoria
            config = self.generar_configuracion_aleatoria()
            
            # Evaluar configuración
            resultado = self.evaluar_configuracion(config)
            self.resultados.append(resultado)
            
            # Verificar si es el mejor hasta ahora
            if resultado.fitness > (self.mejor_resultado.fitness if self.mejor_resultado else float('-inf')):
                self.mejor_resultado = resultado
                self.historial_mejoras.append((i+1, resultado.fitness))
                print(f"    🎯 Nueva mejor configuración! Fitness: {resultado.fitness:.2f}")
            
            # Verificar criterio de parada
            if self._verificar_criterio_parada():
                print(f"  🛑 Criterio de parada alcanzado en iteración {i+1}")
                break
        
        return self.resultados
    
    def buscar_rejilla(self) -> List[ResultadoBusqueda]:
        """Ejecuta búsqueda en rejilla de hiperparámetros"""
        configuraciones = self.generar_configuracion_rejilla()
        print(f"🔍 Iniciando búsqueda en rejilla con {len(configuraciones)} configuraciones...")
        
        # Ejecutar en paralelo
        with ProcessPoolExecutor(max_workers=self.config.num_workers) as executor:
            futures = {executor.submit(self.evaluar_configuracion, config): config 
                      for config in configuraciones}
            
            for i, future in enumerate(as_completed(futures)):
                resultado = future.result()
                self.resultados.append(resultado)
                
                # Verificar si es el mejor hasta ahora
                if resultado.fitness > (self.mejor_resultado.fitness if self.mejor_resultado else float('-inf')):
                    self.mejor_resultado = resultado
                    self.historial_mejoras.append((i+1, resultado.fitness))
                    print(f"  🎯 Nueva mejor configuración! Fitness: {resultado.fitness:.2f}")
                
                print(f"  Progreso: {i+1}/{len(configuraciones)} - Fitness actual: {resultado.fitness:.2f}")
        
        return self.resultados
    
    def _verificar_criterio_parada(self) -> bool:
        """Verifica si se debe parar la búsqueda"""
        if len(self.historial_mejoras) < 2:
            return False
        
        # Verificar si no hay mejora reciente
        ultimas_mejoras = self.historial_mejoras[-self.config.max_corridas_sin_mejora:]
        if len(ultimas_mejoras) >= self.config.max_corridas_sin_mejora:
            mejora_reciente = max(ultimas_mejoras, key=lambda x: x[1])[1]
            mejora_anterior = self.historial_mejoras[-self.config.max_corridas_sin_mejora-1][1]
            
            if abs(mejora_reciente - mejora_anterior) < self.config.mejora_minima:
                return True
        
        return False
    
    def obtener_mejores_configuraciones(self, limite: int = 5) -> List[ResultadoBusqueda]:
        """Obtiene las mejores configuraciones encontradas"""
        return sorted(self.resultados, key=lambda x: x.fitness, reverse=True)[:limite]
    
    def generar_reporte(self) -> Dict[str, Any]:
        """Genera un reporte completo de la búsqueda"""
        if not self.resultados:
            return {"error": "No hay resultados para reportar"}
        
        # Estadísticas generales
        fitnesses = [r.fitness for r in self.resultados if r.fitness != float('-inf')]
        tiempos = [r.tiempo_s for r in self.resultados]
        generaciones = [r.generaciones for r in self.resultados]
        
        reporte = {
            "resumen": {
                "total_configuraciones": len(self.resultados),
                "configuraciones_exitosas": len(fitnesses),
                "mejor_fitness": max(fitnesses) if fitnesses else float('-inf'),
                "peor_fitness": min(fitnesses) if fitnesses else float('-inf'),
                "fitness_promedio": np.mean(fitnesses) if fitnesses else 0.0,
                "tiempo_total": sum(tiempos),
                "tiempo_promedio": np.mean(tiempos) if tiempos else 0.0,
                "generaciones_promedio": np.mean(generaciones) if generaciones else 0.0,
            },
            "mejor_configuracion": {
                "configuracion": self.mejor_resultado.configuracion if self.mejor_resultado else {},
                "fitness": self.mejor_resultado.fitness if self.mejor_resultado else float('-inf'),
                "kpis": self.mejor_resultado.kpis if self.mejor_resultado else {},
            },
            "top_5_configuraciones": [
                {
                    "posicion": i+1,
                    "fitness": r.fitness,
                    "configuracion": r.configuracion,
                    "kpis": r.kpis,
                }
                for i, r in enumerate(self.obtener_mejores_configuraciones(5))
            ],
            "historial_mejoras": self.historial_mejoras,
            "configuracion_busqueda": {
                "max_iteraciones": self.config.max_iteraciones,
                "timeout_por_corrida": self.config.timeout_por_corrida,
                "mejora_minima": self.config.mejora_minima,
                "max_corridas_sin_mejora": self.config.max_corridas_sin_mejora,
            }
        }
        
        return reporte
    
    def guardar_resultados(self, archivo: str = None) -> str:
        """Guarda los resultados de la búsqueda en un archivo JSON"""
        if archivo is None:
            archivo = f"logs/busqueda_hiperparametros_{time.strftime('%Y%m%d_%H%M%S')}.json"
        
        # Crear directorio si no existe
        import os
        os.makedirs(os.path.dirname(archivo), exist_ok=True)
        
        # Generar reporte y guardar
        reporte = self.generar_reporte()
        
        with open(archivo, 'w', encoding='utf-8') as f:
            json.dump(reporte, f, indent=2, ensure_ascii=False)
        
        print(f"📊 Resultados guardados en: {archivo}")
        return archivo

def ejecutar_busqueda_rapida():
    """Ejecuta una búsqueda rápida de hiperparámetros para demostración"""
    print("🚀 Ejecutando búsqueda rápida de hiperparámetros...")
    
    # Configuración de búsqueda rápida
    config = ConfiguracionBusqueda(
        max_iteraciones=10,
        timeout_por_corrida=60,
        num_workers=1
    )
    
    # Crear buscador
    buscador = BuscadorHiperparametros(config)
    
    # Ejecutar búsqueda aleatoria
    resultados = buscador.buscar_random()
    
    # Generar reporte
    reporte = buscador.generar_reporte()
    
    print("\n📊 REPORTE DE BÚSQUEDA:")
    print(f"  Total configuraciones: {reporte['resumen']['total_configuraciones']}")
    print(f"  Configuraciones exitosas: {reporte['resumen']['configuraciones_exitosas']}")
    print(f"  Mejor fitness: {reporte['resumen']['mejor_fitness']:.2f}")
    print(f"  Tiempo total: {reporte['resumen']['tiempo_total']:.1f}s")
    
    print("\n🏆 TOP 3 CONFIGURACIONES:")
    for i, top in enumerate(reporte['top_5_configuraciones'][:3]):
        print(f"  {i+1}. Fitness: {top['fitness']:.2f}")
        print(f"     Población: {top['configuracion']['poblacion_size']}")
        print(f"     Generaciones: {top['configuracion']['generaciones']}")
        print(f"     Prob. Cruce: {top['configuracion']['prob_cruce']:.2f}")
        print(f"     Prob. Mutación: {top['configuracion']['prob_mutacion']:.2f}")
    
    # Guardar resultados
    archivo = buscador.guardar_resultados()
    
    return resultados, reporte, archivo

if __name__ == "__main__":
    ejecutar_busqueda_rapida() 