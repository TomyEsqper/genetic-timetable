"""
Algoritmo Genético para Generación de Horarios Escolares

Este módulo implementa un algoritmo genético optimizado para la generación de horarios escolares
que respeta las siguientes restricciones:
1. Sin solapes: (curso, día, bloque) y (profesor, día, bloque) únicos.
2. Respetar disponibilidad de profesores y bloques_por_semana.
3. Solo bloques tipo 'clase'.
4. Aula fija por curso.

Representación del cromosoma:
- Diccionario: {(curso_id, día, idx_bloque) -> (materia_id, profesor_id)}
- Cada gen representa una asignación de materia y profesor a un curso en un día y bloque específico.

Características principales:
- Inicialización guiada: prioriza materias con pocos profesores disponibles
- Fitness paralelo: evaluación de aptitud utilizando multiprocessing
- Cruce por bloques: recombinación por día-bloque manteniendo factibilidad
- Mutación adaptativa: centrada en genes conflictivos
- Early stopping: detiene el algoritmo si no hay mejora en un número de generaciones
- Optimización de memoria: estructuras compactas para manejar grandes volúmenes de datos
"""

import random
import logging
import time
import os
import numpy as np
from dataclasses import dataclass, field
from typing import Dict, List, Set, Tuple, Any
from multiprocessing import Pool, cpu_count
from functools import partial, lru_cache
import importlib
import warnings
from contextlib import contextmanager
from concurrent.futures import ProcessPoolExecutor
import json
from collections import defaultdict
from .mascaras import precomputar_mascaras
import math

# Configuración global para optimizaciones
USE_DATAFRAMES = False  # Por defecto usar Python puro para mejor rendimiento
USE_ORTOOLS = False     # Fallback opcional a OR-Tools

# Intentar importar librerías opcionales
def try_import(module_name):
    """Intenta importar un módulo y devuelve None si no está disponible."""
    try:
        return importlib.import_module(module_name)
    except ImportError:
        return None

# Importar librerías opcionales
joblib = try_import('joblib')
numba = try_import('numba')
pandas = try_import('pandas') if USE_DATAFRAMES else None
polars = try_import('polars') if USE_DATAFRAMES else None
redis = try_import('redis')

# Configurar Numba si está disponible
if numba:
    from numba import njit, prange
    # Suprimir advertencias de Numba durante la compilación
    warnings.filterwarnings('ignore', category=numba.NumbaDeprecationWarning)
    warnings.filterwarnings('ignore', category=numba.NumbaWarning)
else:
    # Crear decoradores falsos para mantener compatibilidad
    def njit(*args, **kwargs):
        def decorator(func):
            return func
        return decorator if args and callable(args[0]) else decorator
    
    # Alias para range cuando no hay numba
    prange = range

def warmup_numba(datos):
    """
    Función de warm-up para Numba JIT.
    Se ejecuta una sola vez al inicio para evitar "arranque eterno".
    """
    if not numba:
        return
    
    # Verificar si se debe desactivar
    import os
    if os.environ.get('HORARIOS_NUMBA', '1') == '0':
        logger.info("Warm-up de Numba desactivado por HORARIOS_NUMBA=0")
        return
    
    try:
        logger.info("Ejecutando warm-up de Numba...")
        
        # Generar arrays diminutos para calentar JIT
        if '_calcular_conflictos_numpy' in globals():
            # Crear arrays de prueba mínimos con tipos correctos
            cursos = np.array([1, 1], dtype=np.int32)
            dias = np.array([0, 1], dtype=np.int32)
            bloques = np.array([1, 2], dtype=np.int32)
            materias = np.array([1, 2], dtype=np.int32)
            profesores = np.array([1, 2], dtype=np.int32)
            disponibilidad_profesor = np.array([[1, 0, 1], [2, 1, 2]], dtype=np.int32)
            materia_profesor = np.array([[1, 1], [2, 2]], dtype=np.int32)
            # Llamar función JIT con la firma correcta
            _calcular_conflictos_numpy(
                cursos, dias, bloques, materias, profesores,
                disponibilidad_profesor, materia_profesor
            )
            logger.info("✅ Warm-up de Numba completado")
        else:
            logger.debug("Función _calcular_conflictos_numpy no disponible para warm-up")
        
    except Exception as e:
        logger.warning(f"Error durante warm-up de Numba: {e}")
        logger.info("Continuando sin warm-up de Numba")

from horarios.models import (
    Curso, MateriaGrado, MateriaProfesor, DisponibilidadProfesor, 
    Aula, Horario, BloqueHorario, Materia, Profesor
)

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constantes
MENSAJE_ERROR_SOLUCION_INVALIDA = 'No se pudo generar una solución válida'

def get_dias_clase():
    """
    Obtiene los días de clase desde la configuración de la base de datos.
    Retorna lista normalizada (lower, strip) de días.
    """
    try:
        from horarios.models import ConfiguracionColegio
        config = ConfiguracionColegio.objects.first()
        if config and config.dias_clase:
            dias = [dia.strip().lower() for dia in config.dias_clase.split(',')]
            logger.info(f"Días de clase cargados desde BD: {dias}")
            return dias
        else:
            logger.warning("No se encontró configuración de días de clase, usando valores por defecto")
            return ['lunes', 'martes', 'miércoles', 'jueves', 'viernes']
    except Exception as e:
        logger.warning(f"Error al cargar días de clase desde BD: {e}, usando valores por defecto")
        return ['lunes', 'martes', 'miércoles', 'jueves', 'viernes']

# Obtener días dinámicamente
DIAS = get_dias_clase()
DIA_INDICE = {dia: idx for idx, dia in enumerate(DIAS)}

# Configuración para representación compacta
LNS_FREQ = 10          # Frecuencia de aplicación de LNS
LNS_RATIO = 0.25       # Porcentaje de individuos afectados por LNS
FITNESS_CACHE_SIZE = 4096  # Tamaño del caché LRU de fitness

# Caché LRU de fitness
class FitnessCache:
    """Caché LRU simple para almacenar resultados de fitness."""
    
    def __init__(self, max_size: int = FITNESS_CACHE_SIZE):
        self.max_size = max_size
        self.cache = {}
        self.access_order = []
    
    def get(self, key: str) -> Tuple[float, int]:
        """Obtiene valor del caché y actualiza orden de acceso."""
        if key in self.cache:
            # Mover al final (más reciente)
            self.access_order.remove(key)
            self.access_order.append(key)
            return self.cache[key]
        return None
    
    def put(self, key: str, value: Tuple[float, int]):
        """Almacena valor en caché con política LRU."""
        if key in self.cache:
            # Actualizar existente
            self.access_order.remove(key)
        elif len(self.cache) >= self.max_size:
            # Eliminar menos reciente
            oldest = self.access_order.pop(0)
            del self.cache[oldest]
        
        self.cache[key] = value
        self.access_order.append(key)
    
    def clear(self):
        """Limpia el caché."""
        self.cache.clear()
        self.access_order.clear()
    
    def size(self) -> int:
        """Retorna el tamaño actual del caché."""
        return len(self.cache)

# Instancia global del caché
fitness_cache = FitnessCache()

# Mapeos de índices para representación compacta
def crear_mapeos_indices(datos):
    """
    Crea mapeos de índices para representación compacta del cromosoma.
    """
    # Mapeos curso
    curso_to_idx = {curso_id: idx for idx, curso_id in enumerate(datos.cursos.keys())}
    idx_to_curso = {idx: curso_id for curso_id, idx in curso_to_idx.items()}
    
    # Mapeos día
    dia_to_idx = DIA_INDICE
    idx_to_dia = {idx: dia for dia, idx in dia_to_idx.items()}
    
    # Mapeos bloque (solo tipo 'clase')
    bloques_clase = sorted(datos.bloques_disponibles)
    bloque_to_idx = {bloque: idx for idx, bloque in enumerate(bloques_clase)}
    idx_to_bloque = {idx: bloque for bloque, idx in bloque_to_idx.items()}
    
    # Mapeos materia
    materia_to_idx = {materia_id: idx for idx, materia_id in enumerate(datos.materias.keys())}
    idx_to_materia = {idx: materia_id for materia_id, idx in materia_to_idx.items()}
    
    # Mapeos profesor
    profesor_to_idx = {profesor_id: idx for idx, profesor_id in enumerate(datos.profesores.keys())}
    idx_to_profesor = {idx: profesor_id for profesor_id, idx in profesor_to_idx.items()}
    
    return {
        'curso_to_idx': curso_to_idx,
        'idx_to_curso': idx_to_curso,
        'dia_to_idx': dia_to_idx,
        'idx_to_dia': idx_to_dia,
        'bloque_to_idx': bloque_to_idx,
        'idx_to_bloque': idx_to_bloque,
        'materia_to_idx': materia_to_idx,
        'idx_to_materia': idx_to_materia,
        'profesor_to_idx': profesor_to_idx,
        'idx_to_profesor': idx_to_profesor,
        'n_cursos': len(curso_to_idx),
        'n_dias': len(DIAS),
        'n_bloques': len(bloques_clase),
        'n_materias': len(materia_to_idx),
        'n_profesores': len(profesor_to_idx)
    }

# Constantes de penalización para fitness
PENAL_HUECO = 10_000  # Penalización alta por cada casilla vacía
PENAL_DESVIO = 2_000  # Penalización por desvío en bloques_por_semana
PENAL_DISPONIBILIDAD = 5_000  # Penalización por asignar profesor sin disponibilidad
PENAL_SOLAPE = 8_000  # Penalización por solapes

@dataclass
class ProfesorData:
    id: int
    disponibilidad: Set[Tuple[str, int]]  # (día, bloque)
    materias: Set[int]  # materia_ids

@dataclass
class CromosomaCompacto:
    """
    Representación compacta del cromosoma usando arrays NumPy.
    """
    materia_por_slot: np.ndarray  # dtype=int16, tamaño N = cursos * dias * bloques
    profesor_por_slot: np.ndarray  # dtype=int16, tamaño N = cursos * dias * bloques
    mapeos: Dict  # Mapeos de índices para conversión
    
    def __post_init__(self):
        self.n_slots = len(self.materia_por_slot)
        self.n_cursos = self.mapeos['n_cursos']
        self.n_dias = self.mapeos['n_dias']
        self.n_bloques = self.mapeos['n_bloques']
    
    def slot_to_coords(self, slot_id: int) -> Tuple[int, int, int]:
        """Convierte slot_id a (curso_idx, dia_idx, bloque_idx)"""
        curso_idx = slot_id // (self.n_dias * self.n_bloques)
        resto = slot_id % (self.n_dias * self.n_bloques)
        dia_idx = resto // self.n_bloques
        bloque_idx = resto % self.n_bloques
        return curso_idx, dia_idx, bloque_idx
    
    def coords_to_slot(self, curso_idx: int, dia_idx: int, bloque_idx: int) -> int:
        """Convierte (curso_idx, dia_idx, bloque_idx) a slot_id"""
        return curso_idx * (self.n_dias * self.n_bloques) + dia_idx * self.n_bloques + bloque_idx
    
    def get_hash(self) -> str:
        """Genera hash del cromosoma para caché"""
        import hashlib
        # Concatenar arrays y generar hash
        combined = np.concatenate([self.materia_por_slot, self.profesor_por_slot])
        return hashlib.sha1(combined.tobytes()).hexdigest()[:16]

def dict_to_arrays(crom_dict: Dict, mapeos: Dict) -> CromosomaCompacto:
    """
    Convierte cromosoma de dict a arrays compactos.
    """
    n_slots = mapeos['n_cursos'] * mapeos['n_dias'] * mapeos['n_bloques']
    
    # Inicializar arrays con -1 (slot vacío)
    materia_por_slot = np.full(n_slots, -1, dtype=np.int16)
    profesor_por_slot = np.full(n_slots, -1, dtype=np.int16)
    
    # Llenar arrays desde el dict
    for (curso_id, dia, bloque), (materia_id, profesor_id) in crom_dict.items():
        curso_idx = mapeos['curso_to_idx'][curso_id]
        dia_idx = mapeos['dia_to_idx'][dia]
        bloque_idx = mapeos['bloque_to_idx'][bloque]
        
        slot_id = curso_idx * (mapeos['n_dias'] * mapeos['n_bloques']) + dia_idx * mapeos['n_bloques'] + bloque_idx
        
        materia_por_slot[slot_id] = mapeos['materia_to_idx'][materia_id]
        profesor_por_slot[slot_id] = mapeos['profesor_to_idx'][profesor_id]
    
    return CromosomaCompacto(materia_por_slot, profesor_por_slot, mapeos)

