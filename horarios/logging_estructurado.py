"""
Módulo de logging estructurado para el algoritmo genético.

Este módulo implementa logging estructurado en JSON para facilitar
el análisis posterior de las ejecuciones del algoritmo.
"""

import json
import time
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from pathlib import Path
import numpy as np

@dataclass
class MetricasGeneracion:
    """Métricas de una generación específica del GA"""
    generacion: int
    timestamp: str
    mejor_fitness: float
    peor_fitness: float
    fitness_promedio: float
    fitness_mediana: float
    fitness_p95: float
    tiempo_generacion_s: float
    intentos_invalidos: int
    repairs_exitosos: int
    diversidad_poblacional: float

@dataclass
class MetricasEjecucion:
    """Métricas completas de una ejecución del GA"""
    # Configuración del algoritmo
    semilla: int
    poblacion_size: int
    generaciones: int
    prob_cruce: float
    prob_mutacion: float
    elite: int
    paciencia: int
    workers: int
    tournament_size: int
    random_immigrants_rate: float
    
    # Pesos del fitness
    peso_huecos: float
    peso_primeras_ultimas: float
    peso_balance_dia: float
    peso_bloques_semana: float
    
    # Resultados finales
    exito: bool
    fitness_final: float
    generaciones_completadas: int
    convergencia: bool
    tiempo_total_s: float
    
    # KPIs de calidad
    num_solapes: int
    num_huecos: int
    porcentaje_primeras_ultimas: float
    desviacion_balance_dia: float
    
    # Estado del sistema
    num_cursos: int
    num_profesores: int
    num_materias: int
    
    # Evolución del algoritmo
    generaciones_metricas: List[MetricasGeneracion]
    
    # Timestamps
    timestamp_inicio: str
    timestamp_fin: str
    comentarios: str = ""
    tags: str = ""
    
    # Campos esperados por tests
    metricas_por_generacion: List[MetricasGeneracion] = None

