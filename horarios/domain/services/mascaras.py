"""
Módulo de máscaras booleanas precomputadas para optimización del algoritmo genético.

Este módulo precomputa máscaras booleanas que permiten validaciones O(1) en lugar de O(n)
 durante la evaluación de fitness y generación de cromosomas.
"""

import numpy as np
from typing import Dict, List, Tuple, Set, Any
from dataclasses import dataclass
from horarios.models import (
	Profesor, Materia, Curso, Aula, BloqueHorario, 
	MateriaGrado, MateriaProfesor, DisponibilidadProfesor, ConfiguracionColegio, Horario,
	Slot, ProfesorSlot, CursoMateriaRequerida
)
import logging

logger = logging.getLogger(__name__)

@dataclass
class MascarasOptimizadas:
    """Máscaras booleanas precomputadas para validaciones O(1)"""
    profesor_disponible: np.ndarray  # [profesor, dia, bloque] -> bool (compat)
    bloque_tipo_clase: np.ndarray    # [dia, bloque] -> bool (compat)
    profesor_materia: np.ndarray     # [profesor, materia] -> bool
    curso_materia: np.ndarray        # [curso, materia] -> bool
    curso_aula_fija: np.ndarray      # [curso, aula] -> bool
    profesor_to_idx: Dict[int, int]
    materia_to_idx: Dict[int, int]
    curso_to_idx: Dict[int, int]
    aula_to_idx: Dict[int, int]
    dias_clase: List[str]
    bloques_por_dia: int
    total_slots: int
    # Nuevos campos plano por slot
    slots: List[Tuple[str, int]]              # [(dia, bloque)]
    slot_to_idx: Dict[Tuple[str, int], int]   # (dia, bloque) -> idx
    mask_profesor_disponible_flat: np.ndarray # [P, S] -> bool


def _construir_indice_slots_desde_bd() -> Dict[str, Any]:
    """Construye el índice de slots (día x bloque_clase) 100% desde BD."""
    # Usar tabla Slot si existe, si no, derivar
    slots_qs = list(Slot.objects.all().values('dia', 'bloque').order_by('dia', 'bloque'))
    if slots_qs:
        dias = sorted(list({s['dia'] for s in slots_qs}))
        bloques = sorted(list({s['bloque'] for s in slots_qs}))
        slots = [(s['dia'], s['bloque']) for s in slots_qs]
        slot_to_idx = {(d, b): i for i, (d, b) in enumerate(slots)}
        return {'dias': dias, 'bloques': bloques, 'slots': slots, 'slot_to_idx': slot_to_idx}

    # Fallback: derivar desde disponibilidad/horarios/bloques
    dias_set = set(DisponibilidadProfesor.objects.values_list('dia', flat=True))
    if not dias_set:
        dias_set = set(Horario.objects.values_list('dia', flat=True)) if 'Horario' in globals() else set()
    dias = sorted(list(dias_set))

    bloques = sorted(set(BloqueHorario.objects.filter(tipo='clase').values_list('numero', flat=True)))
    if not dias or not bloques:
        raise ValueError("No hay días o bloques 'clase' definidos en BD")

    slots = []
    slot_to_idx = {}
    for d in dias:
        for b in bloques:
            slot_to_idx[(d, b)] = len(slots)
            slots.append((d, b))
    return {'dias': dias, 'bloques': bloques, 'slots': slots, 'slot_to_idx': slot_to_idx}