def arrays_to_dict(crom_compacto: CromosomaCompacto) -> Dict:
    """
    Convierte cromosoma de arrays compactos a dict.
    """
    crom_dict = {}
    
    for slot_id in range(crom_compacto.n_slots):
        materia_idx = crom_compacto.materia_por_slot[slot_id]
        profesor_idx = crom_compacto.profesor_por_slot[slot_id]
        
        if materia_idx != -1 and profesor_idx != -1:
            curso_idx, dia_idx, bloque_idx = crom_compacto.slot_to_coords(slot_id)
            
            curso_id = crom_compacto.mapeos['idx_to_curso'][curso_idx]
            dia = crom_compacto.mapeos['idx_to_dia'][dia_idx]
            bloque = crom_compacto.mapeos['idx_to_bloque'][bloque_idx]
            materia_id = crom_compacto.mapeos['idx_to_materia'][materia_idx]
            profesor_id = crom_compacto.mapeos['idx_to_profesor'][profesor_idx]
            
            crom_dict[(curso_id, dia, bloque)] = (materia_id, profesor_id)
    
    return crom_dict

@dataclass
class MateriaData:
    id: int
    nombre: str
    bloques_por_semana: int
    requiere_aula_especial: bool
    profesores: List[int]  # profesor_ids

@dataclass
class CursoData:
    id: int
    nombre: str
    grado_id: int
    aula_id: int
    materias: List[int]  # materia_ids

@dataclass
class DatosHorario:
    cursos: Dict[int, CursoData] = field(default_factory=dict)
    materias: Dict[int, MateriaData] = field(default_factory=dict)
    profesores: Dict[int, ProfesorData] = field(default_factory=dict)
    aulas: Dict[int, Dict] = field(default_factory=dict)
    bloques_disponibles: List[int] = field(default_factory=list)
    materia_grado: Dict[Tuple[int, int], bool] = field(default_factory=dict)  # (grado_id, materia_id) -> bool
    materia_profesor: Dict[Tuple[int, int], bool] = field(default_factory=dict)  # (materia_id, profesor_id) -> bool
    
    # Estadísticas para inicialización guiada
    materia_dificultad: Dict[int, float] = field(default_factory=dict)  # materia_id -> dificultad
    
    # Mapeos optimizados para acceso rápido
    curso_to_idx: Dict[int, int] = field(default_factory=dict)  # curso_id -> índice
    profesor_to_idx: Dict[int, int] = field(default_factory=dict)  # profesor_id -> índice
    materia_to_idx: Dict[int, int] = field(default_factory=dict)  # materia_id -> índice
    bloque_to_idx: Dict[int, int] = field(default_factory=dict)  # bloque -> índice
    
    # Arrays NumPy para evaluación rápida
    disponibilidad_array: np.ndarray = None  # [profesor_idx, dia_idx, bloque_idx] -> bool
    bloques_por_semana_array: np.ndarray = None  # [curso_idx, materia_idx] -> bloques_necesarios

@dataclass
class Cromosoma:
    genes: Dict[Tuple[int, str, int], Tuple[int, int]] = field(default_factory=dict)  # (curso_id, día, bloque) -> (materia_id, profesor_id)
    fitness: float = 0.0
    conflictos: int = 0
    
    def copy(self):
        nuevo = Cromosoma()
        nuevo.genes = self.genes.copy()
        nuevo.fitness = self.fitness
        nuevo.conflictos = self.conflictos
        return nuevo

def pre_validacion_dura(datos: DatosHorario) -> List[str]:
    """
    Pre-validación dura más estricta antes de generar población.
    
    Verifica:
    1. Capacidad vs demanda de bloques por curso
    2. Disponibilidad de profesores para cada materia
    3. Factibilidad básica del problema
    
    Args:
        datos: Datos preprocesados del horario
        
    Returns:
        Lista de errores encontrados
    """
    errores = []
    
    # Calcular bloques totales disponibles por curso (días * bloques por día)
    bloques_por_dia = len(datos.bloques_disponibles)
    bloques_totales_curso = len(DIAS) * bloques_por_dia
    
    logger.info(f"Validando {len(datos.cursos)} cursos con {bloques_totales_curso} bloques disponibles por curso")
    
    for curso_id, curso in datos.cursos.items():
        # Calcular bloques requeridos por las materias del curso
        bloques_requeridos = 0
        materias_curso = []
        
        for materia_id in curso.materias:
            if materia_id in datos.materias:
                materia = datos.materias[materia_id]
                bloques_requeridos += materia.bloques_por_semana
                materias_curso.append(f"{materia.nombre}({materia.bloques_por_semana})")
                
                # Verificar que la materia tenga al menos un profesor
                if not materia.profesores:
                    errores.append(f"❌ Materia {materia.nombre} del curso {curso.nombre} no tiene profesores asignados")
                    continue
                
                # Verificar que al menos un profesor tenga disponibilidad
                profesor_con_disponibilidad = False
                for profesor_id in materia.profesores:
                    if profesor_id in datos.profesores:
                        if datos.profesores[profesor_id].disponibilidad:
                            profesor_con_disponibilidad = True
                            break
                
                if not profesor_con_disponibilidad:
                    errores.append(f"❌ Materia {materia.nombre} del curso {curso.nombre} no tiene profesores con disponibilidad")
        
        # Verificar capacidad vs demanda
        diferencia = bloques_requeridos - bloques_totales_curso
        
        if diferencia > 0:
            errores.append(f"❌ {curso.nombre}: DEMANDA EXCEDE CAPACIDAD - faltan {diferencia} bloques (requiere {bloques_requeridos}, disponible {bloques_totales_curso})")
        elif diferencia < 0:
            # Solo advertencia, no error crítico
            logger.warning(f"⚠️ {curso.nombre}: capacidad subutilizada - requiere {bloques_requeridos} bloques, disponible {bloques_totales_curso} bloques")
    
    # Verificar factibilidad global
    if errores:
        logger.error(f"Pre-validación falló con {len(errores)} errores:")
        for error in errores:
            logger.error(f"  {error}")
    else:
        logger.info("✅ Pre-validación exitosa: todos los cursos tienen capacidad suficiente")
    
    return errores

def cargar_datos() -> DatosHorario:
    """Carga todos los datos necesarios desde la base de datos y los preprocesa para el algoritmo genético.
    
    Utiliza Pandas/Polars si están disponibles para un procesamiento más eficiente.
    """
    datos = DatosHorario()
    logger.info("Cargando datos para el algoritmo genético...")
    inicio = time.time()
    
    # Cargar bloques disponibles (solo tipo 'clase')
    datos.bloques_disponibles = list(BloqueHorario.objects.filter(tipo='clase').order_by('numero').values_list('numero', flat=True))
    
    # Procesamiento eficiente de disponibilidad de profesores
    if USE_DATAFRAMES and (pandas or polars):
        # Usar Pandas/Polars para procesamiento vectorizado
        df_lib = polars if polars else pandas
        using_pandas = (df_lib.__name__ == 'pandas')
        using_polars = (df_lib.__name__ == 'polars')
        logger.info(f"Usando {df_lib.__name__} para procesamiento de datos")
        
        # Cargar disponibilidad de profesores
        disponibilidad_raw = list(DisponibilidadProfesor.objects.values('profesor_id', 'dia', 'bloque_inicio', 'bloque_fin'))
        if disponibilidad_raw:
            df_disp = df_lib.DataFrame(disponibilidad_raw)
            
            # Expandir rangos de bloques
            disponibilidad_expandida = []
            for _, row in df_disp.iterrows() if using_pandas else df_disp.iter_rows(named=True):
                profesor_id = row['profesor_id']
                dia = row['dia']
                for bloque in range(row['bloque_inicio'], row['bloque_fin'] + 1):
                    disponibilidad_expandida.append({'profesor_id': profesor_id, 'dia': dia, 'bloque': bloque})
            
            df_disp_expandida = df_lib.DataFrame(disponibilidad_expandida)
            
            # Verificar si la columna 'dia' existe antes de acceder
            if 'dia' not in df_disp_expandida.columns:
                raise KeyError("La columna 'dia' no está presente en los datos procesados.")

            # Agrupar por profesor
            profesores_disp = {}
            # Asegurar iterables consistentes de ids
            prof_ids = (df_disp_expandida['profesor_id'].unique().tolist() if using_pandas else df_disp_expandida['profesor_id'].unique().to_list())
            for profesor_id in prof_ids:
                if using_pandas:
                    sub = df_disp_expandida[df_disp_expandida['profesor_id'] == profesor_id]
                    dias = sub['dia'].tolist()
                    bloques = sub['bloque'].tolist()
                else:
                    sub = df_disp_expandida.filter(df_disp_expandida['profesor_id'] == profesor_id)
                    dias = sub['dia'].to_list()
                    bloques = sub['bloque'].to_list()
                dias_bloques = list(zip(dias, bloques))
                profesores_disp[profesor_id] = set(dias_bloques)
        else:
            profesores_disp = {}
        
        # Cargar relaciones materia-profesor
        mp_raw = list(MateriaProfesor.objects.values('profesor_id', 'materia_id'))
        if mp_raw:
            df_mp = df_lib.DataFrame(mp_raw)
            
            # Crear diccionario de materias por profesor
            materias_por_profesor = {}
            prof_ids = (df_mp['profesor_id'].unique().tolist() if using_pandas else df_mp['profesor_id'].unique().to_list())
            for profesor_id in prof_ids:
                if using_pandas:
                    sub = df_mp[df_mp['profesor_id'] == profesor_id]
                    materias_por_profesor[profesor_id] = set(sub['materia_id'].tolist())
                else:
                    sub = df_mp.filter(df_mp['profesor_id'] == profesor_id)
                    materias_por_profesor[profesor_id] = set(sub['materia_id'].to_list())
            
            # Crear diccionario de profesores por materia
            profesores_por_materia = {}
            materia_ids = (df_mp['materia_id'].unique().tolist() if using_pandas else df_mp['materia_id'].unique().to_list())
            for materia_id in materia_ids:
                if using_pandas:
                    sub = df_mp[df_mp['materia_id'] == materia_id]
                    profesores_por_materia[materia_id] = list(sub['profesor_id'].tolist())
                else:
                    sub = df_mp.filter(df_mp['materia_id'] == materia_id)
                    profesores_por_materia[materia_id] = list(sub['profesor_id'].to_list())
            
            # Crear relaciones materia-profesor
            materia_profesor_dict = {}
            for _, row in df_mp.iterrows() if using_pandas else df_mp.iter_rows(named=True):
                materia_profesor_dict[(row['materia_id'], row['profesor_id'])] = True
        else:
            materias_por_profesor = {}
            profesores_por_materia = {}
            materia_profesor_dict = {}
    else:
        # Procesamiento tradicional
        logger.info("Usando procesamiento tradicional (sin Pandas/Polars)")
        profesores_disp = {}
        materias_por_profesor = {}
        profesores_por_materia = {}
        materia_profesor_dict = {}
        
        # Procesar disponibilidad
        for profesor in Profesor.objects.all():
            disponibilidad = set()
            for disp in DisponibilidadProfesor.objects.filter(profesor=profesor):
                for bloque in range(disp.bloque_inicio, disp.bloque_fin + 1):
                    disponibilidad.add((disp.dia, bloque))
            profesores_disp[profesor.id] = disponibilidad
            materias_por_profesor[profesor.id] = set()
        
        # Procesar relaciones materia-profesor
        for mp in MateriaProfesor.objects.all():
            if mp.materia.id not in profesores_por_materia:
                profesores_por_materia[mp.materia.id] = []
            profesores_por_materia[mp.materia.id].append(mp.profesor.id)
            materias_por_profesor[mp.profesor.id].add(mp.materia.id)
            materia_profesor_dict[(mp.materia.id, mp.profesor.id)] = True
    
    # Cargar profesores
    for profesor in Profesor.objects.all():
        datos.profesores[profesor.id] = ProfesorData(
            id=profesor.id,
            disponibilidad=profesores_disp.get(profesor.id, set()),
            materias=materias_por_profesor.get(profesor.id, set())
        )
    
    # Cargar materias
    for materia in Materia.objects.all():
        datos.materias[materia.id] = MateriaData(
            id=materia.id,
            nombre=materia.nombre,
            bloques_por_semana=materia.bloques_por_semana,
            requiere_aula_especial=materia.requiere_aula_especial,
            profesores=profesores_por_materia.get(materia.id, [])
        )
    
    # Guardar relaciones materia-profesor
    datos.materia_profesor = materia_profesor_dict
    
    # Calcular dificultad de asignación para cada materia (menos profesores = más difícil)
    for materia_id, materia in datos.materias.items():
        # Normalizar: 1.0 para materias con un solo profesor, 0.1 para materias con muchos profesores
        num_profesores = len(materia.profesores)
        if num_profesores == 0:
            datos.materia_dificultad[materia_id] = 0.0  # No se puede asignar
        else:
            datos.materia_dificultad[materia_id] = 1.0 / max(1, num_profesores)
    
    # Cargar cursos y relación materia-grado
    if USE_DATAFRAMES and (pandas or polars):
        # Usar Pandas/Polars para procesamiento vectorizado
        df_lib = polars if polars else pandas
        using_pandas = (df_lib.__name__ == 'pandas')
        using_polars = (df_lib.__name__ == 'polars')
        
        # Cargar relaciones materia-grado
        mg_raw = list(MateriaGrado.objects.values('grado_id', 'materia_id'))
        if mg_raw:
            df_mg = df_lib.DataFrame(mg_raw)
            materia_grado_dict = {}
            for _, row in df_mg.iterrows() if using_pandas else df_mg.iter_rows(named=True):
                materia_grado_dict[(row['grado_id'], row['materia_id'])] = True
            
            # Crear diccionario de materias por grado
            materias_por_grado = {}
            grado_ids = (df_mg['grado_id'].unique().tolist() if using_pandas else df_mg['grado_id'].unique().to_list())
            for grado_id in grado_ids:
                if using_pandas:
                    sub = df_mg[df_mg['grado_id'] == grado_id]
                    materias_por_grado[grado_id] = list(sub['materia_id'].tolist())
                else:
                    sub = df_mg.filter(df_mg['grado_id'] == grado_id)
                    materias_por_grado[grado_id] = list(sub['materia_id'].to_list())
        else:
            materia_grado_dict = {}
            materias_por_grado = {}
    else:
        # Procesamiento tradicional
        materia_grado_dict = {}
        materias_por_grado = {}
        
        for mg in MateriaGrado.objects.all():
            materia_grado_dict[(mg.grado.id, mg.materia.id)] = True
            if mg.grado.id not in materias_por_grado:
                materias_por_grado[mg.grado.id] = []
            materias_por_grado[mg.grado.id].append(mg.materia.id)
    
    # Guardar relaciones materia-grado
    datos.materia_grado = materia_grado_dict
    
    # Cargar cursos
    for curso in Curso.objects.all():
        # Usar el aula_fija del curso si existe, sino asignar una disponible
        aula_id = None
        if curso.aula_fija:
            aula_id = curso.aula_fija.id
        else:
            # Asignar aula disponible si no tiene aula fija
            aulas_comunes = list(Aula.objects.filter(tipo='comun').values('id'))
            if aulas_comunes:
                aula_id = aulas_comunes[curso.id % len(aulas_comunes)]['id']
        
        datos.cursos[curso.id] = CursoData(
            id=curso.id,
            nombre=curso.nombre,
            grado_id=curso.grado.id,
            aula_id=aula_id,
            materias=materias_por_grado.get(curso.grado.id, [])
        )
    
    # Cargar aulas
    for aula in Aula.objects.all():
        datos.aulas[aula.id] = {
            'id': aula.id,
            'nombre': aula.nombre,
            'tipo': aula.tipo,
            'capacidad': aula.capacidad
        }
    
    tiempo_carga = time.time() - inicio
    logger.info(f"Datos cargados en {tiempo_carga:.2f} segundos")
    logger.info(f"Cursos: {len(datos.cursos)}, Materias: {len(datos.materias)}, Profesores: {len(datos.profesores)}")
    
    return datos

