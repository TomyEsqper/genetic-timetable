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
from typing import Dict, List, Set, Tuple, Optional, Any, Union, Callable
from multiprocessing import Pool, cpu_count
from functools import partial, lru_cache
import importlib
import warnings
from contextlib import contextmanager

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
        logger.info(f"Usando {df_lib.__name__} para procesamiento de datos")
        
        # Cargar disponibilidad de profesores
        disponibilidad_raw = list(DisponibilidadProfesor.objects.values('profesor_id', 'dia', 'bloque_inicio', 'bloque_fin'))
        if disponibilidad_raw:
            df_disp = df_lib.DataFrame(disponibilidad_raw)
            
            # Expandir rangos de bloques
            disponibilidad_expandida = []
            for _, row in df_disp.iterrows() if pandas else df_disp.iter_rows(named=True):
                profesor_id = row['profesor_id']
                dia = row['dia']
                for bloque in range(row['bloque_inicio'], row['bloque_fin'] + 1):
                    disponibilidad_expandida.append({'profesor_id': profesor_id, 'dia': dia, 'bloque': bloque})
            
            df_disp_expandida = df_lib.DataFrame(disponibilidad_expandida)
            
            # Agrupar por profesor
            profesores_disp = {}
            for profesor_id in df_disp_expandida['profesor_id'].unique():
                filtro = df_disp_expandida['profesor_id'] == profesor_id
                dias_bloques = list(zip(
                    df_disp_expandida.filter(filtro)['dia'],
                    df_disp_expandida.filter(filtro)['bloque']
                ))
                profesores_disp[profesor_id] = set(dias_bloques)
        else:
            profesores_disp = {}
        
        # Cargar relaciones materia-profesor
        mp_raw = list(MateriaProfesor.objects.values('profesor_id', 'materia_id'))
        if mp_raw:
            df_mp = df_lib.DataFrame(mp_raw)
            
            # Crear diccionario de materias por profesor
            materias_por_profesor = {}
            for profesor_id in df_mp['profesor_id'].unique():
                filtro = df_mp['profesor_id'] == profesor_id
                materias_por_profesor[profesor_id] = set(df_mp.filter(filtro)['materia_id'])
            
            # Crear diccionario de profesores por materia
            profesores_por_materia = {}
            for materia_id in df_mp['materia_id'].unique():
                filtro = df_mp['materia_id'] == materia_id
                profesores_por_materia[materia_id] = list(df_mp.filter(filtro)['profesor_id'])
            
            # Crear relaciones materia-profesor
            materia_profesor_dict = {}
            for _, row in df_mp.iterrows() if pandas else df_mp.iter_rows(named=True):
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
            if mp.profesor.id not in profesores_por_materia:
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
        
        # Cargar relaciones materia-grado
        mg_raw = list(MateriaGrado.objects.values('grado_id', 'materia_id'))
        if mg_raw:
            df_mg = df_lib.DataFrame(mg_raw)
            materia_grado_dict = {}
            for _, row in df_mg.iterrows() if pandas else df_mg.iter_rows(named=True):
                materia_grado_dict[(row['grado_id'], row['materia_id'])] = True
            
            # Crear diccionario de materias por grado
            materias_por_grado = {}
            for grado_id in df_mg['grado_id'].unique():
                filtro = df_mg['grado_id'] == grado_id
                materias_por_grado[grado_id] = list(df_mg.filter(filtro)['materia_id'])
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
@njit
def _calcular_conflictos_numpy(cursos, dias, bloques, materias, profesores, bloques_disponibles, 
                               bloques_por_semana, disponibilidad_profesor, materia_profesor):
    """Versión optimizada con Numba para calcular conflictos."""
    n_genes = len(cursos)
    puntaje = 0.0
    conflictos = 0
    
    # Arrays para verificar solapes
    slots_curso = np.zeros((np.max(cursos) + 1, len(DIAS), np.max(bloques) + 1), dtype=np.int8)
    slots_profesor = np.zeros((np.max(profesores) + 1, len(DIAS), np.max(bloques) + 1), dtype=np.int8)
    
    # Contador de bloques por materia y curso
    bloques_materia_curso = np.zeros((np.max(cursos) + 1, np.max(materias) + 1), dtype=np.int32)
    
    # Evaluar cada gen
    for i in range(n_genes):
        curso_id = cursos[i]
        dia = dias[i]
        bloque = bloques[i]
        materia_id = materias[i]
        profesor_id = profesores[i]
        
        # Verificar si el bloque es válido
        bloque_valido = False
        for b in bloques_disponibles:
            if bloque == b:
                bloque_valido = True
                break
        
        if not bloque_valido:
            conflictos += 1
            continue
        
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
        profesor_disponible = False
        for j in range(len(disponibilidad_profesor)):
            if (disponibilidad_profesor[j, 0] == profesor_id and 
                disponibilidad_profesor[j, 1] == dia and 
                disponibilidad_profesor[j, 2] == bloque):
                profesor_disponible = True
                break
        
        if not profesor_disponible:
            conflictos += 1
        else:
            puntaje += 0.5  # Bonificación por respetar disponibilidad
        
        # Verificar que el profesor puede impartir la materia
        profesor_materia_valido = False
        for j in range(len(materia_profesor)):
            if (materia_profesor[j, 0] == materia_id and 
                materia_profesor[j, 1] == profesor_id):
                profesor_materia_valido = True
                break
        
        if not profesor_materia_valido:
            conflictos += 1
        else:
            puntaje += 0.5  # Bonificación por asignación válida materia-profesor
        
        # Contar bloques por materia y curso
        bloques_materia_curso[curso_id, materia_id] += 1
    
    # Verificar bloques_por_semana
    for curso_id in range(bloques_materia_curso.shape[0]):
        for materia_id in range(bloques_materia_curso.shape[1]):
            count = bloques_materia_curso[curso_id, materia_id]
            if count > 0:  # Solo verificar asignaciones existentes
                bloques_necesarios = 0
                for i in range(len(bloques_por_semana)):
                    if bloques_por_semana[i, 0] == materia_id:
                        bloques_necesarios = bloques_por_semana[i, 1]
                        break
                
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
        
        # Si la conversión falló, usar método tradicional
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
        # Si hay algún error, usar el método tradicional
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