def precomputar_mascaras() -> MascarasOptimizadas:
    """
    Precomputa todas las máscaras booleanas necesarias para el GA, 100% data-driven.
    """
    # Índice de entidades
    profesores = list(Profesor.objects.values_list('id', flat=True).order_by('id'))
    materias = list(Materia.objects.values_list('id', flat=True).order_by('id'))
    cursos = list(Curso.objects.values_list('id', flat=True).order_by('id'))
    aulas = list(Aula.objects.values_list('id', flat=True).order_by('id'))

    profesor_to_idx = {pid: idx for idx, pid in enumerate(profesores)}
    materia_to_idx = {mid: idx for idx, mid in enumerate(materias)}
    curso_to_idx = {cid: idx for idx, cid in enumerate(cursos)}
    aula_to_idx = {aid: idx for idx, aid in enumerate(aulas)}

    # Índice de slots data-driven
    idx = _construir_indice_slots_desde_bd()
    dias_clase = idx['dias']
    bloques_clase = idx['bloques']
    slots = idx['slots']
    slot_to_idx = idx['slot_to_idx']

    # Máscaras compat (dia x bloque)
    bloque_tipo_clase = np.zeros((len(dias_clase), len(bloques_clase)), dtype=bool)
    dia_index = {d: i for i, d in enumerate(dias_clase)}
    bloque_index = {b: i for i, b in enumerate(bloques_clase)}
    for (d, b) in slots:
        bloque_tipo_clase[dia_index[d], bloque_index[b]] = True

    profesor_disponible = np.zeros((len(profesores), len(dias_clase), len(bloques_clase)), dtype=bool)
    mask_profesor_disponible_flat = np.zeros((len(profesores), len(slots)), dtype=bool)

    # Usar ProfesorSlot si está materializado; si no, derivar de DisponibilidadProfesor
    ps_rows = list(ProfesorSlot.objects.values_list('profesor_id', 'slot_id'))
    if ps_rows:
        # Mapa rápido de slot_id -> (dia, bloque)
        slot_map = { (s.dia, s.bloque): s.id for s in Slot.objects.all().only('id','dia','bloque') }
        id_to_pair = { v: k for k, v in slot_map.items() }
        for pid, slot_id in ps_rows:
            if pid not in profesor_to_idx or slot_id not in id_to_pair:
                continue
            pidx = profesor_to_idx[pid]
            d, b = id_to_pair[slot_id]
            didx = dia_index.get(d)
            bidx = bloque_index.get(b)
            sidx = slot_to_idx.get((d, b))
            if didx is None or bidx is None or sidx is None:
                continue
            profesor_disponible[pidx, didx, bidx] = True
            mask_profesor_disponible_flat[pidx, sidx] = True
    else:
        for disp in DisponibilidadProfesor.objects.all():
            pid = disp.profesor_id
            if pid not in profesor_to_idx:
                continue
            pidx = profesor_to_idx[pid]
            for b in range(int(disp.bloque_inicio), int(disp.bloque_fin) + 1):
                if b in bloque_index and disp.dia in dia_index:
                    didx = dia_index[disp.dia]
                    bidx = bloque_index[b]
                    profesor_disponible[pidx, didx, bidx] = True
                    sidx = slot_to_idx.get((disp.dia, b))
                    if sidx is not None:
                        mask_profesor_disponible_flat[pidx, sidx] = True

    # Profesor-materia
    profesor_materia = np.zeros((len(profesores), len(materias)), dtype=bool)
    for pid, mid in MateriaProfesor.objects.values_list('profesor_id', 'materia_id'):
        if pid in profesor_to_idx and mid in materia_to_idx:
            profesor_materia[profesor_to_idx[pid], materia_to_idx[mid]] = True

    # Curso-materia desde snapshot (preferido), fallback a MateriaGrado
    curso_materia = np.zeros((len(cursos), len(materias)), dtype=bool)
    cmr = list(CursoMateriaRequerida.objects.values_list('curso_id', 'materia_id'))
    if cmr:
        for cid, mid in cmr:
            if cid in curso_to_idx and mid in materia_to_idx:
                curso_materia[curso_to_idx[cid], materia_to_idx[mid]] = True
    else:
        grado_por_curso = {c.id: c.grado_id for c in Curso.objects.select_related('grado').all()}
        for grado_id, materia_id in MateriaGrado.objects.values_list('grado_id', 'materia_id'):
            for cid, gid in grado_por_curso.items():
                if gid == grado_id and cid in curso_to_idx and materia_id in materia_to_idx:
                    curso_materia[curso_to_idx[cid], materia_to_idx[materia_id]] = True

    # Curso-aula fija
    curso_aula_fija = np.zeros((len(cursos), len(aulas)), dtype=bool)
    for curso in Curso.objects.all():
        if curso.id in curso_to_idx and curso.aula_fija_id in aula_to_idx:
            curso_aula_fija[curso_to_idx[curso.id], aula_to_idx[curso.aula_fija_id]] = True

    # Auditoría simple: 2-3 profesores aleatorios y sus vectores
    try:
        muestra = auditar_mascaras_aleatoria(
            MascarasOptimizadas(
                profesor_disponible=None,
                bloque_tipo_clase=None,
                profesor_materia=None,
                curso_materia=None,
                curso_aula_fija=None,
                profesor_to_idx=profesor_to_idx,
                materia_to_idx=materia_to_idx,
                curso_to_idx=curso_to_idx,
                aula_to_idx=aula_to_idx,
                dias_clase=dias_clase,
                bloques_por_dia=len(bloques_clase),
                total_slots=len(slots),
                slots=slots,
                slot_to_idx=slot_to_idx,
                mask_profesor_disponible_flat=mask_profesor_disponible_flat,
            ), max_mostrar=3
        )
        logger.info(f"Auditoría máscaras (profesor -> #slots y vector): {muestra}")
    except Exception as _:
        pass

    return MascarasOptimizadas(
        profesor_disponible=profesor_disponible,
        bloque_tipo_clase=bloque_tipo_clase,
        profesor_materia=profesor_materia,
        curso_materia=curso_materia,
        curso_aula_fija=curso_aula_fija,
        profesor_to_idx=profesor_to_idx,
        materia_to_idx=materia_to_idx,
        curso_to_idx=curso_to_idx,
        aula_to_idx=aula_to_idx,
        dias_clase=dias_clase,
        bloques_por_dia=len(bloques_clase),
        total_slots=len(slots),
        slots=slots,
        slot_to_idx=slot_to_idx,
        mask_profesor_disponible_flat=mask_profesor_disponible_flat,
    )