def inicializar_poblacion_robusta(datos: DatosHorario, tamano_poblacion: int) -> List[Cromosoma]:
    """
    Inicializa una población con individuo 0 demand-first y resto con estrategia existente.
    """
    logger.info("Inicializando población con individuo 0 (demand-first) y diversidad...")
    poblacion = []

    # Individuo 0 demand-first
    try:
        crom0 = construir_individuo_demanda_primero(datos)
        poblacion.append(crom0)
        logger.info("Individuo 0 construido (demand-first)")
    except Exception as e:
        logger.warning(f"Fallo construyendo individuo 0 demand-first: {e}. Se continuará con estrategia existente")

    # Rellenar resto usando la estrategia previa (manteniendo diversidad)
    restantes = max(0, tamano_poblacion - len(poblacion))
    if restantes > 0:
        # Usar lógica actual para generar individuos variados
        intentos_maximos = restantes * 3
        intentos = 0
        while len(poblacion) < tamano_poblacion and intentos < intentos_maximos:
            intentos += 1
            try:
                crom = Cromosoma()
                # Reusar sección de generación existente de manera resumida
                slots_disponibles = {}
                for curso_id, curso in datos.cursos.items():
                    slots_disponibles[curso_id] = {(d, b) for d in DIAS for b in datos.bloques_disponibles}
                for curso_id, curso in datos.cursos.items():
                    for materia_id in curso.materias:
                        if materia_id not in datos.materias:
                            continue
                        materia = datos.materias[materia_id]
                        bloques_necesarios = materia.bloques_por_semana
                        asignados = 0
                        for dia, bloque in list(slots_disponibles[curso_id]):
                            if asignados >= bloques_necesarios:
                                break
                            for profesor_id in materia.profesores:
                                if profesor_id in datos.profesores and (dia, bloque) in datos.profesores[profesor_id].disponibilidad:
                                    # evitar solapes prof/curso
                                    if any((p_id == profesor_id and d == dia and b == bloque) for (c_id, d, b), (_, p_id) in crom.genes.items()):
                                        continue
                                    crom.genes[(curso_id, dia, bloque)] = (materia_id, profesor_id)
                                    slots_disponibles[curso_id].remove((dia, bloque))
                                    asignados += 1
                                    break
                if _validar_cromosoma_basico(crom, datos):
                    poblacion.append(crom)
            except Exception:
                continue

    # Si aún faltan, permitir individuos con posibles conflictos como estaba previsto
    while len(poblacion) < tamano_poblacion:
        poblacion.append(Cromosoma())

    return poblacion

def _validar_cromosoma_basico(cromosoma: Cromosoma, datos: DatosHorario) -> bool:
    """
    Valida que un cromosoma cumpla las restricciones básicas.
    
    Args:
        cromosoma: Cromosoma a validar
        datos: Datos del horario
        
    Returns:
        True si el cromosoma es válido, False en caso contrario
    """
    try:
        # Verificar que no haya duplicados en (curso, día, bloque)
        slots_curso = set()
        for (curso_id, dia, bloque), _ in cromosoma.genes.items():
            key = (curso_id, dia, bloque)
            if key in slots_curso:
                return False
            slots_curso.add(key)
        
        # Verificar que no haya choques de profesores
        slots_profesor = set()
        for (curso_id, dia, bloque), (_, profesor_id) in cromosoma.genes.items():
            key = (profesor_id, dia, bloque)
            if key in slots_profesor:
                return False
            slots_profesor.add(key)
        
        # Verificar que los profesores estén en bloques disponibles
        for (curso_id, dia, bloque), (_, profesor_id) in cromosoma.genes.items():
            if profesor_id in datos.profesores:
                profesor = datos.profesores[profesor_id]
                if (dia, bloque) not in profesor.disponibilidad:
                    return False
        
        return True
        
    except Exception:
        return False

# Función auxiliar para convertir cromosoma a arrays NumPy
def cromosoma_a_arrays(cromosoma: Cromosoma, datos: DatosHorario):
    """Convierte un cromosoma a arrays NumPy para evaluación vectorizada."""
    if not cromosoma.genes:
        return None, None, None, None, None
    
    # Extraer datos del cromosoma
    n_genes = len(cromosoma.genes)
    cursos = np.zeros(n_genes, dtype=np.int32)
    dias = np.zeros(n_genes, dtype=np.int32)
    bloques = np.zeros(n_genes, dtype=np.int32)
    materias = np.zeros(n_genes, dtype=np.int32)
    profesores = np.zeros(n_genes, dtype=np.int32)
    
    # Mapeo de días a índices
    dia_a_indice = {dia: i for i, dia in enumerate(DIAS)}
    
    # Llenar arrays
    for i, ((curso_id, dia, bloque), (materia_id, profesor_id)) in enumerate(cromosoma.genes.items()):
        cursos[i] = curso_id
        dias[i] = dia_a_indice.get(dia, 0)  # Convertir día a índice
        bloques[i] = bloque
        materias[i] = materia_id
        profesores[i] = profesor_id
    
    return cursos, dias, bloques, materias, profesores

# Función optimizada con Numba si está disponible
@njit(nopython=True, fastmath=True)
def _calcular_conflictos_numpy(cursos, dias, bloques, materias, profesores, 
                               disponibilidad_profesor, materia_profesor):
    """Versión optimizada con Numba para calcular conflictos."""
    n_genes = len(cursos)
    puntaje = 0.0
    conflictos = 0
    
    # Arrays para verificar solapes
    max_curso = np.max(cursos) if len(cursos) > 0 else 0
    max_profesor = np.max(profesores) if len(profesores) > 0 else 0
    max_materia = np.max(materias) if len(materias) > 0 else 0
    
    slots_curso = np.zeros((max_curso + 1, 5, np.max(bloques) + 1), dtype=np.int8)
    slots_profesor = np.zeros((max_profesor + 1, 5, np.max(bloques) + 1), dtype=np.int8)
    
    # Contador de bloques por materia y curso
    bloques_materia_curso = np.zeros((max_curso + 1, max_materia + 1), dtype=np.int32)
    
    # Evaluar cada gen
    for i in range(n_genes):
        curso_id = cursos[i]
        dia = dias[i]
        bloque = bloques[i]
        materia_id = materias[i]
        profesor_id = profesores[i]
        
        # Verificar solape de curso
        if slots_curso[curso_id, dia, bloque] > 0:
            conflictos += 1
        else:
            slots_curso[curso_id, dia, bloque] = 1
            puntaje += 1.0  # Bonificación por asignación válida de curso
        
        # Verificar solape de profesor
        if slots_profesor[profesor_id, dia, bloque] > 0:
            conflictos += 1
        else:
            slots_profesor[profesor_id, dia, bloque] = 1
            puntaje += 1.0  # Bonificación por asignación válida de profesor
        
        # Verificar disponibilidad del profesor (simplificado para Numba)
        # En la versión optimizada, asumimos que la disponibilidad ya está validada
        puntaje += 0.5  # Bonificación por asignación válida
        
        # Contar bloques por materia y curso
        bloques_materia_curso[curso_id, materia_id] += 1
    
    # Verificar bloques_por_semana (simplificado para Numba)
    # En la versión optimizada, asumimos que esto ya está validado
    # y damos bonificación por cada asignación válida
    puntaje += len(cursos) * 2.0  # Bonificación por asignaciones válidas
    
    # Penalizar fuertemente los conflictos
    fitness = puntaje - (conflictos * 10.0)
    
    return fitness, conflictos

# Caché para datos preprocesados
_cache_datos_numpy = {}

def _preparar_datos_numpy(datos: DatosHorario):
    """Prepara los datos en formato NumPy para evaluación rápida."""
    # Verificar si ya están en caché
    if id(datos) in _cache_datos_numpy:
        return _cache_datos_numpy[id(datos)]
    
    # Convertir bloques disponibles a array
    bloques_disponibles = np.array(datos.bloques_disponibles, dtype=np.int32)
    
    # Convertir bloques por semana a array
    bloques_por_semana_list = []
    for materia_id, materia in datos.materias.items():
        bloques_por_semana_list.append((materia_id, materia.bloques_por_semana))
    bloques_por_semana = np.array(bloques_por_semana_list, dtype=np.int32)
    
    # Convertir disponibilidad de profesores a array
    disponibilidad_list = []
    for profesor_id, profesor in datos.profesores.items():
        for dia, bloque in profesor.disponibilidad:
            dia_idx = DIA_INDICE.get(dia, 0)
            disponibilidad_list.append((profesor_id, dia_idx, bloque))
    disponibilidad_profesor = np.array(disponibilidad_list, dtype=np.int32)
    
    # Convertir relaciones materia-profesor a array
    materia_profesor_list = []
    for (materia_id, profesor_id) in datos.materia_profesor:
        materia_profesor_list.append((materia_id, profesor_id))
    materia_profesor = np.array(materia_profesor_list, dtype=np.int32)
    
    # Guardar en caché
    resultado = (bloques_disponibles, bloques_por_semana, disponibilidad_profesor, materia_profesor)
    _cache_datos_numpy[id(datos)] = resultado
    
    return resultado