def evaluar_poblacion_paralelo(poblacion: List[Cromosoma], datos: DatosHorario, workers: int) -> None:
    """
    Evalúa toda la población en paralelo utilizando multiprocessing o joblib si está disponible.
    
    Args:
        poblacion: Lista de cromosomas a evaluar
        datos: Datos preprocesados del horario
        workers: Número de procesos paralelos
    """
    if workers <= 1:
        # Evaluación secuencial
        for cromosoma in poblacion:
            cromosoma.fitness, cromosoma.conflictos = evaluar_fitness(cromosoma, datos)
    else:
        # Intentar usar joblib si está disponible
        if joblib:
            try:
                # Usar joblib con paralelización
                resultados = joblib.Parallel(n_jobs=workers)(
                    joblib.delayed(evaluar_fitness)(cromosoma, datos) for cromosoma in poblacion
                )
                
                for i, (fitness, conflictos) in enumerate(resultados):
                    poblacion[i].fitness = fitness
                    poblacion[i].conflictos = conflictos
                return
            except Exception as e:
                logger.warning(f"Error al usar joblib: {e}. Usando multiprocessing.")
        
        # Fallback a multiprocessing
        try:
            with Pool(processes=workers) as pool:
                resultados = pool.map(partial(evaluar_fitness, datos=datos), poblacion)
                
                for i, (fitness, conflictos) in enumerate(resultados):
                    poblacion[i].fitness = fitness
                    poblacion[i].conflictos = conflictos
        except Exception as e:
            # Si falla la paralelización, ejecutar en serie como último recurso
            logger.warning(f"Error en paralelización: {e}. Ejecutando en serie.")
            for cromosoma in poblacion:
                cromosoma.fitness, cromosoma.conflictos = evaluar_fitness(cromosoma, datos)