def auditar_mascaras_aleatoria(mascaras: MascarasOptimizadas, rng: np.random.RandomState = None, max_mostrar: int = None) -> List[Dict[str, Any]]:
    """Devuelve una muestra de disponibilidad plana por profesor para logging/auditoría."""
    rng = rng or np.random.RandomState()
    P = len(mascaras.profesor_to_idx)
    k = max(1, int(P ** 0.5)) if max_mostrar is None else min(max_mostrar, P)
    profesor_ids = list(mascaras.profesor_to_idx.keys())
    muestra = rng.choice(profesor_ids, size=k, replace=False).tolist() if P > 0 else []
    
    resultado = []
    for pid in muestra:
        pidx = mascaras.profesor_to_idx[pid]
        vec = mascaras.mask_profesor_disponible_flat[pidx, :].astype(int).tolist()
        resultado.append({
            'profesor_id': pid,
            'slots_disponibles': int(np.sum(mascaras.mask_profesor_disponible_flat[pidx, :])),
            'vector_disponibilidad_flat': vec,
        })
    return resultado

def validar_slot_con_mascaras(
    mascaras: MascarasOptimizadas, 
    curso_id: int, 
    materia_id: int, 
    profesor_id: int, 
    dia: str, 
    bloque: int
) -> Tuple[bool, str]:
    """
    Valida un slot usando máscaras precomputadas (O(1)).
    Retorna (es_valido, mensaje_error).
    """
    try:
        # Verificar que los IDs existan en las máscaras
        if curso_id not in mascaras.curso_to_idx:
            return False, f"Curso {curso_id} no encontrado en máscaras"
        if materia_id not in mascaras.materia_to_idx:
            return False, f"Materia {materia_id} no encontrada en máscaras"
        if profesor_id not in mascaras.profesor_to_idx:
            return False, f"Profesor {profesor_id} no encontrado en máscaras"
        
        # Obtener índices
        curso_idx = mascaras.curso_to_idx[curso_id]
        materia_idx = mascaras.materia_to_idx[materia_id]
        profesor_idx = mascaras.profesor_to_idx[profesor_id]
        
        # Verificar que el día y bloque sean válidos
        if dia not in mascaras.dias_clase:
            return False, f"Día {dia} no válido"
        if not (1 <= bloque <= mascaras.bloques_por_dia):
            return False, f"Bloque {bloque} fuera de rango"
        
        dia_idx = mascaras.dias_clase.index(dia)
        bloque_idx = bloque - 1
        
        # 1. Verificar que el bloque sea tipo "clase"
        if not mascaras.bloque_tipo_clase[dia_idx, bloque_idx]:
            return False, f"Bloque {bloque} en {dia} no es tipo 'clase'"
        
        # 2. Verificar disponibilidad del profesor
        if not mascaras.profesor_disponible[profesor_idx, dia_idx, bloque_idx]:
            return False, f"Profesor {profesor_id} no disponible en {dia} bloque {bloque}"
        
        # 3. Verificar compatibilidad profesor-materia
        if not mascaras.profesor_materia[profesor_idx, materia_idx]:
            return False, f"Profesor {profesor_id} no puede enseñar materia {materia_id}"
        
        # 4. Verificar que la materia esté en el plan del curso
        if not mascaras.curso_materia[curso_idx, materia_idx]:
            return False, f"Materia {materia_id} no está en el plan del curso {curso_id}"
        
        return True, "Slot válido"
        
    except Exception as e:
        return False, f"Error en validación: {str(e)}"