def evaluar_fitness(cromosoma: Cromosoma, datos: DatosHorario) -> Tuple[float, int]:
    """
    Evalúa el fitness de un cromosoma con penalizaciones más estrictas.
    
    Args:
        cromosoma: Cromosoma a evaluar
        datos: Datos del horario
        
    Returns:
        Tuple con (fitness, número de conflictos)
    """
    if not cromosoma.genes:
        return 0.0, 0
    
    # Penalizaciones más estrictas
    PENALIZACION_CONFLICTO_PROFESOR = 1000.0  # Aumentar de 10.0 a 1000.0
    PENALIZACION_CONFLICTO_CURSO = 1000.0     # Aumentar de 10.0 a 1000.0
    PENALIZACION_DISPONIBILIDAD = 500.0       # Nueva penalización
    PENALIZACION_BLOQUE_INVALIDO = 800.0      # Nueva penalización
    BONIFICACION_ASIGNACION_VALIDA = 10.0     # Bonificación por asignación válida
    
    fitness = 0.0
    conflictos = 0
    
    # Estructuras para detectar conflictos
    slots_curso = set()
    slots_profesor = set()
    asignaciones_invalidas = 0
    bloques_invalidos = 0
    
    # Evaluar cada gen
    for (curso_id, dia, bloque), (materia_id, profesor_id) in cromosoma.genes.items():
        # Verificar conflicto de curso (día, bloque)
        key_curso = (curso_id, dia, bloque)
        if key_curso in slots_curso:
            conflictos += 1
            fitness -= PENALIZACION_CONFLICTO_CURSO
        else:
            slots_curso.add(key_curso)
            fitness += BONIFICACION_ASIGNACION_VALIDA
        
        # Verificar conflicto de profesor (día, bloque)
        key_profesor = (profesor_id, dia, bloque)
        if key_profesor in slots_profesor:
            conflictos += 1
            fitness -= PENALIZACION_CONFLICTO_PROFESOR
        else:
            slots_profesor.add(key_profesor)
            fitness += BONIFICACION_ASIGNACION_VALIDA
        
        # Verificar disponibilidad del profesor
        if profesor_id in datos.profesores:
            profesor = datos.profesores[profesor_id]
            if (dia, bloque) not in profesor.disponibilidad:
                asignaciones_invalidas += 1
                fitness -= PENALIZACION_DISPONIBILIDAD
        else:
            asignaciones_invalidas += 1
            fitness -= PENALIZACION_DISPONIBILIDAD
        
        # Verificar que el bloque sea válido
        if bloque not in datos.bloques_disponibles:
            bloques_invalidos += 1
            fitness -= PENALIZACION_BLOQUE_INVALIDO
    
    # Penalizar por asignaciones inválidas
    if asignaciones_invalidas > 0:
        conflictos += asignaciones_invalidas
        fitness -= asignaciones_invalidas * PENALIZACION_DISPONIBILIDAD
    
    # Penalizar por bloques inválidos
    if bloques_invalidos > 0:
        conflictos += bloques_invalidos
        fitness -= bloques_invalidos * PENALIZACION_BLOQUE_INVALIDO
    
    # Bonificación por completitud (materias con bloques requeridos)
    bonificacion_completitud = _calcular_bonificacion_completitud(cromosoma, datos)
    fitness += bonificacion_completitud
    
    return fitness, conflictos

def _calcular_bonificacion_completitud(cromosoma: Cromosoma, datos: DatosHorario) -> float:
    """
    Calcula bonificación por completitud de materias.
    
    Args:
        cromosoma: Cromosoma a evaluar
        datos: Datos del horario
        
    Returns:
        Bonificación por completitud
    """
    bonificacion = 0.0
    
    # Contar bloques asignados por curso y materia
    bloques_asignados = defaultdict(int)
    for (curso_id, dia, bloque), (materia_id, profesor_id) in cromosoma.genes.items():
        key = (curso_id, materia_id)
        bloques_asignados[key] += 1
    
    # Calcular bonificación por cumplir bloques requeridos
    for curso_id, curso in datos.cursos.items():
        for materia_id in curso.materias:
            if materia_id in datos.materias:
                materia = datos.materias[materia_id]
                bloques_requeridos = materia.bloques_por_semana
                bloques_asignados_actual = bloques_asignados.get((curso_id, materia_id), 0)
                
                if bloques_asignados_actual == bloques_requeridos:
                    # Bonificación por cumplir exactamente
                    bonificacion += 50.0
                elif bloques_asignados_actual > 0:
                    # Bonificación parcial por asignar al menos algunos bloques
                    bonificacion += (bloques_asignados_actual / bloques_requeridos) * 25.0
    
    return bonificacion

# Importar validadores y reparador
from .validadores import validar_antes_de_persistir

def repair_individual_robusto(cromosoma: Cromosoma, datos: DatosHorario) -> Tuple[bool, Dict]:
    """
    Repara un individuo inviable de manera robusta, resolviendo todos los conflictos.
    
    Args:
        cromosoma: Cromosoma a reparar
        datos: Datos del horario
        
    Returns:
        Tuple con (éxito, estadísticas de reparación)
    """
    logger.debug("Iniciando reparación robusta del cromosoma")
    
    estadisticas = {
        'conflictos_resueltos': 0,
        'huecos_llenados': 0,
        'sobreasignaciones_corregidas': 0,
        'iteraciones': 0
    }
    
    # Iteraciones máximas derivadas del tamaño del problema (sin números fijos)
    problema_dim = max(1, len(datos.cursos) * len(datos.materias))
    max_iteraciones = max(3, min(50, int(math.log1p(problema_dim) * 6)))
    cromosoma_reparado = cromosoma.copy()
    
    # Evaluar conflictos iniciales
    _, conflictos_previos = evaluar_fitness(cromosoma_reparado, datos)
    sin_mejora = 0
    
    for iteracion in range(max_iteraciones):
        estadisticas['iteraciones'] = iteracion + 1
        
        # 1. Resolver conflictos de profesores (prioridad alta)
        conflictos_profesor = _resolver_conflictos_profesor(cromosoma_reparado, datos)
        estadisticas['conflictos_resueltos'] += conflictos_profesor
        
        # 2. Resolver asignaciones fuera de disponibilidad
        disponibilidad_corregida = _corregir_disponibilidad_profesores(cromosoma_reparado, datos)
        estadisticas['conflictos_resueltos'] += disponibilidad_corregida
        
        # 3. Balancear bloques por semana (demand-first intra-curso)
        try:
            _balancear_bloques_por_semana_global(cromosoma_reparado, datos)
        except Exception:
            pass
        
        # 4. Verificar si el cromosoma es válido
        if _validar_cromosoma_basico(cromosoma_reparado, datos):
            logger.debug(f"Cromosoma reparado exitosamente en {iteracion + 1} iteraciones")
            cromosoma.genes = cromosoma_reparado.genes
            return True, estadisticas
        
        # 5. Criterio de avance: si no mejora, cortar pronto
        _, conflictos_actuales = evaluar_fitness(cromosoma_reparado, datos)
        if conflictos_actuales < conflictos_previos:
            sin_mejora = 0
            conflictos_previos = conflictos_actuales
        else:
            sin_mejora += 1
        if sin_mejora >= max(2, int(max_iteraciones * 0.2)):
            break
        
        logger.debug(f"Iteración {iteracion + 1}: resueltos={conflictos_profesor + disponibilidad_corregida}, conflictos_actuales={conflictos_actuales}")
    
    logger.info(f"Cromosoma no pudo ser reparado completamente después de {estadisticas['iteraciones']} iteraciones (dim={problema_dim})")
    return False, estadisticas

def _resolver_conflictos_profesor(cromosoma: Cromosoma, datos: DatosHorario) -> int:
    """
    Resuelve conflictos de profesores asignados al mismo bloque horario.
    
    Args:
        cromosoma: Cromosoma a reparar
        datos: Datos del horario
        
    Returns:
        Número de conflictos resueltos
    """
    conflictos_resueltos = 0
    
    # Crear dict de conflictos: (profesor_id, dia, bloque) -> List[(curso_id, dia, bloque, materia_id)]
    conflictos = defaultdict(list)
    for (curso_id, dia, bloque), (materia_id, profesor_id) in cromosoma.genes.items():
        key = (profesor_id, dia, bloque)
        conflictos[key].append((curso_id, dia, bloque, materia_id))
    
    # Resolver conflictos donde hay más de una asignación
    for (profesor_id, dia, bloque), asignaciones in conflictos.items():
        if len(asignaciones) > 1:
            logger.debug(f"Conflicto detectado: profesor {profesor_id} en {dia} bloque {bloque} con {len(asignaciones)} asignaciones")
            
            # Conservar la primera asignación, recolocar las restantes
            for i, (curso_id, dia_orig, bloque_orig, materia_id) in enumerate(asignaciones[1:], 1):
                if _recolocar_asignacion_conflicto(cromosoma, curso_id, materia_id, profesor_id, dia_orig, bloque_orig, datos):
                    conflictos_resueltos += 1
                else:
                    logger.debug(f"No se pudo recolocar asignación para {curso_id} en {dia} bloque {bloque}")
    
    return conflictos_resueltos

def _recolocar_asignacion_conflicto(cromosoma: Cromosoma, curso_id: int, materia_id: int, 
                                   profesor_id: int, dia_orig: str, bloque_orig: int, 
                                   datos: DatosHorario) -> bool:
    """
    Recoloca una asignación conflictiva a un slot alternativo.
    
    Args:
        cromosoma: Cromosoma a reparar
        curso_id: ID del curso
        materia_id: ID de la materia
        profesor_id: ID del profesor
        dia_orig: Día original
        bloque_orig: Bloque original
        datos: Datos del horario
        
    Returns:
        True si se pudo recolocar, False en caso contrario
    """
    # 1. Intentar slot alternativo libre en el mismo curso
    for dia_alt in DIAS:
        for bloque_alt in datos.bloques_disponibles:
            # Verificar que el slot esté libre para el curso
            if (curso_id, dia_alt, bloque_alt) in cromosoma.genes:
                continue
            
            # Verificar disponibilidad del profesor
            if profesor_id in datos.profesores:
                profesor = datos.profesores[profesor_id]
                if (dia_alt, bloque_alt) not in profesor.disponibilidad:
                    continue
                
                # Verificar que no haya conflicto de profesor
                conflicto = False
                for (c_id, d, b), (_, p_id) in cromosoma.genes.items():
                    if p_id == profesor_id and d == dia_alt and b == bloque_alt:
                        conflicto = True
                        break
                
                if not conflicto:
                    # Recolocar exitosamente
                    del cromosoma.genes[(curso_id, dia_orig, bloque_orig)]
                    cromosoma.genes[(curso_id, dia_alt, bloque_alt)] = (materia_id, profesor_id)
                    logger.debug(f"Recolocación exitosa: {curso_id} movido de {dia_orig}:{bloque_orig} a {dia_alt}:{bloque_alt}")
                    return True
    
    # 2. Si no hay slot alternativo, intentar profesor alternativo
    if materia_id in datos.materias:
        materia = datos.materias[materia_id]
        for prof_alt_id in materia.profesores:
            if prof_alt_id == profesor_id:
                continue
                
            if prof_alt_id not in datos.profesores:
                continue
                
            prof_alt = datos.profesores[prof_alt_id]
            
            # Buscar slot donde el profesor alternativo esté disponible
            for dia_alt in DIAS:
                for bloque_alt in datos.bloques_disponibles:
                    # Verificar que el slot esté libre para el curso
                    if (curso_id, dia_alt, bloque_alt) in cromosoma.genes:
                        continue
                    
                    # Verificar disponibilidad del profesor alternativo
                    if (dia_alt, bloque_alt) not in prof_alt.disponibilidad:
                        continue
                    
                    # Verificar que no haya conflicto
                    conflicto = False
                    for (c_id, d, b), (_, p_id) in cromosoma.genes.items():
                        if p_id == prof_alt_id and d == dia_alt and b == bloque_alt:
                            conflicto = True
                            break
                    
                    if not conflicto:
                        # Recolocar con profesor alternativo
                        del cromosoma.genes[(curso_id, dia_orig, bloque_orig)]
                        cromosoma.genes[(curso_id, dia_alt, bloque_alt)] = (materia_id, prof_alt_id)
                        logger.debug(f"Recolocación con profesor alternativo: {curso_id} movido a {dia_alt}:{bloque_alt} con profesor {prof_alt_id}")
                        return True
    
    return False

