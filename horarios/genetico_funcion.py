from horarios.models import Horario
from django.conf import settings
import os
from .genetico import generar_horarios_genetico_robusto

def generar_horarios_genetico(
    poblacion_size: int = None,
    generaciones: int = None,
    prob_cruce: float = 0.85,
    prob_mutacion: float = 0.25,
    elite: int = None,
    paciencia: int = None,
    timeout_seg: int = None,
    semilla: int = 42,
    workers: int = None
):
    """
    Función principal para generar horarios utilizando el algoritmo genético robusto.
    
    Args:
        poblacion_size: Tamaño de la población
        generaciones: Número máximo de generaciones
        prob_cruce: Probabilidad de cruce
        prob_mutacion: Probabilidad de mutación
        elite: Número de individuos de élite
        paciencia: Generaciones sin mejora antes de early stopping
        timeout_seg: Timeout en segundos
        semilla: Semilla para reproducibilidad
        workers: Número de workers para paralelización
        
    Returns:
        Diccionario con métricas y resultados
    """
    
    # Modo rápido para desarrollo
    if settings.DEBUG or os.environ.get('HORARIOS_FAST') == '1':
        # Aplicar defaults conservadores solo si no fueron especificados explícitamente
        if poblacion_size is None:
            poblacion_size = 40
        if generaciones is None:
            generaciones = 120
        if elite is None:
            elite = 2
        if paciencia is None:
            paciencia = 15
        if workers is None:
            workers = 2
        if timeout_seg is None:
            timeout_seg = 60
        
        print(f"🚀 Modo rápido activado: población={poblacion_size}, generaciones={generaciones}, elite={elite}, workers={workers}")
    else:
        # Defaults normales para producción
        if poblacion_size is None:
            poblacion_size = 100
        if generaciones is None:
            generaciones = 500
        if elite is None:
            elite = 4
        if paciencia is None:
            paciencia = 25
        if timeout_seg is None:
            timeout_seg = 180
    
    return generar_horarios_genetico_robusto(
        poblacion_size=poblacion_size,
        generaciones=generaciones,
        prob_cruce=prob_cruce,
        prob_mutacion=prob_mutacion,
        elite=elite,
        paciencia=paciencia,
        timeout_seg=timeout_seg,
        semilla=semilla,
        workers=workers
    )