def seleccion_torneo(poblacion: List[Cromosoma], tamano_torneo: int = 3) -> Cromosoma:
    """
    Selecciona un cromosoma mediante torneo.
    
    Args:
        poblacion: Lista de cromosomas
        tamano_torneo: Tamaño del torneo
    
    Returns:
        Cromosoma seleccionado
    """
    participantes = random.sample(poblacion, min(tamano_torneo, len(poblacion)))
    return max(participantes, key=lambda c: c.fitness)

def cruce_por_bloques(padre1: Cromosoma, padre2: Cromosoma, prob_cruce: float) -> Tuple[Cromosoma, Cromosoma]:
    """
    Realiza el cruce entre dos cromosomas por bloques (día-bloque).
    
    Utiliza NumPy para optimizar el proceso cuando está disponible.
    
    Args:
        padre1: Primer cromosoma padre
        padre2: Segundo cromosoma padre
        prob_cruce: Probabilidad de cruce
    
    Returns:
        Tupla con dos cromosomas hijos
    """
    if random.random() > prob_cruce:
        return padre1.copy(), padre2.copy()
    
    hijo1 = Cromosoma()
    hijo2 = Cromosoma()
    
    # Intentar usar NumPy para optimizar si está disponible
    try:
        # Obtener todos los días-bloques únicos
        dias_bloques = set()
        for (curso_id, dia, bloque), _ in padre1.genes.items():
            dias_bloques.add((dia, bloque))
        for (curso_id, dia, bloque), _ in padre2.genes.items():
            dias_bloques.add((dia, bloque))
        
        # Convertir a arrays NumPy para procesamiento más rápido
        dias_bloques = list(dias_bloques)
        dias_bloques_array = np.array(dias_bloques)
        
        # Generar índices aleatorios para la división
        indices = np.arange(len(dias_bloques_array))
        np.random.shuffle(indices)
        punto_corte = np.random.randint(0, len(dias_bloques_array) + 1)
        
        # Dividir usando NumPy
        indices_hijo1 = indices[:punto_corte]
        indices_hijo2 = indices[punto_corte:]
        
        dias_bloques_hijo1 = set(tuple(x) for x in dias_bloques_array[indices_hijo1]) if len(indices_hijo1) > 0 else set()
        dias_bloques_hijo2 = set(tuple(x) for x in dias_bloques_array[indices_hijo2]) if len(indices_hijo2) > 0 else set()
    except Exception as e:
        # Fallback a la versión tradicional si hay algún error
        dias_bloques = list(dias_bloques)
        random.shuffle(dias_bloques)
        punto_corte = random.randint(0, len(dias_bloques))
        
        dias_bloques_hijo1 = set(dias_bloques[:punto_corte])
        dias_bloques_hijo2 = set(dias_bloques[punto_corte:])
    
    # Asignar genes a los hijos
    for (curso_id, dia, bloque), valor in padre1.genes.items():
        if (dia, bloque) in dias_bloques_hijo1:
            hijo1.genes[(curso_id, dia, bloque)] = valor
        else:
            hijo2.genes[(curso_id, dia, bloque)] = valor
    
    for (curso_id, dia, bloque), valor in padre2.genes.items():
        # Evitar duplicados
        if (curso_id, dia, bloque) not in hijo1.genes and (dia, bloque) in dias_bloques_hijo1:
            hijo1.genes[(curso_id, dia, bloque)] = valor
        elif (curso_id, dia, bloque) not in hijo2.genes and (dia, bloque) in dias_bloques_hijo2:
            hijo2.genes[(curso_id, dia, bloque)] = valor
    
    return hijo1, hijo2