class LoggerGenetico:
    """
    Logger estructurado para el algoritmo genético.
    Guarda métricas detalladas en formato JSON para análisis posterior.
    """
    
    def __init__(self, archivo_log: str = "logs/ultima_ejecucion.txt"):
        self.archivo_log = archivo_log
        self.metricas_generaciones = []
        self.tiempo_inicio = None
        self.configuracion = {}
        self.metricas_ejecucion = None  # Expuesto para tests
        
        # Crear directorio de logs si no existe
        Path(archivo_log).parent.mkdir(parents=True, exist_ok=True)
        
        # Configurar logging básico
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
    
    def iniciar_ejecucion(self, config: Dict[str, Any], semilla: Optional[int] = None):
        """Inicia el logging de una nueva ejecución (compatible con tests)."""
        self.tiempo_inicio = time.time()
        self.configuracion = config.copy() if config else {}
        if semilla is not None:
            self.configuracion['semilla'] = semilla
        self.metricas_generaciones = []
        
        # Inicializar objeto de métricas visible para tests
        self.metricas_ejecucion = MetricasEjecucion(
            semilla=self.configuracion.get('semilla', 0),
            poblacion_size=self.configuracion.get('poblacion_size', 0),
            generaciones=self.configuracion.get('generaciones', 0),
            prob_cruce=self.configuracion.get('prob_cruce', 0.0),
            prob_mutacion=self.configuracion.get('prob_mutacion', 0.0),
            elite=self.configuracion.get('elite', 0),
            paciencia=self.configuracion.get('paciencia', 0),
            workers=self.configuracion.get('workers', 0),
            tournament_size=self.configuracion.get('tournament_size', 3),
            random_immigrants_rate=self.configuracion.get('random_immigrants_rate', 0.05),
            peso_huecos=self.configuracion.get('peso_huecos', 10.0),
            peso_primeras_ultimas=self.configuracion.get('peso_primeras_ultimas', 5.0),
            peso_balance_dia=self.configuracion.get('peso_balance_dia', 3.0),
            peso_bloques_semana=self.configuracion.get('peso_bloques_semana', 15.0),
            exito=False,
            fitness_final=0.0,
            generaciones_completadas=0,
            convergencia=False,
            tiempo_total_s=0.0,
            num_solapes=0,
            num_huecos=0,
            porcentaje_primeras_ultimas=0.0,
            desviacion_balance_dia=0.0,
            num_cursos=0,
            num_profesores=0,
            num_materias=0,
            generaciones_metricas=[],
            timestamp_inicio=datetime.now().isoformat(),
            timestamp_fin="",
            comentarios="",
            tags="genetic_algorithm,optimization",
            metricas_por_generacion=[]
        )
        
        # Log de inicio
        self._escribir_log({
            "evento": "inicio_ejecucion",
            "timestamp": datetime.now().isoformat(),
            "configuracion": self.configuracion,
            "mensaje": "Iniciando ejecución del algoritmo genético"
        })
        
        self.logger.info(f"Iniciando ejecución con semilla {self.configuracion.get('semilla', 'N/A')}")
    
    def registrar_generacion(
        self, 
        generacion: int, 
        poblacion_fitness: List[float], 
        tiempo_generacion_s: float,
        intentos_invalidos: int = 0,
        repairs_exitosos: int = 0,
        diversidad_poblacional: float = 0.0
    ):
        """Registra métricas de una generación específica (alias para compatibilidad)."""
        if not poblacion_fitness:
            return
        
        # Calcular estadísticas de fitness
        fitness_array = np.array(poblacion_fitness)
        mejor_fitness = float(np.max(fitness_array))
        peor_fitness = float(np.min(fitness_array))
        fitness_promedio = float(np.mean(fitness_array))
        fitness_mediana = float(np.median(fitness_array))
        fitness_p95 = float(np.percentile(fitness_array, 95))
        
        # Crear métricas de la generación
        metricas_gen = MetricasGeneracion(
            generacion=generacion,
            timestamp=datetime.now().isoformat(),
            mejor_fitness=mejor_fitness,
            peor_fitness=peor_fitness,
            fitness_promedio=fitness_promedio,
            fitness_mediana=fitness_mediana,
            fitness_p95=fitness_p95,
            tiempo_generacion_s=tiempo_generacion_s,
            intentos_invalidos=intentos_invalidos,
            repairs_exitosos=repairs_exitosos,
            diversidad_poblacional=diversidad_poblacional
        )
        
        self.metricas_generaciones.append(metricas_gen)
        if self.metricas_ejecucion:
            self.metricas_ejecucion.metricas_por_generacion.append(metricas_gen)
            self.metricas_ejecucion.generaciones_completadas = max(
                self.metricas_ejecucion.generaciones_completadas, generacion
            )
            self.metricas_ejecucion.fitness_final = mejor_fitness
        
        # Log de la generación
        self._escribir_log({
            "evento": "generacion",
            "generacion": generacion,
            "timestamp": datetime.now().isoformat(),
            "metricas": asdict(metricas_gen)
        })
        
        if generacion % 10 == 0:
            self.logger.info(
                f"Gen {generacion}: Mejor={mejor_fitness:.2f}, Promedio={fitness_promedio:.2f}, Tiempo={tiempo_generacion_s:.2f}s"
            )
    
    def registrar_resultado_final(
        self, 
        resultado_final: Dict[str, Any], 
        convergencia: bool = False,
        exito: bool = None,
        mensaje: str = "Ejecución finalizada"
    ):
        """Finaliza el logging de la ejecución (alias compatible con tests)."""
        # Armonizar flags
        if exito is not None:
            resultado_final = {**resultado_final, 'exito': exito}
        tiempo_total = time.time() - self.tiempo_inicio if self.tiempo_inicio else 0
        
        # Permitir estructura 'metricas' anidada en resultado_final
        metricas = resultado_final.get('metricas', {})
        
        metricas_ejecucion = MetricasEjecucion(
            # Configuración
            semilla=self.configuracion.get('semilla', 0),
            poblacion_size=self.configuracion.get('poblacion_size', 0),
            generaciones=self.configuracion.get('generaciones', 0),
            prob_cruce=self.configuracion.get('prob_cruce', 0.0),
            prob_mutacion=self.configuracion.get('prob_mutacion', 0.0),
            elite=self.configuracion.get('elite', 0),
            paciencia=self.configuracion.get('paciencia', 0),
            workers=self.configuracion.get('workers', 0),
            tournament_size=self.configuracion.get('tournament_size', 3),
            random_immigrants_rate=self.configuracion.get('random_immigrants_rate', 0.05),
            
            # Pesos del fitness
            peso_huecos=self.configuracion.get('peso_huecos', 10.0),
            peso_primeras_ultimas=self.configuracion.get('peso_primeras_ultimas', 5.0),
            peso_balance_dia=self.configuracion.get('peso_balance_dia', 3.0),
            peso_bloques_semana=self.configuracion.get('peso_bloques_semana', 15.0),
            
            # Resultados
            exito=resultado_final.get('exito', False),
            fitness_final=resultado_final.get('mejor_fitness', resultado_final.get('mejor_fitness_final', 0.0)),
            generaciones_completadas=resultado_final.get('generaciones_completadas', self.metricas_ejecucion.generaciones_completadas if self.metricas_ejecucion else 0),
            convergencia=convergencia,
            tiempo_total_s=tiempo_total,
            
            # KPIs de calidad
            num_solapes=metricas.get('num_solapes', resultado_final.get('num_solapes', 0)),
            num_huecos=metricas.get('num_huecos', resultado_final.get('num_huecos', 0)),
            porcentaje_primeras_ultimas=metricas.get('porcentaje_primeras_ultimas', resultado_final.get('porcentaje_primeras_ultimas', 0.0)),
            desviacion_balance_dia=metricas.get('desviacion_balance_dia', resultado_final.get('desviacion_balance_dia', 0.0)),
            
            # Estado del sistema
            num_cursos=resultado_final.get('num_cursos', 0),
            num_profesores=resultado_final.get('num_profesores', 0),
            num_materias=resultado_final.get('num_materias', 0),
            
            # Evolución
            generaciones_metricas=self.metricas_generaciones,
            
            # Timestamps
            timestamp_inicio=datetime.fromtimestamp(self.tiempo_inicio).isoformat() if self.tiempo_inicio else "",
            timestamp_fin=datetime.now().isoformat(),
            
            # Metadata
            comentarios=mensaje,
            tags="genetic_algorithm,optimization",
            metricas_por_generacion=self.metricas_generaciones
        )
        
        # Mantener accesible para asserts de tests
        self.metricas_ejecucion = metricas_ejecucion
        
        self._escribir_log({
            "evento": "fin_ejecucion",
            "timestamp": datetime.now().isoformat(),
            "tiempo_total_s": tiempo_total,
            "exito": metricas_ejecucion.exito,
            "fitness_final": metricas_ejecucion.fitness_final,
            "mensaje": mensaje
        })
        
        self.logger.info(
            f"Ejecución finalizada: {'✅ ÉXITO' if metricas_ejecucion.exito else '❌ FALLO'} - Fitness: {metricas_ejecucion.fitness_final:.2f} - Tiempo: {tiempo_total:.2f}s"
        )
        
        self._guardar_metricas_completas(metricas_ejecucion)

    # Aliases antiguos para compatibilidad
    def log_generacion(self, *args, **kwargs):
        return self.registrar_generacion(*args, **kwargs)
    
    def finalizar_ejecucion(self, *args, **kwargs):
        return self.registrar_resultado_final(*args, **kwargs)

    def log_evento(self, evento: str, datos: Dict[str, Any] = None):
        """Registra un evento específico"""
        log_data = {
            "evento": evento,
            "timestamp": datetime.now().isoformat(),
            "datos": datos or {}
        }
        
        self._escribir_log(log_data)
        self.logger.info(f"Evento: {evento} - {datos}")

    # Atajos específicos para esta app
    def log_dimensiones(self, dimensiones: Dict[str, Any]):
        self.log_evento("dimensiones", dimensiones)

    def log_oferta_vs_demanda(self, tabla_y_resumen: Dict[str, Any]):
        # No incluir nombres; solo ids y métricas
        self.log_evento("oferta_vs_demanda", tabla_y_resumen)

    def log_auditoria_mascaras(self, muestra: List[Dict[str, Any]]):
        self.log_evento("auditoria_mascaras", {"muestra": muestra})

    def log_individuo0_diferencias(self, diferencias: List[Dict[str, Any]]):
        self.log_evento("individuo0_diferencias", {"diferencias": diferencias})

    def log_repair_resumen(self, resumen: Dict[str, Any]):
        self.log_evento("repair_resumen", resumen)

    def log_top_slots_escasez(self, top_slots: List[Dict[str, Any]]):
        self.log_evento("top_slots_escasez", {"top": top_slots})

    def log_estado_final(self, estado: Dict[str, Any]):
        self.log_evento("estado_final", estado)
    
    def log_error(self, error: str, contexto: Dict[str, Any] = None):
        """Registra un error con contexto"""
        log_data = {
            "evento": "error",
            "timestamp": datetime.now().isoformat(),
            "error": error,
            "contexto": contexto or {}
        }
        
        self._escribir_log(log_data)
        self.logger.error(f"Error: {error} - Contexto: {contexto}")
    
    def _escribir_log(self, data: Dict):
        """Escribe un log en formato JSON"""
        try:
            with open(self.archivo_log, 'a', encoding='utf-8') as f:
                f.write(json.dumps(data, ensure_ascii=False, default=str) + '\n')
        except Exception as e:
            self.logger.error(f"No se pudo escribir en archivo de log: {e}")
    
    def _guardar_metricas_completas(self, metricas: MetricasEjecucion):
        """Guarda métricas completas en archivo separado para análisis"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            archivo_metricas = f"logs/metricas_ejecucion_{timestamp}.json"
            
            with open(archivo_metricas, 'w', encoding='utf-8') as f:
                json.dump(asdict(metricas), f, ensure_ascii=False, indent=2, default=str)
            
            self.logger.info(f"Métricas completas guardadas en: {archivo_metricas}")
            
        except Exception as e:
            self.logger.error(f"No se pudieron guardar métricas completas: {e}")
    
    def obtener_resumen_ejecucion(self) -> Dict[str, Any]:
        """Obtiene un resumen de la ejecución actual"""
        if not self.metricas_generaciones:
            return {"estado": "sin_datos"}
        
        ultima_gen = self.metricas_generaciones[-1]
        
        return {
            "generaciones_completadas": len(self.metricas_generaciones),
            "ultima_generacion": ultima_gen.generacion,
            "mejor_fitness_actual": ultima_gen.mejor_fitness,
            "fitness_promedio_actual": ultima_gen.fitness_promedio,
            "tiempo_transcurrido": time.time() - self.tiempo_inicio if self.tiempo_inicio else 0,
            "diversidad_actual": ultima_gen.diversidad_poblacional
        }
    
    def limpiar_logs_antiguos(self, dias_antiguedad: int = 30):
        """Limpia logs antiguos para evitar acumulación"""
        try:
            from pathlib import Path
            import os
            
            directorio_logs = Path(self.archivo_log).parent
            tiempo_limite = time.time() - (dias_antiguedad * 24 * 3600)
            
            archivos_eliminados = 0
            for archivo in directorio_logs.glob("*.json"):
                if archivo.stat().st_mtime < tiempo_limite:
                    archivo.unlink()
                    archivos_eliminados += 1
            
            if archivos_eliminados > 0:
                self.logger.info(f"Eliminados {archivos_eliminados} logs antiguos")
                
        except Exception as e:
            self.logger.error(f"Error limpiando logs antiguos: {e}")

def crear_logger_genetico(archivo_log: str = None) -> LoggerGenetico:
    """Función de conveniencia para crear un logger genético"""
    if archivo_log is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        archivo_log = f"logs/ultima_ejecucion_{timestamp}.txt"
    
    return LoggerGenetico(archivo_log)

def analizar_logs_ejecucion(archivo_log: str) -> Dict[str, Any]:
    """
    Analiza logs de una ejecución para generar reportes.
    Retorna métricas agregadas y análisis de tendencias.
    """
    try:
        metricas_generaciones = []
        eventos = []
        
        with open(archivo_log, 'r', encoding='utf-8') as f:
            for linea in f:
                try:
                    data = json.loads(linea.strip())
                    if data.get('evento') == 'generacion':
                        metricas_generaciones.append(data['metricas'])
                    eventos.append(data)
                except json.JSONDecodeError:
                    continue
        
        if not metricas_generaciones:
            return {"error": "No se encontraron métricas de generaciones"}
        
        # Análisis de tendencias
        fitness_evolucion = [m['mejor_fitness'] for m in metricas_generaciones]
        tiempos_generacion = [m['tiempo_generacion_s'] for m in metricas_generaciones]
        
        # Calcular mejoras
        mejoras_por_generacion = []
        for i in range(1, len(fitness_evolucion)):
            mejora = fitness_evolucion[i] - fitness_evolucion[i-1]
            mejoras_por_generacion.append(mejora)
        
        return {
            "total_generaciones": len(metricas_generaciones),
            "fitness_inicial": fitness_evolucion[0],
            "fitness_final": fitness_evolucion[-1],
            "mejora_total": fitness_evolucion[-1] - fitness_evolucion[0],
            "mejora_promedio_por_gen": np.mean(mejoras_por_generacion) if mejoras_por_generacion else 0,
            "tiempo_total_generaciones": sum(tiempos_generacion),
            "tiempo_promedio_por_gen": np.mean(tiempos_generacion),
            "convergencia_detectada": len([m for m in mejoras_por_generacion if m > 0]) < len(mejoras_por_generacion) * 0.1
        }
        
    except Exception as e:
        return {"error": f"Error analizando logs: {str(e)}"} 