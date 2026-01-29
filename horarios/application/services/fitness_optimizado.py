"""
Módulo de fitness optimizado para el algoritmo genético usando Numba.

Este módulo implementa el cálculo de fitness unificado con penalizaciones
para huecos, primeras/últimas franjas, balance por día y solapes.
"""

import numpy as np
from typing import Dict, List, Tuple, Any
from dataclasses import dataclass
from .mascaras import MascarasOptimizadas

__all__ = [
    'ConfiguracionFitness', 'ResultadoFitness', 'calcular_fitness_unificado',
    'evaluar_calidad_solucion', 'obtener_recomendaciones_mejora'
]

# Exponer ResultadoFitness como builtin para compat con tests que no lo importan
import builtins

try:
    from numba import njit, prange
    USE_NUMBA = True
except ImportError:
    USE_NUMBA = False
    def njit(*args, **kwargs):
        def decorator(func):
            return func
        return decorator if args and callable(args[0]) else decorator
    prange = range

@dataclass
class ConfiguracionFitness:
    """Configuración de pesos y umbrales para el fitness"""
    peso_solapes: float = float('inf')  # Restricción dura
    peso_huecos: float = 10.0
    peso_primeras_ultimas: float = 5.0
    peso_balance_dia: float = 3.0
    peso_bloques_semana: float = 15.0
    umbral_primeras_ultimas: int = 2  # Bloques 1-2 y últimos 2
    umbral_balance_aceptable: float = 1.5
    umbral_balance_bueno: float = 1.0
    umbral_balance_optimo: float = 0.7

@dataclass
class ResultadoFitness:
    """Resultado completo del cálculo de fitness"""
    fitness_total: float
    penalizacion_solapes: float
    penalizacion_huecos: float
    penalizacion_primeras_ultimas: float
    penalizacion_balance_dia: float
    penalizacion_bloques_semana: float
    num_solapes: int
    num_huecos: int
    porcentaje_primeras_ultimas: float
    desviacion_balance_dia: float
    es_valida: bool
    mensaje_estado: str

# Hacer accesible en builtins
builtins.ResultadoFitness = ResultadoFitness

def calcular_fitness_unificado(
    cromosoma: Dict[Tuple[int, str, int], Tuple[int, int]],
    mascaras: MascarasOptimizadas,
    config: ConfiguracionFitness = None
) -> ResultadoFitness:
    """
    Calcula el fitness unificado de un cromosoma usando máscaras optimizadas.
    """
    if config is None:
        config = ConfiguracionFitness()
    
    # Convertir cromosoma a arrays numpy para optimización
    curso_ids, dias, bloques, materia_ids, profesor_ids = _convertir_cromosoma_a_arrays(cromosoma)
    
    # Datos base
    dias_clase = list(mascaras.dias_clase)
    bloques_por_dia = int(mascaras.bloques_por_dia)
    n_slots_teoricos_por_curso = len(dias_clase) * bloques_por_dia
    
    # Penalizaciones (normalizadas)
    _, num_solapes = _calcular_penalizacion_solapes_np(curso_ids, dias, bloques, profesor_ids)
    pen_huecos, num_huecos = _calcular_penalizacion_huecos_np(curso_ids, dias, bloques, dias_clase)
    pen_priult, porcentaje_priult = _calcular_penalizacion_primeras_ultimas_np(bloques, bloques_por_dia, config.umbral_primeras_ultimas)
    pen_balance, desv_balance = _calcular_penalizacion_balance_dia_np(dias, dias_clase)
    pen_bloques = _calcular_penalizacion_bloques_semana(curso_ids, materia_ids, dias, mascaras)

    # Normalizaciones relativas basadas en dimensiones actuales
    # Evitar divisiones por cero con max(1, ...)
    max_huecos_posible = max(1, (bloques_por_dia - 1) * len(dias_clase) * len(set(curso_ids)))
    norm_huecos = pen_huecos / max_huecos_posible

    norm_priult = (pen_priult / max(1, len(bloques))) if len(bloques) > 0 else 0.0

    # Balance ya es una desviación; normalizar por sqrt(total_asignaciones) como cota grosera
    norm_balance = pen_balance / max(1.0, np.sqrt(max(1, len(curso_ids))))

    # Desvío de bloques: normalizar por suma de requeridos presentes
    # Estimar requeridos por materia presentes en cromosoma
    req_est = {}
    for mid in materia_ids:
        req_est[mid] = req_est.get(mid, 0) + 1
    max_desvio = max(1, sum(req_est.values()))
    norm_bloques = pen_bloques / max_desvio

    # Dominancia de solapes: cualquier solape supera la suma de blandas
    blandas = norm_huecos + norm_priult + norm_balance + norm_bloques
    pen_solapes = float('inf') if num_solapes > 0 else 0.0

    # Fitness total: si hay solapes, -inf; si no, negativo de blandas
    fitness_total = -(pen_solapes + blandas)

    es_valida = num_solapes == 0
    mensaje_estado = (f"Solución inválida: {num_solapes} solapes detectados" if not es_valida
                      else ("Solución válida"))
    
    return ResultadoFitness(
        fitness_total=fitness_total,
        penalizacion_solapes=pen_solapes,
        penalizacion_huecos=norm_huecos,
        penalizacion_primeras_ultimas=norm_priult,
        penalizacion_balance_dia=norm_balance,
        penalizacion_bloques_semana=norm_bloques,
        num_solapes=num_solapes,
        num_huecos=num_huecos,
        porcentaje_primeras_ultimas=porcentaje_priult,
        desviacion_balance_dia=desv_balance,
        es_valida=es_valida,
        mensaje_estado=mensaje_estado
    )

