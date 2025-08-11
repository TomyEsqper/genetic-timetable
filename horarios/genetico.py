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
pandas = try_import('pandas')
polars = try_import('polars')
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
DIAS = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes']
DIA_INDICE = {dia: idx for idx, dia in enumerate(DIAS)}

@dataclass
class ProfesorData:
    id: int
    disponibilidad: Set[Tuple[str, int]]  # (día, bloque)
    materias: Set[int]  # materia_ids

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
    if pandas or polars:
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
    if pandas or polars:
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
    
    # Asignar aulas fijas a cursos
    aulas_comunes = list(Aula.objects.filter(tipo='comun').values('id'))
    aulas_asignadas = {}
    
    # Cargar cursos
    for curso in Curso.objects.all():
        # Asignar aula fija al curso (si no tiene, asignar una disponible)
        if curso.id not in aulas_asignadas and aulas_comunes:
            aula_id = aulas_comunes[curso.id % len(aulas_comunes)]['id']
            aulas_asignadas[curso.id] = aula_id
        
        datos.cursos[curso.id] = CursoData(
            id=curso.id,
            nombre=curso.nombre,
            grado_id=curso.grado.id,
            aula_id=aulas_asignadas.get(curso.id, None),
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
    Inicializa la población con una estrategia guiada que prioriza las materias más difíciles de asignar.
    
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
    
    for _ in range(tamano_poblacion):
        cromosoma = Cromosoma()
        
        # Ordenar cursos aleatoriamente
        cursos_ids = list(datos.cursos.keys())
        random.shuffle(cursos_ids)
        
        for curso_id in cursos_ids:
            curso = datos.cursos[curso_id]
            
            # Ordenar materias por dificultad (más difíciles primero)
            materias_curso = [(m_id, datos.materia_dificultad.get(m_id, 0)) 
                             for m_id in curso.materias]
            materias_curso.sort(key=lambda x: x[1], reverse=True)
            
            for materia_id, _ in materias_curso:
                materia = datos.materias[materia_id]
                bloques_necesarios = materia.bloques_por_semana
                
                if bloques_necesarios <= 0 or not materia.profesores:
                    continue
                
                # Seleccionar profesor aleatoriamente
                profesor_id = random.choice(materia.profesores)
                profesor = datos.profesores[profesor_id]
                
                # Convertir disponibilidad a lista y mezclar
                disponibilidad = list(profesor.disponibilidad)
                random.shuffle(disponibilidad)
                
                asignados = 0
                for dia, bloque in disponibilidad:
                    # Verificar si el slot ya está ocupado para este curso
                    if (curso_id, dia, bloque) in cromosoma.genes:
                        continue
                    
                    # Verificar si el profesor ya está asignado en este slot
                    profesor_ocupado = False
                    for (c_id, d, b), (_, p_id) in cromosoma.genes.items():
                        if p_id == profesor_id and d == dia and b == bloque:
                            profesor_ocupado = True
                            break
                    
                    if profesor_ocupado:
                        continue
                    
                    # Asignar el gen
                    cromosoma.genes[(curso_id, dia, bloque)] = (materia_id, profesor_id)
                    asignados += 1
                    
                    if asignados == bloques_necesarios:
                        break
        
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
                               disponibilidad_array, bloques_por_semana_array):
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
        
        # Verificar disponibilidad del profesor
        if disponibilidad_array[profesor_id, dia, bloque] == 0:
            conflictos += 1
        else:
            puntaje += 0.5  # Bonificación por respetar disponibilidad
        
        # Contar bloques por materia y curso
        bloques_materia_curso[curso_id, materia_id] += 1
    
    # Verificar bloques_por_semana
    for curso_id in range(bloques_materia_curso.shape[0]):
        for materia_id in range(bloques_materia_curso.shape[1]):
            count = bloques_materia_curso[curso_id, materia_id]
            if count > 0:  # Solo verificar asignaciones existentes
                bloques_necesarios = bloques_por_semana_array[curso_id, materia_id]
                
                if count != bloques_necesarios and bloques_necesarios > 0:
                    # Penalizar proporcionalmente a la diferencia
                    diff = abs(count - bloques_necesarios)
                    conflictos += diff
                elif bloques_necesarios > 0:
                    puntaje += 2.0  # Bonificación por cumplir exactamente bloques_por_semana
    
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
            bloques_disponibles, bloques_por_semana, 
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
        else:
            slots_curso.add((curso_id, dia, bloque))
            puntaje += 1.0  # Bonificación por asignación válida de curso
        
        # Verificar solape de profesor
        if (profesor_id, dia, bloque) in slots_profesor:
            conflictos += 1
        else:
            slots_profesor.add((profesor_id, dia, bloque))
            puntaje += 1.0  # Bonificación por asignación válida de profesor
        
        # Verificar disponibilidad del profesor
        if (dia, bloque) not in datos.profesores[profesor_id].disponibilidad:
            conflictos += 1
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
    
    # Verificar bloques_por_semana
    for (curso_id, materia_id), count in bloques_materia_curso.items():
        if curso_id in datos.cursos and materia_id in datos.materias:
            bloques_necesarios = datos.materias[materia_id].bloques_por_semana
            if count != bloques_necesarios:
                # Penalizar proporcionalmente a la diferencia
                diff = abs(count - bloques_necesarios)
                conflictos += diff
            else:
                puntaje += 2.0  # Bonificación por cumplir exactamente bloques_por_semana
    
    # Penalizar fuertemente los conflictos
    fitness = puntaje - (conflictos * 10.0)
    
    return fitness, conflictos