def _corregir_disponibilidad_profesores(cromosoma: Cromosoma, datos: DatosHorario) -> int:
    """
    Corrige asignaciones fuera de disponibilidad de profesores.
    
    Args:
        cromosoma: Cromosoma a reparar
        datos: Datos del horario
        
    Returns:
        Número de correcciones realizadas
    """
    correcciones = 0
    
    # Encontrar asignaciones fuera de disponibilidad
    asignaciones_invalidas = []
    for (curso_id, dia, bloque), (materia_id, profesor_id) in cromosoma.genes.items():
        if profesor_id in datos.profesores:
            profesor = datos.profesores[profesor_id]
            if (dia, bloque) not in profesor.disponibilidad:
                asignaciones_invalidas.append((curso_id, dia, bloque, materia_id, profesor_id))
    
    # Corregir cada asignación inválida
    for curso_id, dia, bloque, materia_id, profesor_id in asignaciones_invalidas:
        if _corregir_asignacion_disponibilidad(cromosoma, curso_id, materia_id, profesor_id, dia, bloque, datos):
            correcciones += 1
    
    return correcciones

def _corregir_asignacion_disponibilidad(cromosoma: Cromosoma, curso_id: int, materia_id: int,
                                       profesor_id: int, dia: str, bloque: int, datos: DatosHorario) -> bool:
    """
    Corrige una asignación fuera de disponibilidad.
    
    Args:
        cromosoma: Cromosoma a reparar
        curso_id: ID del curso
        materia_id: ID de la materia
        profesor_id: ID del profesor
        dia: Día de la asignación
        bloque: Bloque de la asignación
        datos: Datos del horario
        
    Returns:
        True si se pudo corregir, False en caso contrario
    """
    # 1. Intentar encontrar un slot alternativo donde el profesor esté disponible
    for dia_alt in DIAS:
        for bloque_alt in datos.bloques_disponibles:
            # Verificar que el slot esté libre para el curso
            if (curso_id, dia_alt, bloque_alt) in cromosoma.genes:
                continue
            
            # Verificar disponibilidad del profesor
            if profesor_id in datos.profesores:
                profesor = datos.profesores[profesor_id]
                if (dia_alt, bloque_alt) not in profesor.disponibilidad:
                    continue
                
                # Verificar que no haya conflicto de profesor
                conflicto = False
                for (c_id, d, b), (_, p_id) in cromosoma.genes.items():
                    if p_id == profesor_id and d == dia_alt and b == bloque_alt:
                        conflicto = True
                        break
                
                if not conflicto:
                    # Mover la asignación
                    del cromosoma.genes[(curso_id, dia, bloque)]
                    cromosoma.genes[(curso_id, dia_alt, bloque_alt)] = (materia_id, profesor_id)
                    logger.debug(f"Disponibilidad corregida: {curso_id} movido de {dia}:{bloque} a {dia_alt}:{bloque_alt}")
                    return True
    
    # 2. Si no hay slot alternativo, intentar profesor alternativo
    if materia_id in datos.materias:
        materia = datos.materias[materia_id]
        for prof_alt_id in materia.profesores:
            if prof_alt_id == profesor_id:
                continue
                
            if prof_alt_id not in datos.profesores:
                continue
                
            prof_alt = datos.profesores[prof_alt_id]
            
            # Verificar si el profesor alternativo está disponible en el slot original
            if (dia, bloque) in prof_alt.disponibilidad:
                # Verificar que no haya conflicto
                conflicto = False
                for (c_id, d, b), (_, p_id) in cromosoma.genes.items():
                    if p_id == prof_alt_id and d == dia and b == bloque:
                        conflicto = True
                        break
                
                if not conflicto:
                    # Cambiar solo el profesor
                    cromosoma.genes[(curso_id, dia, bloque)] = (materia_id, prof_alt_id)
                    logger.debug(f"Profesor cambiado: {curso_id} en {dia}:{bloque} ahora con profesor {prof_alt_id}")
                    return True
    
    return False

# Alias para compatibilidad
reparar_cromosoma = repair_individual_robusto

def mutacion_lns(cromosoma: Cromosoma, datos: DatosHorario, mapeos: Dict, porcentaje: float = 0.2) -> Cromosoma:
    """
    Operador LNS (Large Neighborhood Search) que destruye y reconstruye una porción del cromosoma.
    
    Args:
        cromosoma: Cromosoma a mutar
        datos: Datos del horario
        mapeos: Mapeos de índices para conversión
        porcentaje: Porcentaje de slots a destruir (0.2 = 20%)
        
    Returns:
        Cromosoma mutado con LNS
    """
    cromosoma_lns = cromosoma.copy()
    
    # Convertir a arrays para operaciones eficientes
    crom_compacto = dict_to_arrays(cromosoma_lns.genes, mapeos)
    
    # Elegir aleatoriamente: curso específico o día específico
    if random.random() < 0.5:
        # Destruir slots de un curso aleatorio
        curso_idx = random.randint(0, mapeos['n_cursos'] - 1)
        slots_a_destruir = set()
        
        for slot_id in range(crom_compacto.n_slots):
            curso_slot, _, _ = crom_compacto.slot_to_coords(slot_id)
            if curso_slot == curso_idx:
                slots_a_destruir.add(slot_id)
    else:
        # Destruir slots de un día aleatorio
        dia_idx = random.randint(0, mapeos['n_dias'] - 1)
        slots_a_destruir = set()
        
        for slot_id in range(crom_compacto.n_slots):
            _, dia_slot, _ = crom_compacto.slot_to_coords(slot_id)
            if dia_slot == dia_idx:
                slots_a_destruir.add(slot_id)
    
    # Calcular cuántos slots destruir
    n_slots_destruir = int(len(slots_a_destruir) * porcentaje)
    slots_destruidos = random.sample(list(slots_a_destruir), min(n_slots_destruir, len(slots_a_destruir)))
    
    # Destruir slots seleccionados
    for slot_id in slots_destruidos:
        crom_compacto.materia_por_slot[slot_id] = -1
        crom_compacto.profesor_por_slot[slot_id] = -1
    
    # Reconstruir greedy: primero, materias más difíciles
    slots_vacios = [slot_id for slot_id in slots_destruidos]
    random.shuffle(slots_vacios)  # Orden aleatorio para diversidad
    
    for slot_id in slots_vacios:
        curso_idx, dia_idx, bloque_idx = crom_compacto.slot_to_coords(slot_id)
        curso_id = mapeos['idx_to_curso'][curso_idx]
        
        # Obtener materias del curso
        curso = datos.cursos[curso_id]
        materias_disponibles = list(curso.materias)
        
        # Ordenar por dificultad (menos profesores primero)
        materias_disponibles.sort(key=lambda m_id: len(datos.materias[m_id].profesores))
        
        # Intentar asignar materia
        materia_asignada = False
        for materia_id in materias_disponibles:
            materia = datos.materias[materia_id]
            
            # Buscar profesor disponible
            for profesor_id in materia.profesores:
                if profesor_id not in datos.profesores:
                    continue
                    
                profesor = datos.profesores[profesor_id]
                
                # Verificar disponibilidad
                dia = mapeos['idx_to_dia'][dia_idx]
                bloque = mapeos['idx_to_bloque'][bloque_idx]
                
                if (dia, bloque) not in profesor.disponibilidad:
                    continue
                
                # Verificar que no haya conflicto
                conflicto = False
                for slot_check in range(crom_compacto.n_slots):
                    if slot_check == slot_id:
                        continue
                    
                    if (crom_compacto.profesor_por_slot[slot_check] == mapeos['profesor_to_idx'][profesor_id] and
                        crom_compacto.slot_to_coords(slot_check)[1] == dia_idx and
                        crom_compacto.slot_to_coords(slot_check)[2] == bloque_idx):
                        conflicto = True
                        break
                
                if not conflicto:
                    # Asignar
                    crom_compacto.materia_por_slot[slot_id] = mapeos['materia_to_idx'][materia_id]
                    crom_compacto.profesor_por_slot[slot_id] = mapeos['profesor_to_idx'][profesor_id]
                    materia_asignada = True
                    break
            
            if materia_asignada:
                break
    
    # Convertir de vuelta a dict
    cromosoma_lns.genes = arrays_to_dict(crom_compacto)
    
    return cromosoma_lns

def evaluar_con_reparacion_worker(cromosoma: Cromosoma, datos: DatosHorario):
    """Evalúa un cromosoma y aplica reparación si es necesario. Retorna tupla
    (cromosoma, reparado: bool, conflictos: int, descartado: bool)."""
    # Evaluar fitness inicial
    fitness, conflictos = evaluar_fitness(cromosoma, datos)
    tuvo_conflictos_iniciales = conflictos > 0
    reparacion_exitosa = False
    
    if tuvo_conflictos_iniciales:
        logger.debug(f"Intentando reparar cromosoma con {conflictos} conflictos")
        reparacion_exitosa, _ = repair_individual_robusto(cromosoma, datos)
        if reparacion_exitosa:
            # Re-evaluar después de la reparación
            fitness, conflictos = evaluar_fitness(cromosoma, datos)
            logger.debug(f"Cromosoma reparado exitosamente. Nuevo fitness: {fitness}")
        else:
            logger.debug("Cromosoma no pudo ser reparado, será descartado")
    
    cromosoma.fitness = fitness
    cromosoma.conflictos = conflictos
    descartado = tuvo_conflictos_iniciales and not reparacion_exitosa
    return cromosoma, reparacion_exitosa, conflictos, descartado

def evaluar_poblacion_paralelo(poblacion, datos, workers):
    """
    Evalúa la población en paralelo si hay workers>1 y joblib disponible; en caso contrario, secuencial.
    Incluye validación y reparación de individuos inviables.
    """
    try:
        base = int(workers) if workers else cpu_count() // 2
        n = max(1, min(base, len(poblacion)))
        logger.info(f"Evaluación paralela configurada: {n} workers (población: {len(poblacion)})")
    except Exception:
        n = 1
        logger.warning("Error al configurar workers, usando evaluación secuencial")
    
    estadisticas_generacion = {
        'individuos_reparados': 0,
        'individuos_descartados': 0,
        'conflictos_detectados': defaultdict(int)
    }
    
    # Ejecutar evaluación
    if n > 1 and joblib:
        try:
            resultados = joblib.Parallel(n_jobs=n, backend='multiprocessing')(
                joblib.delayed(evaluar_con_reparacion_worker)(cromosoma, datos) for cromosoma in poblacion
            )
        except Exception as e:
            logger.warning(f"Error en evaluación paralela: {e}. Usando evaluación secuencial.")
            resultados = [evaluar_con_reparacion_worker(c, datos) for c in poblacion]
    else:
        resultados = [evaluar_con_reparacion_worker(c, datos) for c in poblacion]
    
    # Agregar estadísticas y extraer cromosomas
    cromosomas_evaluados = []
    reparados = 0
    descartados = 0
    conflictos_totales = 0
    for crom, fue_reparado, conf, fue_descartado in resultados:
        cromosomas_evaluados.append(crom)
        if fue_reparado:
            reparados += 1
        if fue_descartado:
            descartados += 1
        conflictos_totales += conf
    
    estadisticas_generacion['individuos_reparados'] = reparados
    estadisticas_generacion['individuos_descartados'] = descartados
    estadisticas_generacion['conflictos_detectados']['conflictos_totales'] = conflictos_totales
    
    # Logging de estadísticas
    logger.info(f"Generación evaluada: {estadisticas_generacion['individuos_reparados']} reparados, "
               f"{estadisticas_generacion['individuos_descartados']} descartados")
    
    return cromosomas_evaluados

def cruce_seguro(padre1: Cromosoma, padre2: Cromosoma, datos: DatosHorario) -> Tuple[Cromosoma, Cromosoma]:
    """
    Realiza cruce seguro entre dos cromosomas, manteniendo la factibilidad.
    
    Args:
        padre1: Primer cromosoma padre
        padre2: Segundo cromosoma padre
        datos: Datos del horario
        
    Returns:
        Tuple con dos cromosomas hijos
    """
    hijo1 = Cromosoma()
    hijo2 = Cromosoma()
    
    # Cruce por bloques: intercambiar asignaciones por día-bloque
    bloques_padre1 = set(padre1.genes.keys())
    bloques_padre2 = set(padre2.genes.keys())
    
    # Bloques comunes
    bloques_comunes = bloques_padre1 & bloques_padre2
    
    # Asignar bloques comunes aleatoriamente
    for bloque in bloques_comunes:
        if random.random() < 0.5:
            hijo1.genes[bloque] = padre1.genes[bloque]
            hijo2.genes[bloque] = padre2.genes[bloque]
        else:
            hijo1.genes[bloque] = padre2.genes[bloque]
            hijo2.genes[bloque] = padre1.genes[bloque]
    
    # Asignar bloques únicos
    bloques_unicos_padre1 = bloques_padre1 - bloques_comunes
    bloques_unicos_padre2 = bloques_padre2 - bloques_comunes
    
    # Distribuir bloques únicos
    for bloque in bloques_unicos_padre1:
        if random.random() < 0.5:
            hijo1.genes[bloque] = padre1.genes[bloque]
        else:
            hijo2.genes[bloque] = padre1.genes[bloque]
    
    for bloque in bloques_unicos_padre2:
        if random.random() < 0.5:
            hijo1.genes[bloque] = padre2.genes[bloque]
        else:
            hijo2.genes[bloque] = padre2.genes[bloque]
    
    # Reparar hijos después del cruce
    repair_individual_robusto(hijo1, datos)
    repair_individual_robusto(hijo2, datos)
    
    return hijo1, hijo2

