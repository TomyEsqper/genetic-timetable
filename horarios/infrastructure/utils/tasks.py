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
from horarios.application.services.generador_demand_first import GeneradorDemandFirst
from horarios.models import ConfiguracionColegio, Horario, Curso, Materia, Profesor, Aula, BloqueHorario
from django.db import transaction

def persistir_resultado_async(resultado: Dict[str, Any]) -> int:
    """Persiste los resultados de la generación en la base de datos."""
    try:
        with transaction.atomic():
            # Estrategia: Borrar horarios de los cursos afectados y recrearlos
            cursos_afectados = set([h['curso_id'] for h in resultado.get('horarios', []) if 'curso_id' in h])
            
            if not cursos_afectados:
                return 0
                
            # Limpiar horarios anteriores de estos cursos
            Horario.objects.filter(curso_id__in=cursos_afectados).delete()
            
            # Crear nuevos objetos
            objetos = []
            for h in resultado.get('horarios', []):
                objetos.append(Horario(
                    curso_id=h['curso_id'], 
                    materia_id=h['materia_id'], 
                    profesor_id=h['profesor_id'],
                    aula_id=h.get('aula_id'), 
                    dia=h['dia'], 
                    bloque=h['bloque']
                ))
            
            Horario.objects.bulk_create(objetos, batch_size=1000)
            return len(objetos)
    except Exception as e:
        logging.error(f"Error persistiendo resultados en tarea asíncrona: {e}")
        raise e


@shared_task(bind=True, name='horarios.generar_horarios_async')
def generar_horarios_async(self, colegio_id: int, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Tarea asíncrona para generar horarios escolares (Demand-First).
    
    Esta función es un wrapper para GeneradorDemandFirst que puede ejecutarse
    como una tarea de Celery. Si Celery no está disponible, se ejecutará de forma síncrona.
    """
    start_time = time.time()
    logging.info(f"Iniciando generación asíncrona de horarios para colegio ID: {colegio_id}")
    
    default_params = {
        'max_iteraciones': 1000,
        'paciencia': 100,
        'semilla': None
    }
    if params is None:
        params = {}
    
    # Mapeo de parámetros antiguos a nuevos
    run_params = {
        'max_iteraciones': params.get('num_generaciones', default_params['max_iteraciones']),
        'paciencia': params.get('paciencia', default_params['paciencia']),
        'semilla': params.get('semilla', default_params['semilla'])
    }
    
    try:
        # Estado: en-cola -> corriendo
        if CELERY_AVAILABLE and hasattr(self, 'update_state') and self.request.id:
            self.update_state(state='STARTED', meta={'status': 'corriendo'})
        
        # Ejecutar Generador
        generador = GeneradorDemandFirst()
        resultado = generador.generar_horarios(**run_params)
        
        # PERSISTENCIA AUTOMÁTICA
        registros_guardados = 0
        if resultado.get('exito'):
            try:
                registros_guardados = persistir_resultado_async(resultado)
                logging.info(f"Tarea asíncrona: Guardados {registros_guardados} horarios.")
            except Exception as e:
                logging.error(f"Error guardando resultados: {e}")
                resultado['exito'] = False
                resultado['error_persistencia'] = str(e)

        if CELERY_AVAILABLE and hasattr(self, 'update_state') and self.request.id:
            self.update_state(state='SUCCESS', meta={'status': 'terminado', 'exito': resultado.get('exito')})
        
        elapsed_time = time.time() - start_time
        return {
            'status': 'success' if resultado.get('exito') else 'error',
            'colegio_id': colegio_id,
            'tiempo_ejecucion': elapsed_time,
            'calidad_final': resultado.get('calidad', 0),
            'slots_generados': resultado.get('estadisticas', {}).get('slots_generados', 0),
            'horarios_generados': registros_guardados, # Retornamos los guardados en BD
            'exito': resultado.get('exito', False),
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
        try:
            task = generar_horarios_async.delay(colegio_id, params)
            return {
                'status': 'task_created',
                'task_id': task.id,
                'colegio_id': colegio_id
            }
        except Exception as e:
            logging.error(f"Error conectando con broker Celery: {e}. Ejecutando síncronamente.")
            # Fallback a síncrono
            if CELERY_AVAILABLE:
                return generar_horarios_async(colegio_id, params)
            return generar_horarios_async(None, colegio_id, params)
    else:
        # Ejecutar de forma síncrona
        if async_mode and not CELERY_AVAILABLE:
            logging.warning("Celery no está disponible. Ejecutando de forma síncrona.")
        
        if CELERY_AVAILABLE:
            return generar_horarios_async(colegio_id, params)
        return generar_horarios_async(None, colegio_id, params)