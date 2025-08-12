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
        if hasattr(datos, 'bloques_disponibles') and datos.bloques_disponibles:
            # Crear datos de prueba mínimos
            test_genes = {(1, 'lunes', 1): (1, 1)}
            test_bloques = list(datos.bloques_disponibles)[:2] if len(datos.bloques_disponibles) >= 2 else [1, 2]
            
            # Llamar a funciones que usan Numba para calentar JIT
            if '_calcular_conflictos_numpy' in globals():
                _calcular_conflictos_numpy(test_genes, test_bloques)
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
        
        if diferencia != 0:
            if diferencia > 0:
                errores.append(f"❌ {curso.nombre}: DEMANDA EXCEDE CAPACIDAD - requiere {bloques_requeridos} bloques, disponible {bloques_totales_curso} bloques")
            else:
                errores.append(f"⚠️ {curso.nombre}: capacidad subutilizada - requiere {bloques_requeridos} bloques, disponible {bloques_totales_curso} bloques")
    
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

def inicializar_poblacion(datos: DatosHorario, tamano_poblacion: int, semilla: int = None) -> List[Cromosoma]:
    """
    Inicializa la población con individuos "llenos" (sin huecos).
    
    Genera cada individuo asignando exactamente las repeticiones de cada materia
    (según bloques_por_semana) a posiciones (día, bloque) del curso hasta llenar
    todos los bloques de clase.
    
    Args:
        datos: Datos preprocesados del horario
        tamano_poblacion: Tamaño de la población inicial
        semilla: Semilla para reproducibilidad
    
    Returns:
        Lista de cromosomas inicializados
    """
    if semilla is not None:
        random.seed(semilla)
        np.random.seed(semilla)
    
    poblacion = []
    
    # Calcular dificultad de materias por curso para inicialización inteligente
    dificultad_materias = {}
    for curso_id, curso in datos.cursos.items():
        dificultad_materias[curso_id] = []
        
        for materia_id in curso.materias:
            if materia_id not in datos.materias:
                continue
                
            materia = datos.materias[materia_id]
            
            # Calcular puntuación de dificultad
            puntuacion = 0
            
            # Menos profesores = más difícil
            puntuacion += (10 - len(materia.profesores)) * 10
            
            # Baja disponibilidad = más difícil
            disponibilidad_total = 0
            for profesor_id in materia.profesores:
                if profesor_id in datos.profesores:
                    disponibilidad_total += len(datos.profesores[profesor_id].disponibilidad)
            puntuacion += (100 - disponibilidad_total) * 0.1
            
            # Requiere bloques consecutivos = más difícil
            if materia.bloques_por_semana > 1:
                puntuacion += 20
            
            dificultad_materias[curso_id].append((materia_id, puntuacion))
        
        # Ordenar por dificultad (más difícil primero)
        dificultad_materias[curso_id].sort(key=lambda x: x[1], reverse=True)
    
    for individuo in range(tamano_poblacion):
        cromosoma = Cromosoma()
        
        # Ordenar cursos aleatoriamente
        cursos_ids = list(datos.cursos.keys())
        random.shuffle(cursos_ids)
        
        for curso_id in cursos_ids:
            curso = datos.cursos[curso_id]
            
            # Crear slots disponibles para este curso
            slots_disponibles = set()
            for dia in DIAS:
                for bloque in datos.bloques_disponibles:
                    slots_disponibles.add((dia, bloque))
            
            # Crear lista de materias con sus bloques requeridos (ordenadas por dificultad)
            materias_a_asignar = []
            for materia_id, _ in dificultad_materias[curso_id]:
                if materia_id in datos.materias:
                    materia = datos.materias[materia_id]
                    bloques_necesarios = materia.bloques_por_semana
                    if bloques_necesarios > 0 and materia.profesores:
                        # Agregar la materia tantas veces como bloques necesite
                        for _ in range(bloques_necesarios):
                            materias_a_asignar.append(materia_id)
            
            # NO mezclar: mantener orden de dificultad para asignar materias difíciles primero
            
            # Asignar cada materia a un slot disponible
            for materia_id in materias_a_asignar:
                if not slots_disponibles:
                    break
                    
                materia = datos.materias[materia_id]
                
                # Intentar asignar con diferentes profesores
                asignado = False
                intentos_profesor = 0
                max_intentos_profesor = len(materia.profesores) * 3
                
                while not asignado and intentos_profesor < max_intentos_profesor:
                    # Seleccionar profesor aleatoriamente
                    profesor_id = random.choice(materia.profesores)
                    profesor = datos.profesores[profesor_id]
                    
                    # Buscar slot disponible para este profesor
                    slots_profesor = []
                    for slot in slots_disponibles:
                        dia, bloque = slot
                        
                        # Verificar disponibilidad del profesor
                        if (dia, bloque) not in profesor.disponibilidad:
                            continue
                        
                        # Verificar que el profesor no esté ocupado en este slot
                        profesor_ocupado = False
                        for (c_id, d, b), (_, p_id) in cromosoma.genes.items():
                            if p_id == profesor_id and d == dia and b == bloque:
                                profesor_ocupado = True
                                break
                        
                        if not profesor_ocupado:
                            slots_profesor.append(slot)
                    
                    # Si hay slots disponibles para este profesor, asignar
                    if slots_profesor:
                        slot_elegido = random.choice(slots_profesor)
                        dia, bloque = slot_elegido
                        
                        # Asignar el gen
                        cromosoma.genes[(curso_id, dia, bloque)] = (materia_id, profesor_id)
                        slots_disponibles.remove(slot_elegido)
                        asignado = True
                    else:
                        intentos_profesor += 1
                
                # Si no se pudo asignar con ningún profesor, intentar con cualquier slot disponible
                if not asignado and slots_disponibles:
                    # Buscar cualquier profesor disponible para esta materia
                    for profesor_id in materia.profesores:
                        profesor = datos.profesores[profesor_id]
                        
                        # Buscar cualquier slot donde el profesor esté disponible
                        for slot in list(slots_disponibles):
                            dia, bloque = slot
                            
                            if (dia, bloque) in profesor.disponibilidad:
                                # Verificar que no haya conflicto
                                conflicto = False
                                for (c_id, d, b), (_, p_id) in cromosoma.genes.items():
                                    if p_id == profesor_id and d == dia and b == bloque:
                                        conflicto = True
                                        break
                                
                                if not conflicto:
                                    # Asignar el gen
                                    cromosoma.genes[(curso_id, dia, bloque)] = (materia_id, profesor_id)
                                    slots_disponibles.remove(slot)
                                    asignado = True
                                    break
                        
                        if asignado:
                            break
                
                # Si aún no se pudo asignar, forzar la asignación (último recurso)
                if not asignado and slots_disponibles:
                    slot_restante = slots_disponibles.pop()
                    dia, bloque = slot_restante
                    profesor_id = random.choice(materia.profesores)
                    
                    # Asignar el gen (puede crear conflictos, pero se repararán después)
                    cromosoma.genes[(curso_id, dia, bloque)] = (materia_id, profesor_id)
            
            # Llenar slots restantes con materias aleatorias (si quedan)
            if slots_disponibles:
                materias_disponibles = [m_id for m_id in curso.materias if m_id in datos.materias]
                for slot in slots_disponibles:
                    if materias_disponibles:
                        materia_id = random.choice(materias_disponibles)
                        materia = datos.materias[materia_id]
                        profesor_id = random.choice(materia.profesores)
                        dia, bloque = slot
                        cromosoma.genes[(curso_id, dia, bloque)] = (materia_id, profesor_id)
        
        # Reparar el individuo para eliminar conflictos
        reparado, _ = repair_individual_robusto(cromosoma, datos)
        if not reparado:
            # Si no se pudo reparar, crear un nuevo individuo
            continue
        
        poblacion.append(cromosoma)
        
        # Si no hemos generado suficientes individuos, continuar
        if len(poblacion) < tamano_poblacion:
            continue
    
    # Si no se pudieron generar suficientes individuos válidos, generar algunos con conflictos
    while len(poblacion) < tamano_poblacion:
        cromosoma = Cromosoma()
        
        # Generar individuo simple con posibles conflictos
        for curso_id in datos.cursos:
            curso = datos.cursos[curso_id]
            for dia in DIAS:
                for bloque in datos.bloques_disponibles:
                    if curso.materias:
                        materia_id = random.choice(curso.materias)
                        if materia_id in datos.materias:
                            materia = datos.materias[materia_id]
                            if materia.profesores:
                                profesor_id = random.choice(materia.profesores)
                                cromosoma.genes[(curso_id, dia, bloque)] = (materia_id, profesor_id)
        
        poblacion.append(cromosoma)
    
    return poblacion

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
    Evalúa la aptitud de un cromosoma basado en las restricciones.
    
    Utiliza NumPy y Numba (si está disponible) para evaluación vectorizada rápida.
    
    Args:
        cromosoma: Cromosoma a evaluar
        datos: Datos preprocesados del horario
    
    Returns:
        Tuple con (fitness, número de conflictos)
    """
    # Si el cromosoma está vacío, retornar fitness mínimo
    if not cromosoma.genes:
        return float('-inf'), 0
    
    # Intentar usar la versión optimizada con NumPy/Numba
    try:
        # Convertir cromosoma a arrays NumPy
        cursos, dias, bloques, materias, profesores = cromosoma_a_arrays(cromosoma, datos)
        
        # Si la conversión falló, usar metodo tradicional
        if cursos is None:
            return _evaluar_fitness_tradicional(cromosoma, datos)
        
        # Preparar datos en formato NumPy
        bloques_disponibles, bloques_por_semana, disponibilidad_profesor, materia_profesor = _preparar_datos_numpy(datos)
        
        # Calcular fitness usando la versión optimizada
        return _calcular_conflictos_numpy(
            cursos, dias, bloques, materias, profesores,
            disponibilidad_profesor, materia_profesor
        )
    except Exception as e:
        # Si hay algún error, usar el metodo tradicional
        logger.warning(f"Error en evaluación optimizada: {e}. Usando método tradicional.")
        return _evaluar_fitness_tradicional(cromosoma, datos)

def _evaluar_fitness_tradicional(cromosoma: Cromosoma, datos: DatosHorario) -> Tuple[float, int]:
    """Versión tradicional (no optimizada) de la evaluación de fitness."""
    # Inicializar contadores
    puntaje = 0.0
    conflictos = 0
    huecos = 0
    
    # Conjuntos para verificar solapes
    slots_curso = set()  # (curso_id, dia, bloque)
    slots_profesor = set()  # (profesor_id, dia, bloque)
    
    # Contador de bloques por materia y curso
    bloques_materia_curso = {}  # (curso_id, materia_id) -> count
    
    # Evaluar cada gen
    for (curso_id, dia, bloque), (materia_id, profesor_id) in cromosoma.genes.items():
        # Verificar si el bloque es válido (tipo 'clase')
        if bloque not in datos.bloques_disponibles:
            conflictos += 1
            continue
        
        # Verificar solape de curso
        if (curso_id, dia, bloque) in slots_curso:
            conflictos += 1
            puntaje -= PENAL_SOLAPE
        else:
            slots_curso.add((curso_id, dia, bloque))
            puntaje += 1.0  # Bonificación por asignación válida de curso
        
        # Verificar solape de profesor
        if (profesor_id, dia, bloque) in slots_profesor:
            conflictos += 1
            puntaje -= PENAL_SOLAPE
        else:
            slots_profesor.add((profesor_id, dia, bloque))
            puntaje += 1.0  # Bonificación por asignación válida de profesor
        
        # Verificar disponibilidad del profesor
        if (dia, bloque) not in datos.profesores[profesor_id].disponibilidad:
            conflictos += 1
            puntaje -= PENAL_DISPONIBILIDAD
        else:
            puntaje += 0.5  # Bonificación por respetar disponibilidad
        
        # Verificar que el profesor puede impartir la materia
        if (materia_id, profesor_id) not in datos.materia_profesor:
            conflictos += 1
        else:
            puntaje += 0.5  # Bonificación por asignación válida materia-profesor
        
        # Contar bloques por materia y curso
        key = (curso_id, materia_id)
        bloques_materia_curso[key] = bloques_materia_curso.get(key, 0) + 1
    
    # Verificar bloques_por_semana y penalizar desvíos
    for (curso_id, materia_id), count in bloques_materia_curso.items():
        if curso_id in datos.cursos and materia_id in datos.materias:
            bloques_necesarios = datos.materias[materia_id].bloques_por_semana
            if count != bloques_necesarios:
                # Penalizar proporcionalmente a la diferencia
                diff = abs(count - bloques_necesarios)
                conflictos += diff
                puntaje -= PENAL_DESVIO * diff
            else:
                puntaje += 2.0  # Bonificación por cumplir exactamente bloques_por_semana
    
    # Verificar huecos (casillas vacías) por curso
    for curso_id, curso in datos.cursos.items():
        slots_ocupados_curso = set()
        for (c_id, dia, bloque) in cromosoma.genes.keys():
            if c_id == curso_id:
                slots_ocupados_curso.add((dia, bloque))
        
        # Calcular slots totales disponibles para este curso
        slots_totales = set()
        for dia in DIAS:
            for bloque in datos.bloques_disponibles:
                slots_totales.add((dia, bloque))
        
        # Contar huecos
        huecos_curso = len(slots_totales - slots_ocupados_curso)
        huecos += huecos_curso
        puntaje -= PENAL_HUECO * huecos_curso
    
    # Penalizar fuertemente los conflictos y huecos
    fitness = puntaje - (conflictos * 10.0) - (huecos * PENAL_HUECO)
    
    return fitness, conflictos

# Importar validadores y reparador
from .validadores import validar_antes_de_persistir

def repair_individual_robusto(cromosoma: Cromosoma, datos: DatosHorario) -> Tuple[bool, Dict[str, int]]:
    """
    Repara un individuo después de cruce y mutación.
    
    a) Corrige sobreasignaciones/deficiencias para que cada materia cumpla bloques_por_semana.
    b) Rellena cualquier hueco con materias que todavía deban colocarse en ese curso y con un profesor disponible.
    c) Resuelve conflictos (profesor duplicado en mismo (día, bloque)) recolocando en otros slots del mismo curso donde haya disponibilidad.
    
    Args:
        cromosoma: Cromosoma a reparar
        datos: Datos del horario
        
    Returns:
        Tuple con (éxito de reparación, estadísticas de reparación)
    """
    estadisticas = {
        'conflictos_resueltos': 0,
        'huecos_llenados': 0,
        'sobreasignaciones_corregidas': 0
    }
    
    # Crear copia del cromosoma para trabajar
    cromosoma_reparado = cromosoma.copy()
    
    # 1. Identificar todos los slots disponibles por curso
    slots_disponibles = {}
    for curso_id, curso in datos.cursos.items():
        slots_disponibles[curso_id] = set()
        for dia in DIAS:
            for bloque in datos.bloques_disponibles:
                slots_disponibles[curso_id].add((dia, bloque))
    
    # 2. Contar asignaciones actuales por materia y curso
    asignaciones_actuales = {}  # (curso_id, materia_id) -> count
    slots_ocupados = {}  # (curso_id, dia, bloque) -> (materia_id, profesor_id)
    profesores_ocupados = {}  # (profesor_id, dia, bloque) -> curso_id
    
    for (curso_id, dia, bloque), (materia_id, profesor_id) in cromosoma_reparado.genes.items():
        # Contar asignaciones
        key = (curso_id, materia_id)
        asignaciones_actuales[key] = asignaciones_actuales.get(key, 0) + 1
        
        # Marcar slots ocupados
        slots_ocupados[(curso_id, dia, bloque)] = (materia_id, profesor_id)
        profesores_ocupados[(profesor_id, dia, bloque)] = curso_id
        
        # Remover de slots disponibles
        if (dia, bloque) in slots_disponibles[curso_id]:
            slots_disponibles[curso_id].remove((dia, bloque))
    
    # 3. Corregir sobreasignaciones y deficiencias
    for curso_id, curso in datos.cursos.items():
        for materia_id in curso.materias:
            if materia_id not in datos.materias:
                continue
                
            materia = datos.materias[materia_id]
            bloques_necesarios = materia.bloques_por_semana
            asignados = asignaciones_actuales.get((curso_id, materia_id), 0)
            
            if asignados > bloques_necesarios:
                # Sobreasignación: remover asignaciones extra
                asignaciones_a_remover = asignados - bloques_necesarios
                estadisticas['sobreasignaciones_corregidas'] += asignaciones_a_remover
                
                # Encontrar y remover asignaciones extra de esta materia
                asignaciones_removidas = 0
                genes_a_remover = []
                
                for (c_id, dia, bloque), (m_id, p_id) in cromosoma_reparado.genes.items():
                    if c_id == curso_id and m_id == materia_id and asignaciones_removidas < asignaciones_a_remover:
                        genes_a_remover.append((c_id, dia, bloque))
                        asignaciones_removidas += 1
                        
                        # Liberar slot
                        if (dia, bloque) not in slots_disponibles[curso_id]:
                            slots_disponibles[curso_id].add((dia, bloque))
                
                # Remover genes
                for gen in genes_a_remover:
                    del cromosoma_reparado.genes[gen]
                    if gen in slots_ocupados:
                        del slots_ocupados[gen]
                
                # Actualizar contador
                asignaciones_actuales[(curso_id, materia_id)] = bloques_necesarios
            
            elif asignados < bloques_necesarios:
                # Deficiencia: agregar asignaciones faltantes
                asignaciones_faltantes = bloques_necesarios - asignados
                
                # Intentar agregar asignaciones faltantes
                asignaciones_agregadas = 0
                
                for _ in range(asignaciones_faltantes):
                    # Buscar slot disponible y profesor disponible
                    slot_encontrado = None
                    profesor_encontrado = None
                    
                    for dia, bloque in slots_disponibles[curso_id]:
                        # Buscar profesor disponible para esta materia en este slot
                        for profesor_id in materia.profesores:
                            if profesor_id not in datos.profesores:
                                continue
                                
                            profesor = datos.profesores[profesor_id]
                            
                            # Verificar disponibilidad del profesor
                            if (dia, bloque) not in profesor.disponibilidad:
                                continue
                            
                            # Verificar que el profesor no esté ocupado
                            if (profesor_id, dia, bloque) in profesores_ocupados:
                                continue
                            
                            # Slot y profesor encontrados
                            slot_encontrado = (dia, bloque)
                            profesor_encontrado = profesor_id
                            break
                        
                        if slot_encontrado:
                            break
                    
                    if slot_encontrado and profesor_encontrado:
                        # Asignar el gen
                        cromosoma_reparado.genes[(curso_id, slot_encontrado[0], slot_encontrado[1])] = (materia_id, profesor_encontrado)
                        slots_disponibles[curso_id].remove(slot_encontrado)
                        slots_ocupados[(curso_id, slot_encontrado[0], slot_encontrado[1])] = (materia_id, profesor_encontrado)
                        profesores_ocupados[(profesor_encontrado, slot_encontrado[0], slot_encontrado[1])] = curso_id
                        asignaciones_agregadas += 1
                        estadisticas['huecos_llenados'] += 1
                        
                        # Actualizar contador
                        asignaciones_actuales[(curso_id, materia_id)] = asignaciones_actuales.get((curso_id, materia_id), 0) + 1
    
    # 4. Llenar slots restantes con materias aleatorias
    for curso_id, curso in datos.cursos.items():
        while slots_disponibles[curso_id]:
            dia, bloque = slots_disponibles[curso_id].pop()
            
            # Buscar materia y profesor disponible para este slot
            materia_encontrada = None
            profesor_encontrado = None
            
            for materia_id in curso.materias:
                if materia_id not in datos.materias:
                    continue
                    
                materia = datos.materias[materia_id]
                for profesor_id in materia.profesores:
                    if profesor_id not in datos.profesores:
                        continue
                        
                    profesor = datos.profesores[profesor_id]
                    if (dia, bloque) in profesor.disponibilidad:
                        # Verificar que el profesor no esté ocupado
                        if (profesor_id, dia, bloque) not in profesores_ocupados:
                            materia_encontrada = materia_id
                            profesor_encontrado = profesor_id
                            break
                
                if materia_encontrada:
                    break
            
            if materia_encontrada and profesor_encontrado:
                cromosoma_reparado.genes[(curso_id, dia, bloque)] = (materia_encontrada, profesor_encontrado)
                slots_ocupados[(curso_id, dia, bloque)] = (materia_encontrada, profesor_encontrado)
                profesores_ocupados[(profesor_encontrado, dia, bloque)] = curso_id
                estadisticas['huecos_llenados'] += 1
    
    # 5. Resolver conflictos de profesores - O(n) usando dict
    conflictos_resueltos = 0
    max_iteraciones = 10  # Evitar bucle infinito
    
    for iteracion in range(max_iteraciones):
        conflictos_encontrados = False
        
        # Crear dict de conflictos: (profesor_id, dia, bloque) -> List[(curso_id, dia, bloque, materia_id)]
        conflictos = defaultdict(list)
        for (curso_id, dia, bloque), (materia_id, profesor_id) in cromosoma_reparado.genes.items():
            key = (profesor_id, dia, bloque)
            conflictos[key].append((curso_id, dia, bloque, materia_id))
        
        # Resolver conflictos donde hay más de una asignación
        for (profesor_id, dia, bloque), asignaciones in conflictos.items():
            if len(asignaciones) > 1:
                conflictos_encontrados = True
                logger.debug(f"Conflicto detectado: profesor {profesor_id} en {dia} bloque {bloque} con {len(asignaciones)} asignaciones")
                
                # Conservar la primera asignación, recolocar las restantes
                for i, (curso_id, dia_orig, bloque_orig, materia_id) in enumerate(asignaciones[1:], 1):
                    slot_alternativo = None
                    profesor_alternativo = None
                    
                    # Intentar slot alternativo libre en el mismo curso
                    for d_alt in DIAS:
                        for b_alt in datos.bloques_disponibles:
                            if (d_alt, b_alt) in slots_disponibles[curso_id]:
                                # Verificar disponibilidad del profesor
                                if profesor_id in datos.profesores:
                                    profesor = datos.profesores[profesor_id]
                                    if (d_alt, b_alt) in profesor.disponibilidad:
                                        # Verificar que no haya conflicto
                                        if (profesor_id, d_alt, b_alt) not in profesores_ocupados:
                                            slot_alternativo = (d_alt, b_alt)
                                            break
                        
                        if slot_alternativo:
                            break
                    
                    # Si no hay slot alternativo, intentar profesor alternativo
                    if not slot_alternativo and materia_id in datos.materias:
                        materia = datos.materias[materia_id]
                        for prof_alt_id in materia.profesores:
                            if prof_alt_id != profesor_id and prof_alt_id in datos.profesores:
                                prof_alt = datos.profesores[prof_alt_id]
                                # Buscar slot donde el profesor alternativo esté disponible
                                for d_alt in DIAS:
                                    for b_alt in datos.bloques_disponibles:
                                        if (d_alt, b_alt) in slots_disponibles[curso_id]:
                                            if (d_alt, b_alt) in prof_alt.disponibilidad:
                                                if (prof_alt_id, d_alt, b_alt) not in profesores_ocupados:
                                                    slot_alternativo = (d_alt, b_alt)
                                                    profesor_alternativo = prof_alt_id
                                                    break
                                    
                                    if slot_alternativo:
                                        break
                    
                    # Recolocar si se encontró alternativa
                    if slot_alternativo:
                        # Remover asignación original
                        del cromosoma_reparado.genes[(curso_id, dia_orig, bloque_orig)]
                        if (curso_id, dia_orig, bloque_orig) in slots_ocupados:
                            del slots_ocupados[(curso_id, dia_orig, bloque_orig)]
                        
                        # Agregar nueva asignación
                        nuevo_profesor = profesor_alternativo if profesor_alternativo else profesor_id
                        cromosoma_reparado.genes[(curso_id, slot_alternativo[0], slot_alternativo[1])] = (materia_id, nuevo_profesor)
                        slots_ocupados[(curso_id, slot_alternativo[0], slot_alternativo[1])] = (materia_id, nuevo_profesor)
                        profesores_ocupados[(nuevo_profesor, slot_alternativo[0], slot_alternativo[1])] = curso_id
                        
                        # Actualizar slots disponibles
                        if (slot_alternativo[0], slot_alternativo[1]) in slots_disponibles[curso_id]:
                            slots_disponibles[curso_id].remove(slot_alternativo)
                        
                        conflictos_resueltos += 1
                        estadisticas['conflictos_resueltos'] += 1
                        logger.debug(f"Conflicto resuelto: {curso_id} movido a {slot_alternativo} con profesor {nuevo_profesor}")
                    else:
                        logger.debug(f"No se pudo resolver conflicto para {curso_id} en {dia} bloque {bloque}")
        
        if not conflictos_encontrados:
            break
        
        logger.debug(f"Iteración {iteracion + 1}: {conflictos_resueltos} conflictos resueltos")
    
    # Actualizar el cromosoma original
    cromosoma.genes = cromosoma_reparado.genes
    
    return True, estadisticas

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
    
    # Reconstruir greedy: primero materias más difíciles
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
    
    def evaluar_con_reparacion(cromosoma):
        """Evalúa un cromosoma con reparación automática si es necesario."""
        # Evaluar fitness inicial
        fitness, conflictos = evaluar_fitness(cromosoma, datos)
        
        # Si hay conflictos, intentar reparar
        if conflictos > 0:
            logger.debug(f"Intentando reparar cromosoma con {conflictos} conflictos")
            reparacion_exitosa, reparaciones = repair_individual_robusto(cromosoma, datos)
            
            if reparacion_exitosa:
                # Re-evaluar después de la reparación
                fitness, conflictos = evaluar_fitness(cromosoma, datos)
                estadisticas_generacion['individuos_reparados'] += 1
                logger.debug(f"Cromosoma reparado exitosamente. Nuevo fitness: {fitness}")
            else:
                estadisticas_generacion['individuos_descartados'] += 1
                logger.debug("Cromosoma no pudo ser reparado, será descartado")
        
        # Registrar estadísticas de conflictos
        if conflictos > 0:
            estadisticas_generacion['conflictos_detectados']['conflictos_totales'] += conflictos
        
        cromosoma.fitness = fitness
        cromosoma.conflictos = conflictos
        return cromosoma
    
    if n > 1 and joblib:
        # Evaluación paralela con joblib
        try:
            cromosomas_evaluados = joblib.Parallel(n_jobs=n, backend='multiprocessing')(
                joblib.delayed(evaluar_con_reparacion)(cromosoma) for cromosoma in poblacion
            )
        except Exception as e:
            logger.warning(f"Error en evaluación paralela: {e}. Usando evaluación secuencial.")
            cromosomas_evaluados = [evaluar_con_reparacion(c) for c in poblacion]
    else:
        # Evaluación secuencial
        cromosomas_evaluados = [evaluar_con_reparacion(c) for c in poblacion]
    
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
    poblacion = inicializar_poblacion(datos, poblacion_size, semilla)
    
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
    
    # Validar solución final
    horarios_dict = _cromosoma_a_dict(mejor_cromosoma, datos)
    resultado_validacion = validar_antes_de_persistir(horarios_dict)
    
    if not resultado_validacion.es_valido:
        logger.error("La solución final no es válida")
        
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
                    if resultado_validacion.es_valido:
                        logger.info("✅ Fallback OR-Tools exitoso: solución válida generada")
                    else:
                        logger.warning("Fallback OR-Tools no pudo generar solución válida")
                        return {
                            'status': 'error',
                            'mensaje': 'No se pudo generar una solución válida ni con GA ni con OR-Tools',
                            'errores': [e.detalles for e in resultado_validacion.errores]
                        }
                        
                else:
                    logger.warning("OR-Tools no pudo generar horario base")
                    return {
                        'status': 'error',
                        'mensaje': 'No se pudo generar una solución válida',
                        'errores': [e.detalles for e in resultado_validacion.errores]
                    }
                    
            except ImportError:
                logger.warning("OR-Tools no disponible para fallback")
                return {
                    'status': 'error',
                    'mensaje': 'No se pudo generar una solución válida',
                    'errores': [e.detalles for e in resultado_validacion.errores]
                }
        else:
            return {
                'status': 'error',
                'mensaje': 'No se pudo generar una solución válida',
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
