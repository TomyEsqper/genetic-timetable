"""
Reparador de cromosomas para el algoritmo genético.

Este módulo implementa estrategias de reparación para corregir individuos inviables
durante la evolución del algoritmo genético.
"""

import random
import logging
from typing import Dict, List, Set, Tuple, Any, Optional
from dataclasses import dataclass
from collections import defaultdict, Counter

from horarios.models import (
    Horario, Curso, Materia, Profesor, DisponibilidadProfesor,
    BloqueHorario, MateriaGrado, MateriaProfesor
)

logger = logging.getLogger(__name__)

@dataclass
class Reparacion:
    tipo: str
    descripcion: str
    genes_afectados: List[Tuple]
    exitosa: bool

class ReparadorCromosomas:
    """
    Reparador de cromosomas para corregir individuos inviables.
    
    Implementa múltiples estrategias de reparación para diferentes tipos de conflictos.
    """
    
    def __init__(self, datos):
        self.datos = datos
        self.reparaciones_realizadas = []
        self.max_intentos_reparacion = 10
    
    def reparar_cromosoma(self, cromosoma) -> Tuple[bool, List[Reparacion]]:
        """
        Intenta reparar un cromosoma inviable.
        
        Args:
            cromosoma: Cromosoma a reparar
            
        Returns:
            Tuple con (éxito, lista de reparaciones realizadas)
        """
        self.reparaciones_realizadas = []
        intentos = 0
        
        while intentos < self.max_intentos_reparacion:
            # Detectar conflictos
            conflictos = self._detectar_conflictos(cromosoma)
            
            if not conflictos:
                logger.info("Cromosoma reparado exitosamente")
                return True, self.reparaciones_realizadas
            
            # Intentar reparar el conflicto más crítico
            conflicto_critico = self._seleccionar_conflicto_critico(conflictos)
            reparacion_exitosa = self._aplicar_reparacion(cromosoma, conflicto_critico)
            
            if not reparacion_exitosa:
                logger.warning(f"No se pudo reparar conflicto: {conflicto_critico['tipo']}")
                break
            
            intentos += 1
        
        logger.warning(f"Cromosoma no pudo ser reparado después de {intentos} intentos")
        return False, self.reparaciones_realizadas
    
    def _detectar_conflictos(self, cromosoma) -> List[Dict]:
        """Detecta todos los conflictos en un cromosoma."""
        conflictos = []
        
        # Detectar duplicados curso-día-bloque
        duplicados_curso = self._detectar_duplicados_curso(cromosoma)
        conflictos.extend(duplicados_curso)
        
        # Detectar choques de profesores
        choques_profesor = self._detectar_choques_profesor(cromosoma)
        conflictos.extend(choques_profesor)
        
        # Detectar asignaciones fuera de disponibilidad
        disponibilidad_invalida = self._detectar_disponibilidad_invalida(cromosoma)
        conflictos.extend(disponibilidad_invalida)
        
        # Detectar bloques incorrectos
        bloques_incorrectos = self._detectar_bloques_incorrectos(cromosoma)
        conflictos.extend(bloques_incorrectos)
        
        return conflictos
    
    def _detectar_duplicados_curso(self, cromosoma) -> List[Dict]:
        """Detecta duplicados en (curso, día, bloque)."""
        slots_curso = {}
        duplicados = []
        
        for (curso_id, dia, bloque), (materia_id, profesor_id) in cromosoma.genes.items():
            key = (curso_id, dia, bloque)
            if key in slots_curso:
                duplicados.append({
                    'tipo': 'duplicado_curso',
                    'severidad': 'alta',
                    'genes': [slots_curso[key], (curso_id, dia, bloque)],
                    'descripcion': f'Duplicado en curso {curso_id}, día {dia}, bloque {bloque}'
                })
            else:
                slots_curso[key] = (curso_id, dia, bloque)
        
        return duplicados
    
    def _detectar_choques_profesor(self, cromosoma) -> List[Dict]:
        """Detecta choques de profesores en (profesor, día, bloque)."""
        slots_profesor = {}
        choques = []
        
        for (curso_id, dia, bloque), (materia_id, profesor_id) in cromosoma.genes.items():
            key = (profesor_id, dia, bloque)
            if key in slots_profesor:
                choques.append({
                    'tipo': 'choque_profesor',
                    'severidad': 'alta',
                    'genes': [slots_profesor[key], (curso_id, dia, bloque)],
                    'descripcion': f'Choque de profesor {profesor_id} en día {dia}, bloque {bloque}'
                })
            else:
                slots_profesor[key] = (curso_id, dia, bloque)
        
        return choques
    
    def _detectar_disponibilidad_invalida(self, cromosoma) -> List[Dict]:
        """Detecta asignaciones fuera de disponibilidad de profesores."""
        asignaciones_invalidas = []
        
        for (curso_id, dia, bloque), (materia_id, profesor_id) in cromosoma.genes.items():
            if profesor_id in self.datos.profesores:
                profesor = self.datos.profesores[profesor_id]
                if (dia, bloque) not in profesor.disponibilidad:
                    asignaciones_invalidas.append({
                        'tipo': 'disponibilidad_invalida',
                        'severidad': 'media',
                        'genes': [(curso_id, dia, bloque)],
                        'descripcion': f'Profesor {profesor_id} no disponible en {dia}, bloque {bloque}'
                    })
        
        return asignaciones_invalidas
    
    def _detectar_bloques_incorrectos(self, cromosoma) -> List[Dict]:
        """Detecta asignaciones en bloques no válidos."""
        bloques_invalidos = []
        
        for (curso_id, dia, bloque), (materia_id, profesor_id) in cromosoma.genes.items():
            if bloque not in self.datos.bloques_disponibles:
                bloques_invalidos.append({
                    'tipo': 'bloque_invalido',
                    'severidad': 'alta',
                    'genes': [(curso_id, dia, bloque)],
                    'descripcion': f'Bloque {bloque} no válido (no es tipo clase)'
                })
        
        return bloques_invalidos
    
    def _seleccionar_conflicto_critico(self, conflictos: List[Dict]) -> Dict:
        """Selecciona el conflicto más crítico para reparar primero."""
        # Priorizar por severidad: alta > media > baja
        severidades = {'alta': 3, 'media': 2, 'baja': 1}
        
        return max(conflictos, key=lambda c: severidades.get(c['severidad'], 0))
    
    def _aplicar_reparacion(self, cromosoma, conflicto: Dict) -> bool:
        """Aplica una reparación específica según el tipo de conflicto."""
        tipo_conflicto = conflicto['tipo']
        
        if tipo_conflicto == 'duplicado_curso':
            return self._reparar_duplicado_curso(cromosoma, conflicto)
        elif tipo_conflicto == 'choque_profesor':
            return self._reparar_choque_profesor(cromosoma, conflicto)
        elif tipo_conflicto == 'disponibilidad_invalida':
            return self._reparar_disponibilidad_invalida(cromosoma, conflicto)
        elif tipo_conflicto == 'bloque_invalido':
            return self._reparar_bloque_invalido(cromosoma, conflicto)
        else:
            logger.warning(f"Tipo de conflicto no manejado: {tipo_conflicto}")
            return False
    
    def _reparar_duplicado_curso(self, cromosoma, conflicto: Dict) -> bool:
        """Repara duplicados en (curso, día, bloque)."""
        genes_afectados = conflicto['genes']
        
        # Mantener el primer gen y reasignar el segundo
        gen_a_reasignar = genes_afectados[1]
        curso_id, dia, bloque = gen_a_reasignar
        materia_id, profesor_id = cromosoma.genes[gen_a_reasignar]
        
        # Buscar un nuevo slot disponible
        nuevo_slot = self._encontrar_slot_disponible_curso(cromosoma, curso_id, materia_id, profesor_id)
        
        if nuevo_slot:
            # Eliminar asignación anterior
            del cromosoma.genes[gen_a_reasignar]
            
            # Crear nueva asignación
            cromosoma.genes[nuevo_slot] = (materia_id, profesor_id)
            
            self.reparaciones_realizadas.append(Reparacion(
                tipo='duplicado_curso',
                descripcion=f'Reasignado curso {curso_id} de {dia} bloque {bloque} a {nuevo_slot[1]} bloque {nuevo_slot[2]}',
                genes_afectados=[gen_a_reasignar, nuevo_slot],
                exitosa=True
            ))
            
            return True
        
        return False
    
    def _reparar_choque_profesor(self, cromosoma, conflicto: Dict) -> bool:
        """Repara choques de profesores."""
        genes_afectados = conflicto['genes']
        
        # Intentar reasignar el segundo gen
        gen_a_reasignar = genes_afectados[1]
        curso_id, dia, bloque = gen_a_reasignar
        materia_id, profesor_id = cromosoma.genes[gen_a_reasignar]
        
        # Buscar un nuevo slot disponible para el profesor
        nuevo_slot = self._encontrar_slot_disponible_profesor(cromosoma, curso_id, materia_id, profesor_id)
        
        if nuevo_slot:
            # Eliminar asignación anterior
            del cromosoma.genes[gen_a_reasignar]
            
            # Crear nueva asignación
            cromosoma.genes[nuevo_slot] = (materia_id, profesor_id)
            
            self.reparaciones_realizadas.append(Reparacion(
                tipo='choque_profesor',
                descripcion=f'Reasignado profesor {profesor_id} de {dia} bloque {bloque} a {nuevo_slot[1]} bloque {nuevo_slot[2]}',
                genes_afectados=[gen_a_reasignar, nuevo_slot],
                exitosa=True
            ))
            
            return True
        
        return False
    
    def _reparar_disponibilidad_invalida(self, cromosoma, conflicto: Dict) -> bool:
        """Repara asignaciones fuera de disponibilidad."""
        genes_afectados = conflicto['genes']
        gen_a_reasignar = genes_afectados[0]
        curso_id, dia, bloque = gen_a_reasignar
        materia_id, profesor_id = cromosoma.genes[gen_a_reasignar]
        
        # Buscar un slot disponible para el profesor
        nuevo_slot = self._encontrar_slot_disponible_profesor(cromosoma, curso_id, materia_id, profesor_id)
        
        if nuevo_slot:
            # Eliminar asignación anterior
            del cromosoma.genes[gen_a_reasignar]
            
            # Crear nueva asignación
            cromosoma.genes[nuevo_slot] = (materia_id, profesor_id)
            
            self.reparaciones_realizadas.append(Reparacion(
                tipo='disponibilidad_invalida',
                descripcion=f'Reasignado profesor {profesor_id} de slot no disponible a {nuevo_slot[1]} bloque {nuevo_slot[2]}',
                genes_afectados=[gen_a_reasignar, nuevo_slot],
                exitosa=True
            ))
            
            return True
        
        return False
    
    def _reparar_bloque_invalido(self, cromosoma, conflicto: Dict) -> bool:
        """Repara asignaciones en bloques no válidos."""
        genes_afectados = conflicto['genes']
        gen_a_reasignar = genes_afectados[0]
        curso_id, dia, bloque = gen_a_reasignar
        materia_id, profesor_id = cromosoma.genes[gen_a_reasignar]
        
        # Buscar un slot válido
        nuevo_slot = self._encontrar_slot_disponible_curso(cromosoma, curso_id, materia_id, profesor_id)
        
        if nuevo_slot:
            # Eliminar asignación anterior
            del cromosoma.genes[gen_a_reasignar]
            
            # Crear nueva asignación
            cromosoma.genes[nuevo_slot] = (materia_id, profesor_id)
            
            self.reparaciones_realizadas.append(Reparacion(
                tipo='bloque_invalido',
                descripcion=f'Reasignado de bloque inválido {bloque} a bloque válido {nuevo_slot[2]}',
                genes_afectados=[gen_a_reasignar, nuevo_slot],
                exitosa=True
            ))
            
            return True
        
        return False
    
    def _encontrar_slot_disponible_curso(self, cromosoma, curso_id: int, materia_id: int, profesor_id: int) -> Optional[Tuple]:
        """Encuentra un slot disponible para un curso específico."""
        # Obtener disponibilidad del profesor
        if profesor_id not in self.datos.profesores:
            return None
        
        profesor = self.datos.profesores[profesor_id]
        disponibilidad = list(profesor.disponibilidad)
        random.shuffle(disponibilidad)  # Aleatorizar para diversidad
        
        for dia, bloque in disponibilidad:
            # Verificar que el bloque sea válido
            if bloque not in self.datos.bloques_disponibles:
                continue
            
            # Verificar que el slot no esté ocupado por el curso
            if (curso_id, dia, bloque) in cromosoma.genes:
                continue
            
            # Verificar que el profesor no esté ocupado
            profesor_ocupado = False
            for (c_id, d, b), (_, p_id) in cromosoma.genes.items():
                if p_id == profesor_id and d == dia and b == bloque:
                    profesor_ocupado = True
                    break
            
            if not profesor_ocupado:
                return (curso_id, dia, bloque)
        
        return None
    
    def _encontrar_slot_disponible_profesor(self, cromosoma, curso_id: int, materia_id: int, profesor_id: int) -> Optional[Tuple]:
        """Encuentra un slot disponible para un profesor específico."""
        # Obtener disponibilidad del profesor
        if profesor_id not in self.datos.profesores:
            return None
        
        profesor = self.datos.profesores[profesor_id]
        disponibilidad = list(profesor.disponibilidad)
        random.shuffle(disponibilidad)  # Aleatorizar para diversidad
        
        for dia, bloque in disponibilidad:
            # Verificar que el bloque sea válido
            if bloque not in self.datos.bloques_disponibles:
                continue
            
            # Verificar que el slot no esté ocupado por el curso
            if (curso_id, dia, bloque) in cromosoma.genes:
                continue
            
            # Verificar que el profesor no esté ocupado
            profesor_ocupado = False
            for (c_id, d, b), (_, p_id) in cromosoma.genes.items():
                if p_id == profesor_id and d == dia and b == bloque:
                    profesor_ocupado = True
                    break
            
            if not profesor_ocupado:
                return (curso_id, dia, bloque)
        
        return None

def reparar_cromosoma(cromosoma, datos) -> Tuple[bool, List[Reparacion]]:
    """
    Función de conveniencia para reparar un cromosoma.
    
    Args:
        cromosoma: Cromosoma a reparar
        datos: Datos del horario
        
    Returns:
        Tuple con (éxito, lista de reparaciones realizadas)
    """
    reparador = ReparadorCromosomas(datos)
    return reparador.reparar_cromosoma(cromosoma) 