def mutar_adaptativo(cromosoma: Cromosoma, datos: DatosHorario, prob_mutacion: float) -> Cromosoma:
    """
    Realiza mutación adaptativa centrada en genes conflictivos.
    Utiliza NumPy para optimizar el proceso cuando está disponible.
    
    Args:
        cromosoma: Cromosoma a mutar
        datos: Datos preprocesados del horario
        prob_mutacion: Probabilidad base de mutación
    
    Returns:
        Cromosoma mutado
    """
    if not cromosoma.genes or random.random() > prob_mutacion:
        return cromosoma
    
    resultado = cromosoma.copy()
    
    # Identificar genes conflictivos
    genes_conflictivos = []
    slots_curso = {}  # (curso_id, dia, bloque) -> count
    slots_profesor = {}  # (profesor_id, dia, bloque) -> count
    
    for (curso_id, dia, bloque), (materia_id, profesor_id) in resultado.genes.items():
        # Contar ocurrencias para detectar solapes
        curso_key = (curso_id, dia, bloque)
        profesor_key = (profesor_id, dia, bloque)
        
        slots_curso[curso_key] = slots_curso.get(curso_key, 0) + 1
        slots_profesor[profesor_key] = slots_profesor.get(profesor_key, 0) + 1
        
        # Verificar disponibilidad del profesor
        if (dia, bloque) not in datos.profesores[profesor_id].disponibilidad:
            genes_conflictivos.append((curso_id, dia, bloque))
        
        # Verificar que el profesor puede impartir la materia
        if (materia_id, profesor_id) not in datos.materia_profesor:
            genes_conflictivos.append((curso_id, dia, bloque))
    
    # Añadir genes con solapes
    for key, count in slots_curso.items():
        if count > 1:
            genes_conflictivos.append(key)
    
    for key, count in slots_profesor.items():
        profesor_id, dia, bloque = key
        for (curso_id, d, b), (materia_id, p_id) in resultado.genes.items():
            if p_id == profesor_id and d == dia and b == bloque:
                if (curso_id, dia, bloque) not in genes_conflictivos:
                    genes_conflictivos.append((curso_id, dia, bloque))
    
    # Si no hay genes conflictivos, seleccionar aleatoriamente
    if not genes_conflictivos:
        genes_conflictivos = list(resultado.genes.keys())
    
    # Intentar usar NumPy para optimizar la selección de genes a mutar
    try:
        # Convertir a arrays NumPy para procesamiento más rápido
        genes_array = np.array(genes_conflictivos)
        
        # Calcular número de mutaciones
        num_mutaciones = max(1, int(len(genes_conflictivos) * prob_mutacion))
        
        # Seleccionar genes a mutar usando NumPy
        indices = np.random.choice(len(genes_array), size=min(num_mutaciones, len(genes_array)), replace=False)
        genes_a_mutar = genes_array[indices].tolist()
    except Exception:
        # Fallback a la versión tradicional si hay algún error
        num_mutaciones = max(1, int(len(genes_conflictivos) * prob_mutacion))
        genes_a_mutar = random.sample(genes_conflictivos, min(num_mutaciones, len(genes_conflictivos)))
    
    for gen in genes_a_mutar:
        curso_id, dia, bloque = gen
        materia_id, profesor_id = resultado.genes[gen]
        
        # Opciones de mutación:
        tipo_mutacion = random.choice(['dia_bloque', 'profesor', 'ambos'])
        
        if tipo_mutacion in ['dia_bloque', 'ambos']:
            # Cambiar día y bloque
            nuevo_dia = random.choice(DIAS)
            nuevo_bloque = random.choice(datos.bloques_disponibles)
            
            # Verificar que el nuevo slot no esté ocupado
            if (curso_id, nuevo_dia, nuevo_bloque) not in resultado.genes:
                # Eliminar el gen original
                del resultado.genes[gen]
                
                # Si solo cambiamos día/bloque, mantenemos materia y profesor
                if tipo_mutacion == 'dia_bloque':
                    resultado.genes[(curso_id, nuevo_dia, nuevo_bloque)] = (materia_id, profesor_id)
                else:
                    # Cambiar también el profesor
                    if materia_id in datos.materias and datos.materias[materia_id].profesores:
                        # Usar NumPy para selección aleatoria si está disponible
                        try:
                            profesores = np.array(datos.materias[materia_id].profesores)
                            nuevo_profesor_id = np.random.choice(profesores)
                        except Exception:
                            nuevo_profesor_id = random.choice(datos.materias[materia_id].profesores)
                        resultado.genes[(curso_id, nuevo_dia, nuevo_bloque)] = (materia_id, nuevo_profesor_id)
                    else:
                        # Si no hay profesores disponibles, mantener el original
                        resultado.genes[(curso_id, nuevo_dia, nuevo_bloque)] = (materia_id, profesor_id)
        
        elif tipo_mutacion == 'profesor':
            # Solo cambiar el profesor
            if materia_id in datos.materias and datos.materias[materia_id].profesores:
                # Usar NumPy para selección aleatoria si está disponible
                try:
                    profesores = np.array(datos.materias[materia_id].profesores)
                    nuevo_profesor_id = np.random.choice(profesores)
                except Exception:
                    nuevo_profesor_id = random.choice(datos.materias[materia_id].profesores)
                resultado.genes[gen] = (materia_id, nuevo_profesor_id)
    
    return resultado