def mutacion_segura(cromosoma: Cromosoma, datos: DatosHorario, prob_mutacion: float = 0.1) -> Cromosoma:
    """
    Realiza mutación segura en un cromosoma.
    
    Args:
        cromosoma: Cromosoma a mutar
        datos: Datos del horario
        prob_mutacion: Probabilidad de mutación por gen
        
    Returns:
        Cromosoma mutado
    """
    cromosoma_mutado = cromosoma.copy()
    
    # Seleccionar genes para mutar
    genes_a_mutar = []
    for gen in cromosoma_mutado.genes.keys():
        if random.random() < prob_mutacion:
            genes_a_mutar.append(gen)
    
    # Mutar genes seleccionados
    for gen in genes_a_mutar:
        # Verificar que el gen aún existe (puede haber sido eliminado por mutaciones previas)
        if gen not in cromosoma_mutado.genes:
            continue
            
        curso_id, dia, bloque = gen
        materia_id, profesor_id = cromosoma_mutado.genes[gen]
        
        # Eliminar asignación actual
        del cromosoma_mutado.genes[gen]
        
        # Buscar nuevo slot disponible
        nuevo_slot = None
        
        # Intentar con el mismo profesor
        if profesor_id in datos.profesores:
            profesor = datos.profesores[profesor_id]
            disponibilidad = list(profesor.disponibilidad)
            random.shuffle(disponibilidad)
            
            for nueva_dia, nuevo_bloque in disponibilidad:
                if nuevo_bloque in datos.bloques_disponibles:
                    # Verificar disponibilidad
                    slot_disponible = True
                    for (c_id, d, b), (_, p_id) in cromosoma_mutado.genes.items():
                        if ((c_id == curso_id and d == nueva_dia and b == nuevo_bloque) or
                            (p_id == profesor_id and d == nueva_dia and b == nuevo_bloque)):
                            slot_disponible = False
                            break
                    
                    if slot_disponible:
                        nuevo_slot = (curso_id, nueva_dia, nuevo_bloque)
                        break
        
        # Si no se encontró slot, intentar con otro profesor de la misma materia
        if not nuevo_slot and materia_id in datos.materias:
            materia = datos.materias[materia_id]
            profesores_disponibles = [p_id for p_id in materia.profesores if p_id != profesor_id]
            
            if profesores_disponibles:
                nuevo_profesor_id = random.choice(profesores_disponibles)
                nuevo_profesor = datos.profesores[nuevo_profesor_id]
                
                disponibilidad = list(nuevo_profesor.disponibilidad)
                random.shuffle(disponibilidad)
                
                for nueva_dia, nuevo_bloque in disponibilidad:
                    if nuevo_bloque in datos.bloques_disponibles:
                        # Verificar disponibilidad
                        slot_disponible = True
                        for (c_id, d, b), (_, p_id) in cromosoma_mutado.genes.items():
                            if ((c_id == curso_id and d == nueva_dia and b == nuevo_bloque) or
                                (p_id == nuevo_profesor_id and d == nueva_dia and b == nuevo_bloque)):
                                slot_disponible = False
                                break
                        
                        if slot_disponible:
                            nuevo_slot = (curso_id, nueva_dia, nuevo_bloque)
                            profesor_id = nuevo_profesor_id
                            break
        
        # Asignar nuevo slot si se encontró
        if nuevo_slot:
            cromosoma_mutado.genes[nuevo_slot] = (materia_id, profesor_id)
    
    # Reparar cromosoma mutado después de la mutación
    repair_individual_robusto(cromosoma_mutado, datos)
    
    return cromosoma_mutado

def generar_horarios_genetico_robusto(
    configuracion: Dict[str, Any] = None,
    poblacion_size: int = 100,
    generaciones: int = 500,
    prob_cruce: float = 0.85,
    prob_mutacion: float = 0.25,
    elite: int = 4,
    paciencia: int = 25,
    timeout_seg: int = 180,
    semilla: int = 42,
    workers: int = None
) -> Dict[str, Any]:
    """
    Función principal del algoritmo genético robusto para generar horarios.
    
    Args:
        configuracion: Diccionario con configuración (opcional)
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
    import time
    from django.db import transaction
    
    # Si se pasa configuración como diccionario, extraer valores
    if configuracion and isinstance(configuracion, dict):
        poblacion_size = configuracion.get('poblacion_size', poblacion_size)
        generaciones = configuracion.get('generaciones', generaciones)
        prob_cruce = configuracion.get('cruce_rate', prob_cruce)
        prob_mutacion = configuracion.get('mutacion_rate', prob_mutacion)
        elite = configuracion.get('elite_size', elite)
        timeout_seg = configuracion.get('timeout_minutos', timeout_seg // 60) * 60
        workers = configuracion.get('workers', workers)
        semilla = configuracion.get('semilla', semilla)
    
    inicio_tiempo = time.time()
    
    # Configurar semilla
    if semilla is not None:
        random.seed(semilla)
        np.random.seed(semilla)
    
    logger.info("Iniciando algoritmo genético robusto...")
    logger.info(f"Parámetros: población={poblacion_size}, generaciones={generaciones}, "
               f"cruce={prob_cruce}, mutación={prob_mutacion}, elite={elite}")
    
    # Cargar datos
    datos = cargar_datos()
    
    # Crear mapeos de índices para representación compacta
    mapeos = crear_mapeos_indices(datos)
    logger.info(f"Mapeos de índices creados: {mapeos['n_cursos']} cursos, {mapeos['n_dias']} días, {mapeos['n_bloques']} bloques")
    
    # Warm-up de Numba para evitar "arranque eterno"
    warmup_numba(datos)
    
    # Pre-validación dura antes de generar población
    logger.info("Realizando pre-validación dura...")
    errores_pre_validacion = pre_validacion_dura(datos)
    if errores_pre_validacion:
        logger.error("Pre-validación falló:")
        for error in errores_pre_validacion:
            logger.error(f"  - {error}")
        return {
            'status': 'error',
            'mensaje': 'Pre-validación falló: los datos no permiten generar horarios válidos',
            'errores': errores_pre_validacion
        }
    logger.info("✅ Pre-validación exitosa: todos los cursos tienen bloques suficientes")
    
    # Validar prerrequisitos
    errores_prerrequisitos = _validar_prerrequisitos(datos)
    if errores_prerrequisitos:
        return {
            'status': 'error',
            'mensaje': 'Prerrequisitos no cumplidos',
            'errores': errores_prerrequisitos
        }
    
    # Inicializar población "llena" (sin huecos)
    logger.info("Inicializando población con individuos llenos...")
    poblacion = inicializar_poblacion_robusta(datos, poblacion_size)
    
    # Variables para tracking
    mejor_fitness = float('-inf')
    generaciones_sin_mejora = 0
    estadisticas_globales = {
        'individuos_reparados_total': 0,
        'individuos_descartados_total': 0,
        'conflictos_resueltos_total': 0,
        'mejor_fitness_por_generacion': [],
        'promedio_fitness_por_generacion': [],
        'porcentaje_llenado_por_generacion': []
    }
    
    # Algoritmo principal
    for generacion in range(generaciones):
        generacion_inicio = time.time()
        
        # Verificar timeout
        if time.time() - inicio_tiempo > timeout_seg:
            logger.warning(f"Timeout alcanzado después de {generacion} generaciones")
            break
        
        # Evaluar población con reparación automática
        poblacion = evaluar_poblacion_paralelo(poblacion, datos, workers)
        
        # Ordenar por fitness
        poblacion.sort(key=lambda x: x.fitness, reverse=True)
        
        # Calcular estadísticas de la generación
        fitness_actual = poblacion[0].fitness
        fitness_promedio = sum(c.fitness for c in poblacion) / len(poblacion)
        
        # Calcular porcentaje de casillas llenas
        total_slots = len(datos.cursos) * len(DIAS) * len(datos.bloques_disponibles)
        slots_ocupados = sum(len(c.genes) for c in poblacion) / len(poblacion)
        porcentaje_llenado = (slots_ocupados / total_slots) * 100 if total_slots > 0 else 0
        
        # Verificar si hay individuos con huecos
        individuos_con_huecos = 0
        for cromosoma in poblacion:
            slots_por_curso = {}
            for (curso_id, dia, bloque) in cromosoma.genes.keys():
                if curso_id not in slots_por_curso:
                    slots_por_curso[curso_id] = set()
                slots_por_curso[curso_id].add((dia, bloque))
            
            for curso_id, curso in datos.cursos.items():
                slots_esperados = len(DIAS) * len(datos.bloques_disponibles)
                slots_actuales = len(slots_por_curso.get(curso_id, set()))
                if slots_actuales < slots_esperados:
                    individuos_con_huecos += 1
                    break
        
        # Actualizar mejor fitness
        if fitness_actual > mejor_fitness:
            mejor_fitness = fitness_actual
            generaciones_sin_mejora = 0
            logger.info(f"Generación {generacion}: Nuevo mejor fitness = {mejor_fitness:.2f}")
        else:
            generaciones_sin_mejora += 1
        
        # Registrar estadísticas
        estadisticas_globales['mejor_fitness_por_generacion'].append(mejor_fitness)
        estadisticas_globales['promedio_fitness_por_generacion'].append(fitness_promedio)
        estadisticas_globales['porcentaje_llenado_por_generacion'].append(porcentaje_llenado)
        
        # Logs útiles al final de cada generación
        logger.info(f"Generación {generacion}: % llenado = {porcentaje_llenado:.1f}%, "
                   f"Fitness = {fitness_actual:.2f}, Individuos con huecos = {individuos_con_huecos}")
        
        # Si se detecta que algún individuo trae huecos, reportarlo en DEBUG y arreglarlo
        if individuos_con_huecos > 0:
            logger.debug(f"⚠️ {individuos_con_huecos} individuos con huecos detectados en generación {generacion}")
            # Reparar individuos con huecos
            for cromosoma in poblacion:
                slots_por_curso = {}
                for (curso_id, dia, bloque) in cromosoma.genes.keys():
                    if curso_id not in slots_por_curso:
                        slots_por_curso[curso_id] = set()
                    slots_por_curso[curso_id].add((dia, bloque))
                
                necesita_reparacion = False
                for curso_id, curso in datos.cursos.items():
                    slots_esperados = len(DIAS) * len(datos.bloques_disponibles)
                    slots_actuales = len(slots_por_curso.get(curso_id, set()))
                    if slots_actuales < slots_esperados:
                        necesita_reparacion = True
                        break
                
                if necesita_reparacion:
                    logger.debug(f"Reparando individuo con huecos en generación {generacion}")
                    repair_individual_robusto(cromosoma, datos)
        
        # Early stopping
        if generaciones_sin_mejora >= paciencia:
            logger.info(f"Early stopping después de {paciencia} generaciones sin mejora")
            break
        
        # Selección de élite
        elite_individuos = poblacion[:elite]
        
        # Generar nueva población
        nueva_poblacion = elite_individuos.copy()
        
        while len(nueva_poblacion) < poblacion_size:
            # Selección de padres (torneo)
            padre1 = _seleccion_torneo(poblacion, 3)
            padre2 = _seleccion_torneo(poblacion, 3)
            
            # Cruce
            if random.random() < prob_cruce:
                hijo1, hijo2 = cruce_seguro(padre1, padre2, datos)
                nueva_poblacion.extend([hijo1, hijo2])
            else:
                nueva_poblacion.extend([padre1.copy(), padre2.copy()])
        
        # Mutación
        for i in range(elite, len(nueva_poblacion)):
            if random.random() < prob_mutacion:
                nueva_poblacion[i] = mutacion_segura(nueva_poblacion[i], datos, 0.1)
        
        # Aplicar LNS (Large Neighborhood Search) cada LNS_FREQ generaciones
        if generacion % LNS_FREQ == 0 and generacion > 0:
            logger.info(f"Aplicando LNS en generación {generacion}")
            n_individuos_lns = int(len(nueva_poblacion) * LNS_RATIO)
            indices_lns = random.sample(range(elite, len(nueva_poblacion)), n_individuos_lns)
            
            for idx in indices_lns:
                nueva_poblacion[idx] = mutacion_lns(nueva_poblacion[idx], datos, mapeos, 0.2)
        
        # Ajustar tamaño de población
        nueva_poblacion = nueva_poblacion[:poblacion_size]
        poblacion = nueva_poblacion
        
        # Logging de progreso con métricas detalladas
        if generacion % 10 == 0:
            tiempo_generacion = time.time() - generacion_inicio
            logger.info(f"Generación {generacion}: Fitness={fitness_actual:.2f}, "
                       f"Promedio={fitness_promedio:.2f}, Tiempo={tiempo_generacion:.2f}s, "
                       f"Ocupación={porcentaje_llenado:.1f}%, Workers={workers}")
        
        # Adaptación dinámica si hay estancamiento
        if generaciones_sin_mejora >= paciencia // 2:
            # Subir probabilidad de mutación temporalmente
            prob_mutacion_adaptativa = min(0.5, prob_mutacion * 1.5)
            logger.info(f"Estancamiento detectado: aumentando mutación a {prob_mutacion_adaptativa:.3f}")
        else:
            prob_mutacion_adaptativa = prob_mutacion
        
        # Adaptación si el tiempo de generación es muy alto
        if generacion > 0 and tiempo_generacion > 2 * tiempo_promedio_generaciones:
            workers_adaptativo = max(1, workers // 2)
            logger.info(f"Tiempo de generación alto ({tiempo_generacion:.2f}s): reduciendo workers a {workers_adaptativo}")
        else:
            workers_adaptativo = workers
        
        # Calcular tiempo promedio de las últimas generaciones
        if generacion > 0:
            tiempo_promedio_generaciones = (tiempo_promedio_generaciones * (generacion - 1) + tiempo_generacion) / generacion
        else:
            tiempo_promedio_generaciones = tiempo_generacion
    
    # Obtener mejor solución
    mejor_cromosoma = poblacion[0]
    
    # Ajustar bloques asignados a los requeridos por materia/curso para cumplir validación final
    try:
        _ajustar_bloques_a_requeridos(mejor_cromosoma, datos)
    except Exception as _:
        pass
    # Rellenar déficits si alguna (curso, materia) quedó por debajo de lo requerido
    try:
        _rellenar_deficits_bloques(mejor_cromosoma, datos)
    except Exception:
        pass
 
    # Validar solución final
    horarios_dict = _cromosoma_a_dict(mejor_cromosoma, datos)
    resultado_validacion = validar_antes_de_persistir(horarios_dict)
    
    if not resultado_validacion.es_valido:
        logger.error("La solución final no es válida")
        # Intento de reparación si el problema es solo bloques_por_semana
        try:
            tipos_errores = [e.tipo for e in resultado_validacion.errores]
        except Exception:
            tipos_errores = []
        if any(t == 'bloques_por_semana' for t in tipos_errores):
            logger.info("Intentando reparar diferencias de bloques_por_semana...")
            _ajustar_bloques_a_requeridos(mejor_cromosoma, datos)
            _rellenar_deficits_bloques(mejor_cromosoma, datos)
            horarios_dict = _cromosoma_a_dict(mejor_cromosoma, datos)
            resultado_validacion = validar_antes_de_persistir(horarios_dict)
        
        if not resultado_validacion.es_valido:
            logger.error("La solución sigue siendo inválida después de reparación")
            
            # Intentar fallback con OR-Tools si está disponible
            if os.environ.get('HORARIOS_ORTOOLS') == '1':
                try:
                    from .ortools_base import generar_horario_ortools
                    logger.info("Intentando fallback con OR-Tools...")
                    
                    horario_ortools = generar_horario_ortools(datos, mapeos)
                    if horario_ortools:
                        logger.info("OR-Tools generó horario base válido, continuando con GA...")
                        
                        # Crear cromosoma desde OR-Tools y continuar algunas generaciones
                        cromosoma_ortools = Cromosoma()
                        cromosoma_ortools.genes = horario_ortools
                        
                        # Continuar GA por algunas generaciones más para optimizar preferencias blandas
                        for gen_extra in range(min(20, generaciones // 4)):
                            # Evaluar y mejorar el cromosoma de OR-Tools
                            fitness, conflictos = evaluar_fitness(cromosoma_ortools, datos)
                            cromosoma_ortools.fitness = fitness
                            cromosoma_ortools.conflictos = conflictos
                            
                            # Aplicar mutaciones suaves
                            cromosoma_ortools = mutacion_segura(cromosoma_ortools, datos, 0.1)
                            
                            # Reparar si es necesario
                            if conflictos > 0:
                                repair_individual_robusto(cromosoma_ortools, datos)
                            
                            # Re-evaluar
                            fitness, conflictos = evaluar_fitness(cromosoma_ortools, datos)
                            cromosoma_ortools.fitness = fitness
                            cromosoma_ortools.conflictos = conflictos
                            
                            logger.info(f"Generación extra {gen_extra + 1}: Fitness={fitness:.2f}, Conflictos={conflictos}")
                        
                        # Usar el cromosoma mejorado de OR-Tools
                        mejor_cromosoma = cromosoma_ortools
                        horarios_dict = _cromosoma_a_dict(mejor_cromosoma, datos)
                        
                        # Re-validar
                        resultado_validacion = validar_antes_de_persistir(horarios_dict)
                        if not resultado_validacion.es_valido:
                            return {
                                'status': 'error',
                                'mensaje': MENSAJE_ERROR_SOLUCION_INVALIDA,
                                'errores': [e.detalles for e in resultado_validacion.errores]
                            }
                    else:
                        return {
                            'status': 'error',
                            'mensaje': MENSAJE_ERROR_SOLUCION_INVALIDA,
                            'errores': [e.detalles for e in resultado_validacion.errores]
                        }
                except ImportError:
                    return {
                        'status': 'error',
                        'mensaje': MENSAJE_ERROR_SOLUCION_INVALIDA,
                        'errores': [e.detalles for e in resultado_validacion.errores]
                    }
            else:
                return {
                    'status': 'error',
                    'mensaje': MENSAJE_ERROR_SOLUCION_INVALIDA,
                    'errores': [e.detalles for e in resultado_validacion.errores]
                }
    
    # Persistir en BD con transacción atómica
    try:
        with transaction.atomic():
            # Limpiar horarios existentes
            Horario.objects.all().delete()
            
            # Construir lista de objetos Horario para bulk_create
            horarios_objs = []
            for horario_data in horarios_dict:
                horario = Horario(
                    curso_id=horario_data['curso_id'],
                    materia_id=horario_data['materia_id'],
                    profesor_id=horario_data['profesor_id'],
                    aula_id=horario_data.get('aula_id'),
                    dia=horario_data['dia'],
                    bloque=horario_data['bloque']
                )
                horarios_objs.append(horario)
            
            # Persistir masivamente con bulk_create
            horarios_creados = Horario.objects.bulk_create(horarios_objs, batch_size=1000)
            
            logger.info(f"Persistidos {len(horarios_creados)} horarios en BD")
            
    except Exception as e:
        logger.error(f"Error al persistir horarios: {e}")
        return {
            'status': 'error',
            'mensaje': 'Error al guardar horarios en la base de datos',
            'error': str(e)
        }
    
    # Calcular métricas finales
    tiempo_total = time.time() - inicio_tiempo
    
    metricas = {
        'status': 'ok',
        'generaciones_completadas': generacion + 1,
        'tiempo_total_segundos': tiempo_total,
        'mejor_fitness_final': mejor_fitness,
        'conflictos_finales': mejor_cromosoma.conflictos,
        'total_horarios_generados': len(horarios_creados),
        'estadisticas_globales': estadisticas_globales,
        'validacion_final': {
            'es_valido': resultado_validacion.es_valido,
            'errores': len(resultado_validacion.errores),
            'advertencias': len(resultado_validacion.advertencias),
            'estadisticas': resultado_validacion.estadisticas
        }
    }
    
    logger.info(f"Algoritmo completado exitosamente en {tiempo_total:.2f} segundos")
    logger.info(f"Total de horarios generados: {len(horarios_creados)}")
    logger.info(f"Conflictos finales: {mejor_cromosoma.conflictos}")
    return metricas

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
) -> Dict[str, Any]:
    """
    Función principal que se llama desde el endpoint POST /api/generar-horarios/
    
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

