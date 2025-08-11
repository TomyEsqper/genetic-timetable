from horarios.models import Horario
from .genetico import generar_horarios_genetico_robusto

def generar_horarios_genetico(
    poblacion_size: int = 100,
    generaciones: int = 500,
    prob_cruce: float = 0.85,
    prob_mutacion: float = 0.25,
    elite: int = 4,
    paciencia: int = 25,
    timeout_seg: int = 180,
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