def generar_horarios_genetico(
    poblacion_size=80,
    generaciones=500,
    prob_cruce=0.85,
    prob_mutacion=0.25,
    elite=4,
    paciencia=25,
    semilla=42,
    workers=None
):
    """
    Genera horarios escolares utilizando un algoritmo genético optimizado.
    
    Args:
        poblacion_size: Tamaño de la población
        generaciones: Número máximo de generaciones
        prob_cruce: Probabilidad de cruce
        prob_mutacion: Probabilidad base de mutación
        elite: Número de mejores individuos que pasan directamente a la siguiente generación
        paciencia: Número de generaciones sin mejora antes de detener el algoritmo
        semilla: Semilla para reproducibilidad
        workers: Número de procesos paralelos (None = automático)
    
    Returns:
        None (guarda los resultados en la base de datos)
    """
    tiempo_inicio = time.time()
    
    # Configurar número de workers
    if workers is None:
        workers = max(1, cpu_count() - 1)
    
    # Cargar datos
    datos = cargar_datos()
    
    # Registrar librerías disponibles para optimización
    libs_disponibles = []
    if 'np' in globals():
        libs_disponibles.append(f"NumPy {np.__version__}")
    if numba:
        libs_disponibles.append(f"Numba {numba.__version__}")
    if joblib:
        libs_disponibles.append(f"Joblib {joblib.__version__}")
    if pandas:
        libs_disponibles.append(f"Pandas {pandas.__version__}")
    if polars:
        libs_disponibles.append(f"Polars {polars.__version__}")
    
    # Intentar importar librerías para visualización
    matplotlib = try_import('matplotlib.pyplot')
    seaborn = try_import('seaborn')
    if matplotlib and seaborn:
        libs_disponibles.append(f"Matplotlib {matplotlib.__version__}")
        libs_disponibles.append(f"Seaborn {seaborn.__version__}")
    
    if libs_disponibles:
        logger.info(f"Librerías optimizadas disponibles: {', '.join(libs_disponibles)}")
    
    # Preparar estructuras para seguimiento de progreso
    historial_fitness = []
    historial_conflictos = []
    historial_diversidad = []
    
    # Logging inicial
    logger.info(f"Iniciando generación de horarios con algoritmo genético")
    logger.info(f"Cursos: {len(datos.cursos)}, Materias: {len(datos.materias)}, Profesores: {len(datos.profesores)}")
    logger.info(f"Bloques disponibles: {len(datos.bloques_disponibles)}, Total posibles slots: {len(datos.cursos) * len(DIAS) * len(datos.bloques_disponibles)}")
    logger.info(f"Parámetros: población={poblacion_size}, generaciones={generaciones}, prob_cruce={prob_cruce}, prob_mutacion={prob_mutacion}, elite={elite}, workers={workers}")
    
    # Inicializar población
    poblacion = inicializar_poblacion(datos, poblacion_size, semilla)
    
    # Evaluar población inicial
    evaluar_poblacion_paralelo(poblacion, datos, workers)
    
    # Ordenar población por fitness
    poblacion.sort(key=lambda c: c.fitness, reverse=True)
    
    mejor_fitness = poblacion[0].fitness if poblacion else float('-inf')
    mejor_cromosoma = poblacion[0].copy() if poblacion else None
    generaciones_sin_mejora = 0
    prob_mutacion_actual = prob_mutacion
    
    # Calcular diversidad inicial
    diversidad = calcular_diversidad_poblacion(poblacion)
    
    # Registrar estado inicial
    historial_fitness.append(mejor_fitness)
    historial_conflictos.append(poblacion[0].conflictos if poblacion else 0)
    historial_diversidad.append(diversidad)
    
    # Evolución
    for generacion in range(1, generaciones + 1):
        tiempo_gen_inicio = time.time()
        
        # Elitismo: los mejores pasan directamente
        nueva_poblacion = [c.copy() for c in poblacion[:elite]]
        
        # Generar nueva población
        while len(nueva_poblacion) < poblacion_size:
            # Selección
            padre1 = seleccion_torneo(poblacion)
            padre2 = seleccion_torneo(poblacion)
            
            # Cruce
            hijo1, hijo2 = cruce_por_bloques(padre1, padre2, prob_cruce)
            
            # Mutación
            hijo1 = mutar_adaptativo(hijo1, datos, prob_mutacion_actual)
            hijo2 = mutar_adaptativo(hijo2, datos, prob_mutacion_actual)
            
            nueva_poblacion.append(hijo1)
            if len(nueva_poblacion) < poblacion_size:
                nueva_poblacion.append(hijo2)
        
        # Reemplazar población
        poblacion = nueva_poblacion
        
        # Evaluar nueva población
        evaluar_poblacion_paralelo(poblacion, datos, workers)
        
        # Ordenar por fitness
        poblacion.sort(key=lambda c: c.fitness, reverse=True)
        
        # Calcular diversidad
        diversidad = calcular_diversidad_poblacion(poblacion)
        
        # Registrar estado actual
        historial_fitness.append(poblacion[0].fitness)
        historial_conflictos.append(poblacion[0].conflictos)
        historial_diversidad.append(diversidad)
        
        # Verificar mejora
        if poblacion and poblacion[0].fitness > mejor_fitness:
            mejor_fitness = poblacion[0].fitness
            mejor_cromosoma = poblacion[0].copy()
            generaciones_sin_mejora = 0
            prob_mutacion_actual = prob_mutacion  # Resetear probabilidad de mutación
        else:
            generaciones_sin_mejora += 1
            # Aumentar probabilidad de mutación si no hay mejora
            if generaciones_sin_mejora % 10 == 0:
                prob_mutacion_actual = min(0.45, prob_mutacion_actual * 1.2)
        
        # Logging
        tiempo_gen = time.time() - tiempo_gen_inicio
        mejor_actual = poblacion[0] if poblacion else None
        logger.info(f"Gen {generacion}: Mejor fitness={mejor_actual.fitness:.2f}, Conflictos={mejor_actual.conflictos}, "
                   f"Tiempo={tiempo_gen:.2f}s, Sin mejora={generaciones_sin_mejora}, Prob. mutación={prob_mutacion_actual:.2f}, Diversidad={diversidad:.2f}")
        
        # Early stopping
        if generaciones_sin_mejora >= paciencia:
            logger.info(f"Early stopping después de {generaciones_sin_mejora} generaciones sin mejora")
            break
        
        # Detener si encontramos solución óptima (sin conflictos)
        if mejor_actual and mejor_actual.conflictos == 0:
            logger.info(f"Solución óptima encontrada en generación {generacion}: Sin conflictos")
            mejor_cromosoma = mejor_actual.copy()
            break
    
    # Convertir el mejor cromosoma a formato de horario
    horario_final = []
    
    if mejor_cromosoma:
        for (curso_id, dia, bloque), (materia_id, profesor_id) in mejor_cromosoma.genes.items():
            if curso_id in datos.cursos and materia_id in datos.materias and profesor_id in datos.profesores:
                curso = datos.cursos[curso_id]
                aula_id = curso.aula_id
                
                horario_final.append({
                    'curso_id': curso_id,
                    'materia_id': materia_id,
                    'profesor_id': profesor_id,
                    'aula_id': aula_id,
                    'dia': dia,
                    'bloque': bloque
                })
    
    # Guardar en base de datos
    Horario.objects.all().delete()
    for item in horario_final:
        try:
            Horario.objects.create(
                curso_id=item['curso_id'],
                materia_id=item['materia_id'],
                profesor_id=item['profesor_id'],
                aula_id=item['aula_id'],
                dia=item['dia'],
                bloque=item['bloque']
            )
        except Exception as e:
            logger.error(f"Error al guardar horario: {e}")
    
    # Generar visualizaciones si las librerías están disponibles
    try:
        if matplotlib and seaborn:
            generar_visualizaciones(
                historial_fitness, 
                historial_conflictos, 
                historial_diversidad
            )
    except Exception as e:
        logger.warning(f"Error al generar visualizaciones: {e}")
    
    # Logging final
    tiempo_total = time.time() - tiempo_inicio
    logger.info(f"✅ Horarios generados con éxito en {tiempo_total:.2f} segundos")
    logger.info(f"Generaciones ejecutadas: {min(generacion, generaciones)}")
    logger.info(f"Fitness final: {mejor_fitness:.2f}, Conflictos: {mejor_cromosoma.conflictos if mejor_cromosoma else 'N/A'}")
    
    return None


