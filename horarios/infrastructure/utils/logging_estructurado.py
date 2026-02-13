"""
Módulo de logging estructurado para el motor de generación de horarios.

Este módulo implementa logging estructurado en JSON para facilitar
el análisis posterior de las ejecuciones del algoritmo Demand-First.
"""

import json
import time
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from pathlib import Path
import numpy as np
import sentry_sdk

@dataclass
class MetricasFase:
    """Métricas de una fase específica de la generación"""
    fase: str  # 'construccion', 'mejora', 'validacion'
    timestamp: str
    duracion_s: float
    items_procesados: int  # slots, cursos, etc.
    exito: bool
    detalles: Dict[str, Any]

@dataclass
class MetricasEjecucion:
    """Métricas completas de una ejecución del motor"""
    # Configuración
    semilla: int
    configuracion: Dict[str, Any]
    
    # Resultados finales
    exito: bool
    calidad_final: float
    tiempo_total_s: float
    
    # KPIs de calidad
    slots_generados: int
    cursos_completos: int
    profesores_usados: int
    violaciones_duras: int
    violaciones_suaves: int
    
    # Fases
    fases: List[MetricasFase]
    
    # Timestamps
    timestamp_inicio: str
    timestamp_fin: str
    tags: str = "demand_first,optimization"

class LoggerEstructurado:
    """
    Logger estructurado para el motor de horarios.
    Guarda métricas detalladas en formato JSON para análisis posterior.
    """
    
    def __init__(self, archivo_log: str = "logs/ultima_ejecucion.txt"):
        self.archivo_log = archivo_log
        self.fases = []
        self.tiempo_inicio = None
        self.configuracion = {}
        self.metricas_ejecucion = None
        
        # Crear directorio de logs si no existe
        Path(archivo_log).parent.mkdir(parents=True, exist_ok=True)
        
        # Configurar logging básico
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
    
    def iniciar_ejecucion(self, config: Dict[str, Any], semilla: Optional[int] = None):
        """Inicia el logging de una nueva ejecución."""
        self.tiempo_inicio = time.time()
        self.configuracion = config.copy() if config else {}
        if semilla is not None:
            self.configuracion['semilla'] = semilla
        self.fases = []
        
        # Log de inicio
        self._escribir_log({
            "evento": "inicio_ejecucion",
            "timestamp": datetime.now().isoformat(),
            "configuracion": self.configuracion,
            "mensaje": "Iniciando ejecución del motor de horarios"
        })
        
        self.logger.info(f"Iniciando ejecución con semilla {self.configuracion.get('semilla', 'N/A')}")
    
    def registrar_fase(self, fase: str, duracion: float, items: int, exito: bool, detalles: Dict = None):
        """Registra métricas de una fase completada."""
        metricas = MetricasFase(
            fase=fase,
            timestamp=datetime.now().isoformat(),
            duracion_s=duracion,
            items_procesados=items,
            exito=exito,
            detalles=detalles or {}
        )
        self.fases.append(metricas)
        
        self._escribir_log({
            "evento": "fase_completada",
            "fase": fase,
            "metricas": asdict(metricas)
        })
        
        self.logger.info(f"Fase {fase}: Éxito={exito}, Tiempo={duracion:.2f}s, Items={items}")

    def registrar_resultado_final(
        self, 
        resultado: Dict[str, Any], 
        exito: bool = None
    ):
        """Finaliza el logging de la ejecución."""
        if exito is not None:
            resultado['exito'] = exito
            
        tiempo_total = time.time() - self.tiempo_inicio if self.tiempo_inicio else 0
        estadisticas = resultado.get('estadisticas', {})
        
        self.metricas_ejecucion = MetricasEjecucion(
            semilla=self.configuracion.get('semilla', 0),
            configuracion=self.configuracion,
            exito=bool(resultado.get('exito', False)),
            calidad_final=float(resultado.get('calidad', 0.0)),
            tiempo_total_s=float(resultado.get('tiempo_total', tiempo_total)),
            slots_generados=int(estadisticas.get('slots_generados', 0)),
            cursos_completos=int(estadisticas.get('cursos_completos', 0)),
            profesores_usados=int(estadisticas.get('profesores_activos', 0)),
            violaciones_duras=int(estadisticas.get('violaciones_criticas', 0)),
            violaciones_suaves=int(estadisticas.get('violaciones_suaves', 0)),
            fases=self.fases,
            timestamp_inicio=datetime.fromtimestamp(self.tiempo_inicio).isoformat() if self.tiempo_inicio else datetime.now().isoformat(),
            timestamp_fin=datetime.now().isoformat()
        )
        
        # Log final
        self._escribir_log({
            "evento": "fin_ejecucion",
            "timestamp": datetime.now().isoformat(),
            "resultado": resultado,
            "resumen": asdict(self.metricas_ejecucion)
        })
        
        self.logger.info(f"Ejecución finalizada. Éxito={self.metricas_ejecucion.exito}, Tiempo={self.metricas_ejecucion.tiempo_total_s:.2f}s")

    def log_evento(self, evento: str, datos: Dict[str, Any] = None):
        """Registra un evento específico"""
        log_data = {
            "evento": evento,
            "timestamp": datetime.now().isoformat(),
            "datos": datos or {}
        }
        
        self._escribir_log(log_data)
        self.logger.info(f"Evento: {evento}")
    
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
        """Escribe un log en formato JSON y lo envía a Sentry como breadcrumb"""
        try:
            # 1. Escribir en archivo local
            with open(self.archivo_log, 'a', encoding='utf-8') as f:
                f.write(json.dumps(data, ensure_ascii=False, default=str) + '\n')
            
            # 2. Enviar a Sentry (Breadcrumb para trazabilidad)
            category = data.get("evento", "log")
            level = "error" if category == "error" else "info"
            sentry_sdk.add_breadcrumb(
                category=category,
                message=data.get("mensaje") or f"Evento: {category}",
                data=data,
                level=level
            )

        except Exception as e:
            self.logger.error(f"No se pudo escribir en archivo de log: {e}")

# Funciones de conveniencia y compatibilidad
def crear_logger_estructurado(archivo_log: str = None) -> LoggerEstructurado:
    """Crea una instancia del logger estructurado"""
    if archivo_log is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        archivo_log = f"logs/ejecucion_{timestamp}.txt"
    
    return LoggerEstructurado(archivo_log)