def obtener_slots_disponibles_profesor(
    mascaras: MascarasOptimizadas, 
    profesor_id: int
) -> List[Tuple[str, int]]:
    """
    Obtiene todos los slots disponibles para un profesor usando máscaras.
    Retorna lista de (dia, bloque).
    """
    if profesor_id not in mascaras.profesor_to_idx:
        return []
    
    profesor_idx = mascaras.profesor_to_idx[profesor_id]
    slots_disponibles = []
    
    for dia_idx, dia in enumerate(mascaras.dias_clase):
        for bloque_idx in range(mascaras.bloques_por_dia):
            if (mascaras.profesor_disponible[profesor_idx, dia_idx, bloque_idx] and 
                mascaras.bloque_tipo_clase[dia_idx, bloque_idx]):
                slots_disponibles.append((dia, bloque_idx + 1))
    
    return slots_disponibles

def obtener_materias_profesor(
    mascaras: MascarasOptimizadas, 
    profesor_id: int
) -> List[int]:
    """
    Obtiene todas las materias que puede enseñar un profesor usando máscaras.
    Retorna lista de IDs de materias.
    """
    if profesor_id not in mascaras.profesor_to_idx:
        return []
    
    profesor_idx = mascaras.profesor_to_idx[profesor_id]
    materias = []
    
    for materia_id, materia_idx in mascaras.materia_to_idx.items():
        if mascaras.profesor_materia[profesor_idx, materia_idx]:
            materias.append(materia_id)
    
    return materias

def obtener_materias_curso(
    mascaras: MascarasOptimizadas, 
    curso_id: int
) -> List[int]:
    """
    Obtiene todas las materias del plan de un curso usando máscaras.
    Retorna lista de IDs de materias.
    """
    if curso_id not in mascaras.curso_to_idx:
        return []
    
    curso_idx = mascaras.curso_to_idx[curso_id]
    materias = []
    
    for materia_id, materia_idx in mascaras.materia_to_idx.items():
        if mascaras.curso_materia[curso_idx, materia_idx]:
            materias.append(materia_id)
    
    return materias

def obtener_aula_fija_curso(
    mascaras: MascarasOptimizadas, 
    curso_id: int
) -> int:
    """
    Obtiene el ID del aula fija de un curso usando máscaras.
    Retorna ID del aula o None si no tiene aula fija.
    """
    if curso_id not in mascaras.curso_to_idx:
        return None
    
    curso_idx = mascaras.curso_to_idx[curso_id]
    
    for aula_id, aula_idx in mascaras.aula_to_idx.items():
        if mascaras.curso_aula_fija[curso_idx, aula_idx]:
            return aula_id
    
    return None 