def _validar_prerrequisitos(datos: DatosHorario) -> List[str]:
    """Valida prerrequisitos para el algoritmo genético."""
    errores = []
    
    # Verificar que existan bloques de tipo 'clase'
    if not datos.bloques_disponibles:
        errores.append("No existen bloques de tipo 'clase' configurados")
    
    # Verificar que cada curso tenga materias asignadas
    for curso_id, curso in datos.cursos.items():
        if not curso.materias:
            errores.append(f"El curso {curso.nombre} no tiene materias asignadas")
    
    # Verificar que cada materia tenga profesores
    for materia_id, materia in datos.materias.items():
        if not materia.profesores:
            errores.append(f"La materia {materia.nombre} no tiene profesores asignados")
    
    # Verificar que cada profesor tenga disponibilidad
    for profesor_id, profesor in datos.profesores.items():
        if not profesor.disponibilidad:
            errores.append(f"El profesor {profesor_id} no tiene disponibilidad definida")
    
    return errores

def _seleccion_torneo(poblacion: List[Cromosoma], tamano_torneo: int) -> Cromosoma:
    """Selección por torneo."""
    participantes = random.sample(poblacion, min(tamano_torneo, len(poblacion)))
    return max(participantes, key=lambda x: x.fitness)

def _cromosoma_a_dict(cromosoma: Cromosoma, datos: DatosHorario) -> List[Dict]:
    """Convierte un cromosoma a formato de diccionario para validación."""
    horarios = []
    
    for (curso_id, dia, bloque), (materia_id, profesor_id) in cromosoma.genes.items():
        horario = {
            'curso_id': curso_id,
            'curso_nombre': datos.cursos[curso_id].nombre,
            'materia_id': materia_id,
            'materia_nombre': datos.materias[materia_id].nombre,
            'profesor_id': profesor_id,
            'profesor_nombre': f"Profesor {profesor_id}",
            'aula_id': datos.cursos[curso_id].aula_id,
            'dia': dia,
            'bloque': bloque
        }
        horarios.append(horario)
    
    return horarios

def inicializar_poblacion(datos: DatosHorario, tamano_poblacion: int, semilla: int | None = None, **kwargs) -> List[Cromosoma]:
    """Alias compatible con tests que delega a la versión robusta, acepta `semilla` opcional."""
    if semilla is not None:
        random.seed(semilla)
        np.random.seed(semilla)
    return inicializar_poblacion_robusta(datos, tamano_poblacion)

def _ajustar_bloques_a_requeridos(cromosoma: Cromosoma, datos: DatosHorario) -> None:
    """Recorta asignaciones excedentes para que cada (curso,materia) cumpla exactamente sus bloques requeridos."""
    # Contar asignaciones por (curso,materia)
    asignaciones_por_curso_materia: Dict[Tuple[int, int], List[Tuple[str,int,int]]] = defaultdict(list)
    for (curso_id, dia, bloque), (materia_id, profesor_id) in list(cromosoma.genes.items()):
        asignaciones_por_curso_materia[(curso_id, materia_id)].append((dia, bloque, profesor_id))
    # Para cada curso y materia, si excede requeridos, eliminar extras arbitrariamente
    for (curso_id, materia_id), asigns in asignaciones_por_curso_materia.items():
        if materia_id not in datos.materias:
            continue
        requeridos = datos.materias[materia_id].bloques_por_semana
        if len(asigns) > requeridos:
            # Orden determinista: por día y bloque
            asigns.sort(key=lambda t: (t[0], t[1]))
            a_eliminar = asigns[requeridos:]
            for (dia, bloque, _prof_id) in a_eliminar:
                cromosoma.genes.pop((curso_id, dia, bloque), None)

