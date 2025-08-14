from horarios.models import Horario, Profesor, Materia, Curso, Aula, BloqueHorario, MateriaGrado, MateriaProfesor, DisponibilidadProfesor, ConfiguracionColegio
from django.conf import settings
import os
import logging
# Usar la función que ya persiste resultados en BD
from .genetico import generar_horarios_genetico as _generar_y_persistir
from .validadores import prevalidar_factibilidad_dataset

logger = logging.getLogger(__name__)

def validar_prerrequisitos_criticos():
    """
    Validaciones imprescindibles que cortan antes de ejecutar el algoritmo genético.
    Retorna lista de errores. Si está vacía, se puede proceder.
    """
    errores = []
    
    # 1. Profesores sin disponibilidad
    profesores_sin_disponibilidad = Profesor.objects.exclude(
        id__in=DisponibilidadProfesor.objects.values_list('profesor', flat=True)
    )
    if profesores_sin_disponibilidad.exists():
        nombres = [p.nombre for p in profesores_sin_disponibilidad]
        errores.append(f"Profesores sin disponibilidad: {', '.join(nombres)}")
    
    # 2. Materias del plan sin profesores habilitados
    materias_sin_profesor = MateriaGrado.objects.exclude(
        materia__in=MateriaProfesor.objects.values_list('materia', flat=True)
    )
    if materias_sin_profesor.exists():
        nombres = [f"{mg.materia.nombre} ({mg.grado.nombre})" for mg in materias_sin_profesor]
        errores.append(f"Materias sin profesor: {', '.join(nombres)}")
    
    # 3. Bloques por semana inviables: validar solo que sean valores no negativos
    for mg in MateriaGrado.objects.all():
        if mg.materia.bloques_por_semana < 0:
            errores.append(f"Materia {mg.materia.nombre} tiene bloques_por_semana negativo")
    
    # 4. Bloques no tipo "clase" pueden existir (descanso/almuerzo). No es error previo.
    
    # 5. Aula fija no asignada a un curso
    aulas_fijas_sin_curso = Aula.objects.filter(
        id__in=Curso.objects.values_list('aula_fija', flat=True)
    ).exclude(
        id__in=Curso.objects.values_list('aula_fija', flat=True).filter(aula_fija__isnull=False)
    )
    if aulas_fijas_sin_curso.exists():
        errores.append("Hay inconsistencias en la asignación de aulas fijas")
    
    # 6. La factibilidad global se valida con oferta vs demanda por materia antes del GA
    
    return errores

def generar_horarios_genetico(
    poblacion_size: int = None,
    generaciones: int = None,
    prob_cruce: float = 0.85,
    prob_mutacion: float = 0.25,
    elite: int = None,
    paciencia: int = None,
    timeout_seg: int = None,
    semilla: int = 42,
    workers: int = None,
    tournament_size: int = 3,
    random_immigrants_rate: float = 0.05
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
        tournament_size: Tamaño del torneo para selección (default: 3)
        random_immigrants_rate: Porcentaje de inmigrantes aleatorios (default: 0.05)
        
    Returns:
        Diccionario con métricas y resultados
    """
    
    try:
        # Modo rápido para desarrollo
        if settings.DEBUG or os.environ.get('HORARIOS_FAST') == '1':
            # Aplicar defaults conservadores solo si no fueron especificados explícitamente
            if poblacion_size is None:
                poblacion_size = 30
            if generaciones is None:
                generaciones = 80
            if elite is None:
                elite = 2
            if paciencia is None:
                paciencia = 12
            if workers is None:
                workers = 1
            if timeout_seg is None:
                timeout_seg = 45
            
            logger.info(f"Modo rápido activado: población={poblacion_size}, generaciones={generaciones}, elite={elite}, workers={workers}")
        else:
            # Defaults optimizados para producción
            if poblacion_size is None:
                poblacion_size = 200  # Aumentado para mejor exploración
            if generaciones is None:
                generaciones = 800     # Aumentado para convergencia
            if elite is None:
                elite = 10             # 5% de élite
            if paciencia is None:
                paciencia = 50         # Más paciencia para evitar convergencia prematura
            if timeout_seg is None:
                timeout_seg = 900      # 15 minutos máximo
            if workers is None:
                workers = min(4, os.cpu_count())  # Usar hasta 4 cores
        
        # Prevalidación data-driven (oferta vs demanda)
        pre = prevalidar_factibilidad_dataset()
        if not pre.get('viable', False):
            return {
                'status': 'error',
                'mensaje': 'instancia_inviable',
                'oferta_vs_demanda': pre.get('oferta_vs_demanda', {}),
            }

        # Ejecutar usando la función que ya persiste en BD
        resultado = _generar_y_persistir(
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
        
        # Verificar que el resultado no sea None
        if resultado is None:
            logger.error("La función _generar_y_persistir retornó None")
            return {
                'status': 'error',
                'mensaje': 'Error interno: la generación de horarios falló inesperadamente',
                'error': 'resultado_none'
            }
        
        # Adjuntar tabla oferta_vs_demanda para trazabilidad
        if isinstance(resultado, dict):
            resultado['oferta_vs_demanda'] = prevalidar_factibilidad_dataset()
        return resultado
        
    except Exception as e:
        logger.error(f"Error inesperado en generar_horarios_genetico: {str(e)}")
        import traceback
        logger.error(f"Traceback completo: {traceback.format_exc()}")
        return {
            'status': 'error',
            'mensaje': f'Error interno: {str(e)}',
            'error': 'excepcion_inesperada',
            'traceback': traceback.format_exc()
        }