def calcular_diversidad_poblacion(poblacion: List[Cromosoma]) -> float:
    """Calcula la diversidad genética de la población.
    
    Args:
        poblacion: Lista de cromosomas
    
    Returns:
        Valor de diversidad entre 0 y 1
    """
    if not poblacion or len(poblacion) < 2:
        return 0.0
    
    # Muestrear hasta 10 cromosomas para eficiencia
    muestra = poblacion[:min(10, len(poblacion))]
    distancias = []
    
    for i in range(len(muestra)):
        for j in range(i+1, len(muestra)):
            # Calcular distancia entre cromosomas (proporción de genes diferentes)
            genes_i = set(muestra[i].genes.items())
            genes_j = set(muestra[j].genes.items())
            
            union = len(genes_i.union(genes_j))
            if union == 0:
                distancias.append(0.0)
            else:
                interseccion = len(genes_i.intersection(genes_j))
                distancias.append(1.0 - (interseccion / union))
    
    # Retornar diversidad promedio
    return sum(distancias) / len(distancias) if distancias else 0.0


def generar_visualizaciones(historial_fitness, historial_conflictos, historial_diversidad):
    """Genera visualizaciones del progreso del algoritmo genético.
    
    Args:
        historial_fitness: Lista de valores de fitness por generación
        historial_conflictos: Lista de conflictos por generación
        historial_diversidad: Lista de diversidad por generación
    """
    import os
    import matplotlib.pyplot as plt
    import seaborn as sns
    
    # Configurar estilo de visualización
    sns.set_style("whitegrid")
    plt.figure(figsize=(15, 10))
    
    # Gráfico 1: Evolución del fitness
    plt.subplot(3, 1, 1)
    plt.plot(historial_fitness, 'b-', linewidth=2)
    plt.title('Evolución del Fitness')
    plt.xlabel('Generación')
    plt.ylabel('Fitness')
    plt.grid(True)
    
    # Gráfico 2: Evolución de conflictos
    plt.subplot(3, 1, 2)
    plt.plot(historial_conflictos, 'r-', linewidth=2)
    plt.title('Evolución de Conflictos')
    plt.xlabel('Generación')
    plt.ylabel('Número de Conflictos')
    plt.grid(True)
    
    # Gráfico 3: Evolución de la diversidad
    plt.subplot(3, 1, 3)
    plt.plot(historial_diversidad, 'g-', linewidth=2)
    plt.title('Evolución de la Diversidad')
    plt.xlabel('Generación')
    plt.ylabel('Diversidad')
    plt.ylim(0, 1)
    plt.grid(True)
    
    plt.tight_layout()
    
    # Guardar gráfico
    directorio = 'diagnosticos'
    if not os.path.exists(directorio):
        os.makedirs(directorio)
        
    plt.savefig(f"{directorio}/evolucion_algoritmo_genetico.png")
    logger.info(f"Visualización guardada en {directorio}/evolucion_algoritmo_genetico.png")
    
    # Cerrar figura para liberar memoria
    plt.close()
