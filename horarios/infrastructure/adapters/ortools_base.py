"""
Módulo opcional de OR-Tools para generar horarios base cuando el GA falla.

Este módulo implementa un generador de horarios usando CP-SAT que asigna:
- (curso, día, bloque) único
- (profesor, día, bloque) único  
- Disponibilidad de profesor
- bloques_por_semana por materia
- Solo bloques tipo 'clase'

Sin preferencias blandas (eso lo pule el GA luego).
"""

import logging
from typing import Dict, List, Tuple, Optional
from collections import defaultdict

logger = logging.getLogger(__name__)

# Intentar importar OR-Tools
try:
    from ortools.sat.python import cp_model
    ORTOOLS_AVAILABLE = True
    logger.info("OR-Tools disponible para fallback")
except ImportError:
    ORTOOLS_AVAILABLE = False
    logger.warning("OR-Tools no disponible - fallback desactivado")

def generar_horario_ortools(datos, mapeos) -> Optional[Dict]:
    """
    Genera un horario base usando OR-Tools CP-SAT.
    
    Args:
        datos: Datos del horario
        mapeos: Mapeos de índices para conversión
        
    Returns:
        Diccionario de horarios o None si falla
    """
    if not ORTOOLS_AVAILABLE:
        logger.warning("OR-Tools no disponible")
        return None
    
    try:
        logger.info("Generando horario base con OR-Tools CP-SAT...")
        
        # Crear modelo CP-SAT
        model = cp_model.CpModel()
        
        # Variables de decisión: x[curso_idx][dia_idx][bloque_idx][materia_idx][profesor_idx]
        # 1 si se asigna, 0 si no
        x = {}
        for curso_idx in range(mapeos['n_cursos']):
            for dia_idx in range(mapeos['n_dias']):
                for bloque_idx in range(mapeos['n_bloques']):
                    for materia_idx in range(mapeos['n_materias']):
                        for profesor_idx in range(mapeos['n_profesores']):
                            x[curso_idx, dia_idx, bloque_idx, materia_idx, profesor_idx] = model.NewBoolVar(
                                f'x_{curso_idx}_{dia_idx}_{bloque_idx}_{materia_idx}_{profesor_idx}'
                            )
        
        # Restricción 1: Cada slot (curso, dia, bloque) debe tener exactamente una asignación
        for curso_idx in range(mapeos['n_cursos']):
            for dia_idx in range(mapeos['n_dias']):
                for bloque_idx in range(mapeos['n_bloques']):
                    model.AddExactlyOne([
                        x[curso_idx, dia_idx, bloque_idx, materia_idx, profesor_idx]
                        for materia_idx in range(mapeos['n_materias'])
                        for profesor_idx in range(mapeos['n_profesores'])
                    ])
        
        # Restricción 2: Cada profesor solo puede estar en un lugar a la vez
        for profesor_idx in range(mapeos['n_profesores']):
            for dia_idx in range(mapeos['n_dias']):
                for bloque_idx in range(mapeos['n_bloques']):
                    model.AddAtMostOne([
                        x[curso_idx, dia_idx, bloque_idx, materia_idx, profesor_idx]
                        for curso_idx in range(mapeos['n_cursos'])
                        for materia_idx in range(mapeos['n_materias'])
                    ])
        
        # Restricción 3: Cada materia debe cumplir bloques_por_semana por curso
        for curso_idx in range(mapeos['n_cursos']):
            curso_id = mapeos['idx_to_curso'][curso_idx]
            curso = datos.cursos[curso_id]
            
            for materia_id in curso.materias:
                if materia_id not in datos.materias:
                    continue
                    
                materia = datos.materias[materia_id]
                materia_idx = mapeos['materia_to_idx'][materia_id]
                bloques_requeridos = materia.bloques_por_semana
                
                # Suma de asignaciones debe ser igual a bloques_requeridos
                model.Add(
                    sum([
                        x[curso_idx, dia_idx, bloque_idx, materia_idx, profesor_idx]
                        for dia_idx in range(mapeos['n_dias'])
                        for bloque_idx in range(mapeos['n_bloques'])
                        for profesor_idx in range(mapeos['n_profesores'])
                    ]) == bloques_requeridos
                )
        
        # Restricción 4: Solo asignar donde el profesor esté disponible
        for curso_idx in range(mapeos['n_cursos']):
            for dia_idx in range(mapeos['n_dias']):
                for bloque_idx in range(mapeos['n_bloques']):
                    for materia_idx in range(mapeos['n_materias']):
                        for profesor_idx in range(mapeos['n_profesores']):
                            profesor_id = mapeos['idx_to_profesor'][profesor_idx]
                            dia = mapeos['idx_to_dia'][dia_idx]
                            bloque = mapeos['idx_to_bloque'][bloque_idx]
                            
                            # Si el profesor no está disponible en este slot, forzar x = 0
                            if profesor_id in datos.profesores:
                                profesor = datos.profesores[profesor_id]
                                if (dia, bloque) not in profesor.disponibilidad:
                                    model.Add(x[curso_idx, dia_idx, bloque_idx, materia_idx, profesor_idx] == 0)
        
        # Restricción 5: Solo asignar materias que pertenezcan al curso
        for curso_idx in range(mapeos['n_cursos']):
            curso_id = mapeos['idx_to_curso'][curso_idx]
            curso = datos.cursos[curso_id]
            
            for materia_idx in range(mapeos['n_materias']):
                materia_id = mapeos['idx_to_materia'][materia_idx]
                
                # Si la materia no pertenece al curso, forzar x = 0
                if materia_id not in curso.materias:
                    for dia_idx in range(mapeos['n_dias']):
                        for bloque_idx in range(mapeos['n_bloques']):
                            for profesor_idx in range(mapeos['n_profesores']):
                                model.Add(x[curso_idx, dia_idx, bloque_idx, materia_idx, profesor_idx] == 0)
        
        # Restricción 6: Solo asignar profesores que puedan dar la materia
        for materia_idx in range(mapeos['n_materias']):
            materia_id = mapeos['idx_to_materia'][materia_idx]
            
            if materia_id in datos.materias:
                materia = datos.materias[materia_id]
                
                for profesor_idx in range(mapeos['n_profesores']):
                    profesor_id = mapeos['idx_to_profesor'][profesor_idx]
                    
                    # Si el profesor no puede dar la materia, forzar x = 0
                    if profesor_id not in materia.profesores:
                        for curso_idx in range(mapeos['n_cursos']):
                            for dia_idx in range(mapeos['n_dias']):
                                for bloque_idx in range(mapeos['n_bloques']):
                                    model.Add(x[curso_idx, dia_idx, bloque_idx, materia_idx, profesor_idx] == 0)
        
        # Resolver el modelo
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 30.0  # Timeout de 30 segundos
        
        logger.info("Resolviendo modelo CP-SAT...")
        status = solver.Solve(model)
        
        if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
            logger.info(f"OR-Tools encontró solución: {status}")
            
            # Convertir solución a formato de horarios
            horarios = {}
            
            for curso_idx in range(mapeos['n_cursos']):
                for dia_idx in range(mapeos['n_dias']):
                    for bloque_idx in range(mapeos['n_bloques']):
                        for materia_idx in range(mapeos['n_materias']):
                            for profesor_idx in range(mapeos['n_profesores']):
                                if solver.Value(x[curso_idx, dia_idx, bloque_idx, materia_idx, profesor_idx]) == 1:
                                    curso_id = mapeos['idx_to_curso'][curso_idx]
                                    dia = mapeos['idx_to_dia'][dia_idx]
                                    bloque = mapeos['idx_to_bloque'][bloque_idx]
                                    materia_id = mapeos['idx_to_materia'][materia_idx]
                                    profesor_id = mapeos['idx_to_profesor'][profesor_idx]
                                    
                                    horarios[(curso_id, dia, bloque)] = (materia_id, profesor_id)
            
            logger.info(f"Horario generado con {len(horarios)} asignaciones")
            return horarios
            
        else:
            logger.warning(f"OR-Tools no pudo encontrar solución: {status}")
            return None
            
    except Exception as e:
        logger.error(f"Error en OR-Tools: {e}")
        return None

def verificar_ortools_disponible() -> bool:
    """Verifica si OR-Tools está disponible."""
    return ORTOOLS_AVAILABLE 