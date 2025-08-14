"""Módulo de tareas asíncronas para la generación de horarios.

Este módulo prepara la integración con Celery para ejecutar la generación de horarios
como tareas asíncronas, permitiendo escalar horizontalmente el procesamiento.

Nota: Para usar este módulo, es necesario instalar Celery y configurar un broker como Redis.

Ejemplo de configuración en settings.py:
    CELERY_BROKER_URL = 'redis://localhost:6379/0'
    CELERY_RESULT_BACKEND = 'redis://localhost:6379/0'

Para activar Celery, es necesario crear un archivo celery.py en el directorio del proyecto
y configurar la aplicación Celery.
"""

import logging
import time
from typing import Dict, Any, Optional, List, Tuple

# Importación condicional de Celery
try:
    from celery import shared_task
    CELERY_AVAILABLE = True
    logging.info("Celery está disponible para tareas asíncronas")
except ImportError:
    # Definimos un decorador de reemplazo si Celery no está disponible
    def shared_task(func=None, **kwargs):
        """Decorador de reemplazo cuando Celery no está disponible."""
        def decorator(f):
            return f
        return decorator if func is None else decorator(func)
    CELERY_AVAILABLE = False
    logging.warning("Celery no está disponible. Las tareas se ejecutarán de forma síncrona.")

# Importamos el generador de horarios
from horarios.genetico import generar_horarios_genetico
from horarios.models import ConfiguracionColegio


@shared_task(bind=True, name='horarios.generar_horarios_async')
def generar_horarios_async(self, colegio_id: int, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
	"""Tarea asíncrona para generar horarios escolares.
	
	Esta función es un wrapper para generar_horarios_genetico que puede ejecutarse
	como una tarea de Celery. Si Celery no está disponible, se ejecutará de forma síncrona.
	"""
	start_time = time.time()
	logging.info(f"Iniciando generación asíncrona de horarios para colegio ID: {colegio_id}")
	default_params = {
		'tamano_poblacion': 100,
		'num_generaciones': 100,
		'probabilidad_mutacion': 0.1,
		'elitismo': 0.1,
		'semilla': None,
		'modo_debug': False
	}
	if params is None:
		params = {}
	params = {**default_params, **params}
	try:
		# Estado: en-cola -> corriendo
		if CELERY_AVAILABLE and hasattr(self, 'update_state'):
			self.update_state(state='STARTED', meta={'status': 'corriendo'})
		# Ejecutar GA (wrapped)
		resultado = generar_horarios_genetico(
			poblacion_size=params.get('tamano_poblacion', 100),
			generaciones=params.get('num_generaciones', 100),
			prob_cruce=0.85,
			prob_mutacion=params.get('probabilidad_mutacion', 0.1),
			elite=max(1, int(params.get('elitismo', 0.1) * params.get('tamano_poblacion', 100))),
			timeout_seg= params.get('timeout_seg', 300),
			semilla=params.get('semilla', None),
			workers=params.get('workers', 1)
		)
		if CELERY_AVAILABLE and hasattr(self, 'update_state'):
			self.update_state(state='PROGRESS', meta={'status': 'mejor-hasta-ahora', 'timeout': bool(resultado.get('timeout', False)), 'mejor_fitness': resultado.get('mejor_fitness')})
		elapsed_time = time.time() - start_time
		return {
			'status': 'success' if resultado.get('exito') else 'error',
			'colegio_id': colegio_id,
			'tiempo_ejecucion': elapsed_time,
			'fitness_final': resultado.get('mejor_fitness', 0),
			'conflictos': resultado.get('conflictos_finales', 0),
			'generaciones': resultado.get('generaciones_completadas', 0),
			'horarios_generados': len(resultado.get('horarios', [])),
			'timeout': bool(resultado.get('timeout', False)),
		}
	except Exception as e:
		logging.error(f"Error en generación asíncrona de horarios: {str(e)}")
		return {
			'status': 'error',
			'colegio_id': colegio_id,
			'error': str(e),
			'tiempo_ejecucion': time.time() - start_time
		}


def ejecutar_generacion_horarios(colegio_id: int, async_mode: bool = False, 
                               params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Función de conveniencia para ejecutar la generación de horarios.
    
    Esta función decide si ejecutar la generación de forma síncrona o asíncrona
    según el parámetro async_mode y la disponibilidad de Celery.
    
    Args:
        colegio_id: ID del colegio para el que se generarán los horarios
        async_mode: Si es True, intenta ejecutar de forma asíncrona (requiere Celery)
        params: Parámetros adicionales para el algoritmo genético
        
    Returns:
        En modo síncrono: Dict con información sobre el resultado de la generación
        En modo asíncrono: Dict con información sobre la tarea creada
    """
    if async_mode and CELERY_AVAILABLE:
        # Ejecutar de forma asíncrona
        task = generar_horarios_async.delay(colegio_id, params)
        return {
            'status': 'task_created',
            'task_id': task.id,
            'colegio_id': colegio_id
        }
    else:
        # Ejecutar de forma síncrona
        if async_mode and not CELERY_AVAILABLE:
            logging.warning("Celery no está disponible. Ejecutando de forma síncrona.")
        return generar_horarios_async(None, colegio_id, params)