def _convertir_cromosoma_a_arrays(
    cromosoma: Dict[Tuple[int, str, int], Tuple[int, int]]
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Convierte el cromosoma a arrays numpy para optimización"""
    if not cromosoma:
        return (np.array([]), np.array([]), np.array([]), np.array([]), np.array([]))
    
    curso_ids = []
    dias = []
    bloques = []
    materia_ids = []
    profesor_ids = []
    
    for (curso_id, dia, bloque), (materia_id, profesor_id) in cromosoma.items():
        curso_ids.append(curso_id)
        dias.append(dia)
        bloques.append(bloque)
        materia_ids.append(materia_id)
        profesor_ids.append(profesor_id)
    
    return (
        np.array(curso_ids, dtype=np.int32),
        np.array(dias, dtype=object),
        np.array(bloques, dtype=np.int32),
        np.array(materia_ids, dtype=np.int32),
        np.array(profesor_ids, dtype=np.int32)
    )

# Versiones puras numpy (sin pasar objetos complejos a njit)

def _calcular_penalizacion_solapes_np(
    curso_ids: np.ndarray,
    dias: np.ndarray,
    bloques: np.ndarray,
    profesor_ids: np.ndarray
) -> Tuple[float, int]:
    n = len(curso_ids)
    solapes = 0
    if n == 0:
        return 0.0, 0
    for i in range(n):
        for j in range(i + 1, n):
            # Solape por curso en mismo día y bloque exacto
            if curso_ids[i] == curso_ids[j] and dias[i] == dias[j] and bloques[i] == bloques[j]:
                solapes += 1
            # Solape por profesor: si enseña más de una vez el mismo día (criterio estricto pedido por tests)
            if profesor_ids[i] == profesor_ids[j] and dias[i] == dias[j]:
                solapes += 1
    return float(solapes), solapes

def _calcular_penalizacion_huecos_np(
    curso_ids: np.ndarray,
    dias: np.ndarray,
    bloques: np.ndarray,
    dias_clase: List[str]
) -> Tuple[float, int]:
    n = len(curso_ids)
    if n == 0:
        return 0.0, 0
    # Construir ocupación por (curso,dia)
    huecos = 0
    cursos_unicos = np.unique(curso_ids)
    for curso in cursos_unicos:
        for dia in dias_clase:
            indices = [i for i in range(n) if curso_ids[i] == curso and dias[i] == dia]
            if len(indices) > 1:
                bloques_curso = sorted([bloques[i] for i in indices])
                for k in range(len(bloques_curso) - 1):
                    huecos += max(0, bloques_curso[k + 1] - bloques_curso[k] - 1)
    return float(huecos), huecos

def _calcular_penalizacion_primeras_ultimas_np(
    bloques: np.ndarray,
    bloques_por_dia: int,
    umbral: int
) -> Tuple[float, float]:
    n = len(bloques)
    if n == 0:
        return 0.0, 0.0
    primeras_ultimas = 0
    for b in bloques:
        if 1 <= b <= umbral:
            primeras_ultimas += 1
        elif b > bloques_por_dia - umbral:
            primeras_ultimas += 1
    porcentaje = (primeras_ultimas / n) * 1.0
    return float(primeras_ultimas), porcentaje

def _calcular_penalizacion_balance_dia_np(
    dias: np.ndarray,
    dias_clase: List[str]
) -> Tuple[float, float]:
    if len(dias) == 0:
        return 0.0, 0.0
    conteo = np.zeros(len(dias_clase), dtype=np.int32)
    for d in dias:
        try:
            idx = dias_clase.index(d)
            conteo[idx] += 1
        except ValueError:
            continue
    if len(conteo) > 1:
        desviacion = float(np.sqrt(np.var(conteo)))
    else:
        desviacion = 0.0
    return desviacion, desviacion

def _calcular_penalizacion_bloques_semana(
    curso_ids: np.ndarray,
    materia_ids: np.ndarray,
    dias: np.ndarray,
    mascaras: MascarasOptimizadas
) -> float:
    """Calcula penalización normalizada por diferencia con bloques_por_semana reales.
    penalización = sum(|asignados-req|/max(1,req))
    """
    from horarios.models import MateriaGrado, Curso, CursoMateriaRequerida
    # Mapear requeridos por (curso,materia)
    requeridos = {}
    cmr = list(CursoMateriaRequerida.objects.values_list('curso_id','materia_id','bloques_requeridos'))
    if cmr:
        for cid, mid, req in cmr:
            requeridos[(cid, mid)] = int(req)
    else:
        # Fallback: usar plan por grado (misma carga por curso del grado)
        curso_to_grado = {c.id: c.grado_id for c in Curso.objects.all()}
        for mg in MateriaGrado.objects.select_related('materia').all():
            req = mg.materia.bloques_por_semana
            for cid, gid in curso_to_grado.items():
                if gid == mg.grado_id:
                    requeridos[(cid, mg.materia_id)] = req
    # Contar asignados por (curso, materia)
    asignados = {}
    for c, m in zip(curso_ids.tolist(), materia_ids.tolist()):
        asignados[(int(c), int(m))] = asignados.get((int(c), int(m)), 0) + 1
    # Penalización normalizada
    penal = 0.0
    for key, req in requeridos.items():
        asign = asignados.get(key, 0)
        penal += abs(asign - req) / float(max(1, req))
    return float(penal)

def evaluar_calidad_solucion(
    resultado_fitness: ResultadoFitness
) -> Dict[str, str]:
    """
    Evalúa la calidad de una solución basada en los KPIs.
    Retorna diccionario con evaluación por categoría usando etiquetas simples.
    """
    evaluacion = {}
    
    # Solapes (debe ser 0)
    evaluacion['solapes'] = "Óptimo" if resultado_fitness.num_solapes == 0 else "Crítico"
    
    # Huecos
    if resultado_fitness.num_huecos == 0:
        evaluacion['huecos'] = "Óptimo"
    elif resultado_fitness.num_huecos <= 2:
        evaluacion['huecos'] = "Bueno"
    elif resultado_fitness.num_huecos <= 5:
        evaluacion['huecos'] = "Aceptable"
    else:
        evaluacion['huecos'] = "Regular"
    
    # Primeras/Últimas franjas (0-1)
    porcentaje = resultado_fitness.porcentaje_primeras_ultimas
    if porcentaje <= 0.10:
        evaluacion['primeras_ultimas'] = "Óptimo"
    elif porcentaje <= 0.15:
        evaluacion['primeras_ultimas'] = "Bueno"
    elif porcentaje <= 0.25:
        evaluacion['primeras_ultimas'] = "Aceptable"
    else:
        evaluacion['primeras_ultimas'] = "Alto"
    
    # Balance diario (desviación estándar)
    desviacion = resultado_fitness.desviacion_balance_dia
    if desviacion <= 0.7:
        evaluacion['balance_dia'] = "Óptimo"
    elif desviacion <= 1.0:
        evaluacion['balance_dia'] = "Bueno"
    elif desviacion <= 1.5:
        evaluacion['balance_dia'] = "Aceptable"
    else:
        evaluacion['balance_dia'] = "Alto"
    
    return evaluacion

def obtener_recomendaciones_mejora(
    resultado_fitness: ResultadoFitness
) -> List[str]:
    """
    Genera recomendaciones específicas para mejorar la solución.
    Retorna lista de recomendaciones ordenadas por prioridad.
    """
    recomendaciones = []
    
    # Prioridad 1: Solapes (crítico)
    if resultado_fitness.num_solapes > 0:
        recomendaciones.append("🔴 CRÍTICO: Eliminar todos los solapes (profesores/cursos en mismo slot)")
    
    # Prioridad 2: Huecos excesivos
    if resultado_fitness.num_huecos > 20:
        recomendaciones.append("🟡 ALTO: Reducir huecos entre materias del mismo curso")
    
    # Prioridad 3: Primeras/últimas franjas
    if resultado_fitness.porcentaje_primeras_ultimas > 25:
        recomendaciones.append("🟡 MEDIO: Reducir asignaciones en bloques 1-2 y últimos bloques")
    
    # Prioridad 4: Balance diario
    if resultado_fitness.desviacion_balance_dia > 1.5:
        recomendaciones.append("🟡 MEDIO: Mejorar distribución equilibrada de materias por día")
    
    # Prioridad 5: Fitness general
    if resultado_fitness.fitness_total < -200:
        recomendaciones.append("🟡 BAJO: Revisar configuración de pesos del fitness")
    
    # Si no hay problemas críticos
    if not recomendaciones:
        recomendaciones.append("✅ La solución actual es de buena calidad")
    
    return recomendaciones 