# Importar validadores y reparador
from .validadores import validar_antes_de_persistir
from .reparador import reparar_cromosoma

def evaluar_poblacion_paralelo(poblacion, datos, workers):
    """
    Evalúa la población en paralelo si hay workers>1 y joblib disponible; en caso contrario, secuencial.
    Incluye validación y reparación de individuos inviables.
    """
    try:
        n = int(workers or 1)
    except Exception:
        n = 1
    
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
            reparacion_exitosa, reparaciones = reparar_cromosoma(cromosoma, datos)
            
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
    
    # Reparar hijos si es necesario
    reparar_cromosoma(hijo1, datos)
    reparar_cromosoma(hijo2, datos)
    
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
    
    # Reparar cromosoma mutado si es necesario
    reparar_cromosoma(cromosoma_mutado, datos)
    
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
    
    # Validar prerrequisitos
    errores_prerrequisitos = _validar_prerrequisitos(datos)
    if errores_prerrequisitos:
        return {
            'status': 'error',
            'mensaje': 'Prerrequisitos no cumplidos',
            'errores': errores_prerrequisitos
        }
    
    # Inicializar población
    poblacion = inicializar_poblacion(datos, poblacion_size, semilla)
    
    # Variables para tracking
    mejor_fitness = float('-inf')
    generaciones_sin_mejora = 0
    estadisticas_globales = {
        'individuos_reparados_total': 0,
        'individuos_descartados_total': 0,
        'conflictos_resueltos_total': 0,
        'mejor_fitness_por_generacion': [],
        'promedio_fitness_por_generacion': []
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
        
        # Actualizar mejor fitness
        fitness_actual = poblacion[0].fitness
        if fitness_actual > mejor_fitness:
            mejor_fitness = fitness_actual
            generaciones_sin_mejora = 0
            logger.info(f"Generación {generacion}: Nuevo mejor fitness = {mejor_fitness:.2f}")
        else:
            generaciones_sin_mejora += 1
        
        # Registrar estadísticas
        fitness_promedio = sum(c.fitness for c in poblacion) / len(poblacion)
        estadisticas_globales['mejor_fitness_por_generacion'].append(mejor_fitness)
        estadisticas_globales['promedio_fitness_por_generacion'].append(fitness_promedio)
        
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
        
        # Ajustar tamaño de población
        nueva_poblacion = nueva_poblacion[:poblacion_size]
        poblacion = nueva_poblacion
        
        # Logging de progreso
        if generacion % 10 == 0:
            tiempo_generacion = time.time() - generacion_inicio
            logger.info(f"Generación {generacion}: Fitness={fitness_actual:.2f}, "
                       f"Promedio={fitness_promedio:.2f}, Tiempo={tiempo_generacion:.2f}s")
    
    # Obtener mejor solución
    mejor_cromosoma = poblacion[0]
    
    # Validar solución final
    horarios_dict = _cromosoma_a_dict(mejor_cromosoma, datos)
    resultado_validacion = validar_antes_de_persistir(horarios_dict)
    
    if not resultado_validacion.es_valido:
        logger.error("La solución final no es válida")
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
            
            # Crear nuevos horarios
            horarios_creados = []
            for horario_data in horarios_dict:
                horario = Horario.objects.create(
                    curso_id=horario_data['curso_id'],
                    materia_id=horario_data['materia_id'],
                    profesor_id=horario_data['profesor_id'],
                    aula_id=horario_data.get('aula_id'),
                    dia=horario_data['dia'],
                    bloque=horario_data['bloque']
                )
                horarios_creados.append(horario)
            
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
    return metricas

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