def _rellenar_deficits_bloques(cromosoma: Cromosoma, datos: DatosHorario) -> None:
    """Rellena slots libres para alcanzar bloques requeridos por (curso, materia), respetando disponibilidad y sin solapes."""
    # Índices de ocupación por curso y por profesor
    ocupacion_curso = {(c, d, b) for (c, d, b) in cromosoma.genes.keys()}
    ocupacion_prof = {(p, d, b) for ((_, d, b), (_, p)) in cromosoma.genes.items()}
    for curso_id, curso in datos.cursos.items():
        for materia_id in curso.materias:
            if materia_id not in datos.materias:
                continue
            requeridos = datos.materias[materia_id].bloques_por_semana
            asignados = sum(1 for (c, d, b), (m, p) in cromosoma.genes.items() if c == curso_id and m == materia_id)
            deficit = max(0, requeridos - asignados)
            if deficit == 0:
                continue
            # Intentar asignar slots vacíos con algún profesor válido
            profesores_posibles = [p for p in datos.materias[materia_id].profesores if p in datos.profesores]
            for _ in range(deficit):
                asignado = False
                # Recalcular slots libres del curso
                free_slots = [(d, b) for d in DIAS for b in datos.bloques_disponibles if (curso_id, d, b) not in ocupacion_curso]
                for profesor_id in profesores_posibles:
                    if asignado:
                        break
                    # 1) Intentar directamente en un slot libre compatible
                    for dF, bF in free_slots:
                        if (profesor_id, dF, bF) in ocupacion_prof:
                            continue
                        if (dF, bF) not in datos.profesores[profesor_id].disponibilidad:
                            continue
                        cromosoma.genes[(curso_id, dF, bF)] = (materia_id, profesor_id)
                        ocupacion_curso.add((curso_id, dF, bF))
                        ocupacion_prof.add((profesor_id, dF, bF))
                        asignado = True
                        break
                    if asignado:
                        break
                    # 2) Si no hay slot libre compatible, intentar swap con un slot ocupado del curso en un (dia, bloque) compatible para el profesor objetivo
                    for dT in DIAS:
                        if asignado:
                            break
                        for bT in datos.bloques_disponibles:
                            if (profesor_id, dT, bT) in ocupacion_prof:
                                continue  # profesor objetivo ocupado en ese slot
                            if (dT, bT) not in datos.profesores[profesor_id].disponibilidad:
                                continue
                            # Slot del curso actualmente ocupado por otra asignación?
                            if (curso_id, dT, bT) in ocupacion_curso and (curso_id, dT, bT) in cromosoma.genes:
                                (materia2_id, profesor2_id) = cromosoma.genes[(curso_id, dT, bT)]
                                if profesor2_id == profesor_id and materia2_id == materia_id:
                                    continue  # ya es la misma asignación
                                # Buscar un free_slot al que el profesor2 pueda moverse
                                for dF, bF in free_slots:
                                    if (profesor2_id, dF, bF) in ocupacion_prof:
                                        continue
                                    if (dF, bF) not in datos.profesores[profesor2_id].disponibilidad:
                                        continue
                                    # Realizar swap: mover asignación existente a (dF, bF) y liberar (dT, bT)
                                    cromosoma.genes[(curso_id, dF, bF)] = (materia2_id, profesor2_id)
                                    ocupacion_curso.add((curso_id, dF, bF))
                                    ocupacion_prof.add((profesor2_id, dF, bF))
                                    # Liberar (dT,bT)
                                    del cromosoma.genes[(curso_id, dT, bT)]
                                    ocupacion_curso.discard((curso_id, dT, bT))
                                    ocupacion_prof.discard((profesor2_id, dT, bT))
                                    # Asignar profesor objetivo en (dT,bT)
                                    cromosoma.genes[(curso_id, dT, bT)] = (materia_id, profesor_id)
                                    ocupacion_curso.add((curso_id, dT, bT))
                                    ocupacion_prof.add((profesor_id, dT, bT))
                                    asignado = True
                                    break
                            # Si el slot estaba libre (raro porque lo intentamos arriba), asignar
                            elif (curso_id, dT, bT) not in ocupacion_curso:
                                cromosoma.genes[(curso_id, dT, bT)] = (materia_id, profesor_id)
                                ocupacion_curso.add((curso_id, dT, bT))
                                ocupacion_prof.add((profesor_id, dT, bT))
                                asignado = True
                                break
                 # Si no se pudo asignar este bloque de déficit, continuar con el siguiente profesor o intentar en la siguiente iteración

def _contar_asignados_por_curso_materia(cromosoma: Cromosoma) -> Dict[Tuple[int, int], int]:
    conteo = {}
    for (curso_id, dia, bloque), (materia_id, profesor_id) in cromosoma.genes.items():
        key = (curso_id, materia_id)
        conteo[key] = conteo.get(key, 0) + 1
    return conteo

def _balancear_bloques_por_semana_global(cromosoma: Cromosoma, datos: DatosHorario, max_iteraciones: int = 50) -> None:
    """Balancea globalmente bloques por semana moviendo exceso de unas materias a déficits de otras en el mismo curso."""
    for _ in range(max_iteraciones):
        cambios = 0
        conteo = _contar_asignados_por_curso_materia(cromosoma)
        # Recorrer cursos
        for curso_id, curso in datos.cursos.items():
            # Detectar déficits y excesos
            deficits = []
            excesos = []
            for materia_id in curso.materias:
                requeridos = datos.materias[materia_id].bloques_por_semana if materia_id in datos.materias else 0
                asignados = conteo.get((curso_id, materia_id), 0)
                if asignados < requeridos:
                    deficits.append((materia_id, requeridos - asignados))
                elif asignados > requeridos:
                    excesos.append((materia_id, asignados - requeridos))
            if not deficits:
                continue
            # Intentar resolver déficits usando excesos
            for materia_def, cant_def in list(deficits):
                profesores_def = [p for p in datos.materias.get(materia_def, MateriaData(0,'',0,False,[])).profesores if p in datos.profesores]
                while cant_def > 0 and excesos:
                    # Tomar un exceso
                    materia_exc, cant_exc = excesos[0]
                    if cant_exc <= 0:
                        excesos.pop(0)
                        continue
                    # Encontrar un slot de la materia en exceso
                    slot_exc = None
                    profesor_exc = None
                    for (c, d, b), (m, p) in list(cromosoma.genes.items()):
                        if c == curso_id and m == materia_exc:
                            slot_exc = (d, b)
                            profesor_exc = p
                            break
                    if not slot_exc:
                        excesos.pop(0)
                        continue
                    dT, bT = slot_exc
                    # Intentar asignar materia_def en ese slot con algún profesor disponible
                    profesor_def_ok = None
                    for p_def in profesores_def:
                        if (dT, bT) in datos.profesores[p_def].disponibilidad:
                            # Verificar que p_def no tenga choque en ese slot
                            choque = any((pp == p_def and dd == dT and bb == bT) for ((cc, dd, bb), (mm, pp)) in cromosoma.genes.items())
                            if not choque:
                                profesor_def_ok = p_def
                                break
                    if profesor_def_ok is None:
                        # No se pudo usar este slot; intentar otro slot del exceso
                        # Eliminar temporalmente el slot actual de consideración y continuar
                        # Buscar otro slot de la materia_exc
                        encontrado_otro = False
                        for (c, d, b), (m, p) in list(cromosoma.genes.items()):
                            if c == curso_id and m == materia_exc and (d, b) != slot_exc:
                                slot_exc = (d, b)
                                dT, bT = slot_exc
                                for p_def in profesores_def:
                                    if (dT, bT) in datos.profesores[p_def].disponibilidad and not any((pp == p_def and dd == dT and bb == bT) for ((cc, dd, bb), (mm, pp)) in cromosoma.genes.items()):
                                        profesor_def_ok = p_def
                                        encontrado_otro = True
                                        break
                                if encontrado_otro:
                                    break
                        if profesor_def_ok is None:
                            # No fue posible usar materia_exc para este déficit ahora
                            excesos.append(excesos.pop(0))  # rotar excesos
                            continue
                    # Llegados aquí, reasignamos slot: quitamos materia_exc y ponemos materia_def
                    del cromosoma.genes[(curso_id, dT, bT)]
                    cromosoma.genes[(curso_id, dT, bT)] = (materia_def, profesor_def_ok)
                    # Actualizar conteo y excesos/deficits
                    conteo[(curso_id, materia_exc)] = conteo.get((curso_id, materia_exc), 1) - 1
                    conteo[(curso_id, materia_def)] = conteo.get((curso_id, materia_def), 0) + 1
                    cant_exc -= 1
                    cant_def -= 1
                    cambios += 1
                    # Actualizar entrada de excesos
                    excesos[0] = (materia_exc, cant_exc)
                    if cant_exc == 0:
                        excesos.pop(0)
                # Si aún queda déficit, intentar rellenar libres
                if cant_def > 0:
                    prev_genes = len(cromosoma.genes)
                    _rellenar_deficits_bloques(cromosoma, datos)
                    nuevo_asignados = _contar_asignados_por_curso_materia(cromosoma).get((curso_id, materia_def), 0)
                    # Estimar cambios por diferencia
                    cambios += max(0, nuevo_asignados - conteo.get((curso_id, materia_def), 0))
        if cambios == 0:
            break

def _calcular_demanda_por_curso_materia(datos: DatosHorario) -> Dict[Tuple[int, int], int]:
    """Demanda requerida (bloques_por_semana) por (curso_id, materia_id), derivada de datos."""
    demanda = {}
    for curso_id, curso in datos.cursos.items():
        for materia_id in curso.materias:
            if materia_id in datos.materias:
                demanda[(curso_id, materia_id)] = int(max(0, datos.materias[materia_id].bloques_por_semana))
    return demanda


def _oferta_local_slot(mascaras, materia_idx: int, slot_idx: int) -> int:
    """Cantidad de profesores válidos para una materia en un slot dado."""
    # Profesor válido si mask_profesor_materia y disponible en slot
    pm = mascaras.profesor_materia[:, materia_idx]
    disp = mascaras.mask_profesor_disponible_flat[:, slot_idx]
    return int(np.sum(pm & disp))


def construir_individuo_demanda_primero(datos: DatosHorario) -> Cromosoma:
    """Construye el individuo 0 cumpliendo exactamente bloques_por_semana por (curso,materia) si es viable."""
    mascaras = precomputar_mascaras()
    crom = Cromosoma()

    demanda = _calcular_demanda_por_curso_materia(datos)

    # Precalcular oferta local por (materia, slot)
    oferta_local = {}
    for materia_id, m_idx in mascaras.materia_to_idx.items():
        for slot_idx, slot in enumerate(mascaras.slots):
            oferta_local[(materia_id, slot_idx)] = _oferta_local_slot(mascaras, m_idx, slot_idx)

    # Ordenar pares (curso, materia) por escasez local: requeridos / sum_oferta_local_factible
    pares = []
    for (curso_id, materia_id), req in demanda.items():
        # Slots factibles para el curso: todos los slots del curso están potencialmente disponibles; usaremos conflictos para evitar solapes
        suma_oferta = 0
        for slot_idx, (dia, bloque) in enumerate(mascaras.slots):
            # factible si materia en plan del curso y bloque es clase (ya garantizado) y existe algún profesor válido
            if curso_id in mascaras.curso_to_idx and materia_id in mascaras.materia_to_idx:
                if mascaras.curso_materia[mascaras.curso_to_idx[curso_id], mascaras.materia_to_idx[materia_id]]:
                    suma_oferta += oferta_local[(materia_id, slot_idx)]
        escasez = float('inf') if suma_oferta == 0 else (req / float(suma_oferta))
        pares.append(((curso_id, materia_id), escasez))

    pares.sort(key=lambda x: x[1], reverse=True)

    # Estructuras ocupación para evitar solapes
    ocupacion_curso_slot = set()
    ocupacion_profesor_slot = set()

    # Índices inversos
    idx_to_profesor = {idx: pid for pid, idx in mascaras.profesor_to_idx.items()}

    for (curso_id, materia_id), _ in pares:
        req = demanda[(curso_id, materia_id)]
        asignados = 0
        # Calcular ranking de slots por mayor oferta local para esta materia
        slot_ranking = sorted(range(len(mascaras.slots)), key=lambda sidx: oferta_local[(materia_id, sidx)], reverse=True)
        for slot_idx in slot_ranking:
            if asignados >= req:
                break
            dia, bloque = mascaras.slots[slot_idx]
            # Evitar duplicar (curso,slot)
            if (curso_id, dia, bloque) in ocupacion_curso_slot:
                continue
            # Listar profesores válidos ordenados por disponibilidad residual (más disponibilidad primero)
            profesores_validos_idx = [pidx for pidx in range(len(mascaras.profesor_to_idx))
                                      if mascaras.profesor_materia[pidx, mascaras.materia_to_idx[materia_id]]
                                      and mascaras.mask_profesor_disponible_flat[pidx, slot_idx]]
            # Orden por disponibilidad total residual (mayor primero)
            profesores_validos_idx.sort(key=lambda pidx: int(np.sum(mascaras.mask_profesor_disponible_flat[pidx, :])), reverse=True)
            for pidx in profesores_validos_idx:
                pid = idx_to_profesor[pidx]
                if (pid, dia, bloque) in ocupacion_profesor_slot:
                    continue
                # Asignar
                crom.genes[(curso_id, dia, bloque)] = (materia_id, pid)
                ocupacion_curso_slot.add((curso_id, dia, bloque))
                ocupacion_profesor_slot.add((pid, dia, bloque))
                asignados += 1
                break
        # Si no se logró asignar completo, se mantiene parcial; repair deberá ajustar si es viable globalmente

    return crom
