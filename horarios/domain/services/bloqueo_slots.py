"""
Sistema de bloqueo de slots y re-generación parcial.

Permite bloquear slots específicos (curso, dia, bloque) y regenerar
solo la parte del horario que no está bloqueada.
"""

import json
from typing import Dict, List, Tuple, Set, Optional
from dataclasses import dataclass
from django.core.cache import cache
from .models import Horario, Curso, Materia, Profesor

@dataclass
class SlotBloqueado:
    """Representa un slot bloqueado en el horario"""
    curso_id: int
    materia_id: int
    profesor_id: int
    dia: str
    bloque: int
    aula_id: Optional[int] = None
    razon: str = "manual"
    timestamp: str = ""
    
    def __post_init__(self):
        if not self.timestamp:
            from datetime import datetime
            self.timestamp = datetime.now().isoformat()
    
    def to_dict(self) -> Dict:
        """Convierte el slot bloqueado a diccionario"""
        return {
            'curso_id': self.curso_id,
            'materia_id': self.materia_id,
            'profesor_id': self.profesor_id,
            'dia': self.dia,
            'bloque': self.bloque,
            'aula_id': self.aula_id,
            'razon': self.razon,
            'timestamp': self.timestamp
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'SlotBloqueado':
        """Crea un SlotBloqueado desde un diccionario"""
        return cls(**data)

class GestorSlotsBloqueados:
    """
    Gestiona slots bloqueados/fijos en el horario.
    Permite regeneración parcial manteniendo asignaciones específicas.
    """
    
    def __init__(self, cache_key: str = "slots_bloqueados"):
        self.cache_key = cache_key
        self.slots_bloqueados: Set[Tuple[int, str, int]] = set()  # (curso_id, dia, bloque)
        self.detalles_slots: Dict[Tuple[int, str, int], SlotBloqueado] = {}
        self._cargar_desde_cache()
    
    def bloquear_slot(
        self,
        curso_id: int,
        materia_id: int,
        profesor_id: int,
        dia: str,
        bloque: int,
        aula_id: Optional[int] = None,
        razon: str = "manual"
    ) -> bool:
        """
        Bloquea un slot específico en el horario.
        
        Args:
            curso_id: ID del curso
            materia_id: ID de la materia
            profesor_id: ID del profesor
            dia: Día de la semana
            bloque: Número de bloque
            aula_id: ID del aula (opcional)
            razon: Razón del bloqueo
        
        Returns:
            True si se bloqueó exitosamente, False si ya estaba bloqueado
        """
        slot_key = (curso_id, dia, bloque)
        
        if slot_key in self.slots_bloqueados:
            return False  # Ya está bloqueado
        
        # Crear slot bloqueado
        slot_bloqueado = SlotBloqueado(
            curso_id=curso_id,
            materia_id=materia_id,
            profesor_id=profesor_id,
            dia=dia,
            bloque=bloque,
            aula_id=aula_id,
            razon=razon
        )
        
        # Agregar a las estructuras internas
        self.slots_bloqueados.add(slot_key)
        self.detalles_slots[slot_key] = slot_bloqueado
        
        # Guardar en cache
        self._guardar_en_cache()
        
        return True
    
    def desbloquear_slot(self, curso_id: int, dia: str, bloque: int) -> bool:
        """
        Desbloquea un slot específico.
        
        Args:
            curso_id: ID del curso
            dia: Día de la semana
            bloque: Número de bloque
        
        Returns:
            True si se desbloqueó exitosamente, False si no estaba bloqueado
        """
        slot_key = (curso_id, dia, bloque)
        
        if slot_key not in self.slots_bloqueados:
            return False  # No estaba bloqueado
        
        # Remover de las estructuras internas
        self.slots_bloqueados.remove(slot_key)
        if slot_key in self.detalles_slots:
            del self.detalles_slots[slot_key]
        
        # Guardar en cache
        self._guardar_en_cache()
        
        return True
    
    def es_slot_bloqueado(self, curso_id: int, dia: str, bloque: int) -> bool:
        """Verifica si un slot está bloqueado"""
        return (curso_id, dia, bloque) in self.slots_bloqueados
    
    def obtener_slot_bloqueado(
        self, 
        curso_id: int, 
        dia: str, 
        bloque: int
    ) -> Optional[SlotBloqueado]:
        """Obtiene los detalles de un slot bloqueado"""
        slot_key = (curso_id, dia, bloque)
        return self.detalles_slots.get(slot_key)
    
    def obtener_slots_bloqueados_curso(self, curso_id: int) -> List[SlotBloqueado]:
        """Obtiene todos los slots bloqueados de un curso específico"""
        slots = []
        for slot_key, slot in self.detalles_slots.items():
            if slot_key[0] == curso_id:  # curso_id
                slots.append(slot)
        return slots
    
    def obtener_slots_bloqueados_profesor(self, profesor_id: int) -> List[SlotBloqueado]:
        """Obtiene todos los slots bloqueados de un profesor específico"""
        return [slot for slot in self.detalles_slots.values() if slot.profesor_id == profesor_id]
    
    def obtener_slots_bloqueados_dia(self, dia: str) -> List[SlotBloqueado]:
        """Obtiene todos los slots bloqueados de un día específico"""
        return [slot for slot in self.detalles_slots.values() if slot.dia == dia]
    
    def obtener_todos_slots_bloqueados(self) -> List[SlotBloqueado]:
        """Obtiene todos los slots bloqueados"""
        return list(self.detalles_slots.values())
    
    def bloquear_desde_horario_existente(
        self, 
        curso_ids: Optional[List[int]] = None,
        razon: str = "preservar_existente"
    ) -> int:
        """
        Bloquea slots basándose en horarios existentes en la base de datos.
        
        Args:
            curso_ids: Lista de IDs de cursos a considerar (None = todos)
            razon: Razón del bloqueo
        
        Returns:
            Número de slots bloqueados
        """
        # Obtener horarios existentes
        queryset = Horario.objects.all()
        if curso_ids:
            queryset = queryset.filter(curso_id__in=curso_ids)
        
        slots_bloqueados = 0
        
        for horario in queryset:
            if self.bloquear_slot(
                curso_id=horario.curso_id,
                materia_id=horario.materia_id,
                profesor_id=horario.profesor_id,
                dia=horario.dia,
                bloque=horario.bloque,
                aula_id=horario.aula_id if horario.aula_id else None,
                razon=razon
            ):
                slots_bloqueados += 1
        
        return slots_bloqueados
    
    def bloquear_slots_por_restricciones(
        self,
        restricciones: List[Dict]
    ) -> int:
        """
        Bloquea slots basándose en restricciones específicas.
        
        Args:
            restricciones: Lista de restricciones con formato:
                {
                    'tipo': 'profesor_no_disponible' | 'aula_ocupada' | 'materia_requerida',
                    'curso_id': int,
                    'dia': str,
                    'bloque': int,
                    'materia_id': int,
                    'profesor_id': int,
                    'razon': str
                }
        
        Returns:
            Número de slots bloqueados
        """
        slots_bloqueados = 0
        
        for restriccion in restricciones:
            if self.bloquear_slot(
                curso_id=restriccion['curso_id'],
                materia_id=restriccion['materia_id'],
                profesor_id=restriccion['profesor_id'],
                dia=restriccion['dia'],
                bloque=restriccion['bloque'],
                razon=restriccion.get('razon', 'restriccion')
            ):
                slots_bloqueados += 1
        
        return slots_bloqueados
    
    def limpiar_slots_bloqueados(self, razon: Optional[str] = None) -> int:
        """
        Limpia slots bloqueados, opcionalmente por razón específica.
        
        Args:
            razon: Si se especifica, solo limpia slots con esa razón
        
        Returns:
            Número de slots desbloqueados
        """
        slots_a_limpiar = []
        
        for slot_key, slot in self.detalles_slots.items():
            if razon is None or slot.razon == razon:
                slots_a_limpiar.append(slot_key)
        
        slots_desbloqueados = 0
        for slot_key in slots_a_limpiar:
            if self.desbloquear_slot(slot_key[0], slot_key[1], slot_key[2]):
                slots_desbloqueados += 1
        
        return slots_desbloqueados
    
    def obtener_estadisticas(self) -> Dict:
        """Obtiene estadísticas de los slots bloqueados"""
        if not self.detalles_slots:
            return {
                "total_slots_bloqueados": 0,
                "por_curso": {},
                "por_profesor": {},
                "por_dia": {},
                "por_razon": {}
            }
        
        # Contar por curso
        por_curso = {}
        for slot in self.detalles_slots.values():
            curso_id = slot.curso_id
            por_curso[curso_id] = por_curso.get(curso_id, 0) + 1
        
        # Contar por profesor
        por_profesor = {}
        for slot in self.detalles_slots.values():
            profesor_id = slot.profesor_id
            por_profesor[profesor_id] = por_profesor.get(profesor_id, 0) + 1
        
        # Contar por día
        por_dia = {}
        for slot in self.detalles_slots.values():
            dia = slot.dia
            por_dia[dia] = por_dia.get(dia, 0) + 1
        
        # Contar por razón
        por_razon = {}
        for slot in self.detalles_slots.values():
            razon = slot.razon
            por_razon[razon] = por_razon.get(razon, 0) + 1
        
        return {
            "total_slots_bloqueados": len(self.detalles_slots),
            "por_curso": por_curso,
            "por_profesor": por_profesor,
            "por_dia": por_dia,
            "por_razon": por_razon
        }
    
    def exportar_configuracion(self, archivo: str = None) -> str:
        """
        Exporta la configuración de slots bloqueados a JSON.
        
        Args:
            archivo: Archivo donde guardar (opcional)
        
        Returns:
            JSON string con la configuración
        """
        configuracion = {
            "timestamp": self._obtener_timestamp_actual(),
            "total_slots": len(self.detalles_slots),
            "slots": [slot.to_dict() for slot in self.detalles_slots.values()]
        }
        
        json_str = json.dumps(configuracion, ensure_ascii=False, indent=2, default=str)
        
        if archivo:
            try:
                with open(archivo, 'w', encoding='utf-8') as f:
                    f.write(json_str)
            except Exception as e:
                raise Exception(f"Error guardando archivo: {e}")
        
        return json_str
    
    def importar_configuracion(self, configuracion_json: str) -> int:
        """
        Importa configuración de slots bloqueados desde JSON.
        
        Args:
            configuracion_json: JSON string con la configuración
        
        Returns:
            Número de slots importados
        """
        try:
            configuracion = json.loads(configuracion_json)
            slots_importados = 0
            
            # Limpiar slots existentes
            self.limpiar_slots_bloqueados()
            
            # Importar nuevos slots
            for slot_data in configuracion.get('slots', []):
                slot = SlotBloqueado.from_dict(slot_data)
                slot_key = (slot.curso_id, slot.dia, slot.bloque)
                
                self.slots_bloqueados.add(slot_key)
                self.detalles_slots[slot_key] = slot
                slots_importados += 1
            
            # Guardar en cache
            self._guardar_en_cache()
            
            return slots_importados
            
        except Exception as e:
            raise Exception(f"Error importando configuración: {e}")
    
    def _guardar_en_cache(self):
        """Guarda la configuración en cache"""
        try:
            configuracion_cache = {
                'slots_bloqueados': list(self.slots_bloqueados),
                'detalles_slots': {str(k): v.to_dict() for k, v in self.detalles_slots.items()}
            }
            cache.set(self.cache_key, configuracion_cache, timeout=3600)  # 1 hora
        except Exception:
            pass  # Fallback silencioso si cache falla
    
    def _cargar_desde_cache(self):
        """Carga la configuración desde cache"""
        try:
            configuracion_cache = cache.get(self.cache_key)
            if configuracion_cache:
                # Restaurar slots bloqueados
                self.slots_bloqueados = set(tuple(slot) for slot in configuracion_cache.get('slots_bloqueados', []))
                
                # Restaurar detalles
                self.detalles_slots = {}
                for k_str, v_dict in configuracion_cache.get('detalles_slots', {}).items():
                    k = eval(k_str)  # Convertir string de tupla a tupla
                    self.detalles_slots[k] = SlotBloqueado.from_dict(v_dict)
        except Exception:
            pass  # Fallback silencioso si cache falla
    
    def _obtener_timestamp_actual(self) -> str:
        """Obtiene timestamp actual en formato ISO"""
        from datetime import datetime
        return datetime.now().isoformat()

def crear_gestor_slots_bloqueados(cache_key: str = "slots_bloqueados") -> GestorSlotsBloqueados:
    """Función de conveniencia para crear un gestor de slots bloqueados"""
    return GestorSlotsBloqueados(cache_key)

def integrar_slots_bloqueados_en_ga(
    cromosoma: Dict[Tuple[int, str, int], Tuple[int, int]],
    gestor_slots: GestorSlotsBloqueados
) -> Dict[Tuple[int, str, int], Tuple[int, int]]:
    """
    Integra slots bloqueados en un cromosoma del GA.
    Los slots bloqueados no se pueden modificar durante la evolución.
    
    Args:
        cromosoma: Cromosoma actual del GA
        gestor_slots: Gestor de slots bloqueados
    
    Returns:
        Cromosoma con slots bloqueados integrados
    """
    cromosoma_integrado = cromosoma.copy()
    
    # Agregar slots bloqueados al cromosoma
    for slot in gestor_slots.obtener_todos_slots_bloqueados():
        slot_key = (slot.curso_id, slot.dia, slot.bloque)
        slot_value = (slot.materia_id, slot.profesor_id)
        
        # Solo agregar si no existe o es diferente
        if slot_key not in cromosoma_integrado or cromosoma_integrado[slot_key] != slot_value:
            cromosoma_integrado[slot_key] = slot_value
    
    return cromosoma_integrado

def validar_cromosoma_con_slots_bloqueados(
    cromosoma: Dict[Tuple[int, str, int], Tuple[int, int]],
    gestor_slots: GestorSlotsBloqueados
) -> Tuple[bool, List[str]]:
    """
    Valida que un cromosoma respete los slots bloqueados.
    
    Args:
        cromosoma: Cromosoma a validar
        gestor_slots: Gestor de slots bloqueados
    
    Returns:
        (es_valido, lista_errores)
    """
    errores = []
    
    for slot in gestor_slots.obtener_todos_slots_bloqueados():
        slot_key = (slot.curso_id, slot.dia, slot.bloque)
        slot_value_esperado = (slot.materia_id, slot.profesor_id)
        
        if slot_key in cromosoma:
            slot_value_actual = cromosoma[slot_key]
            if slot_value_actual != slot_value_esperado:
                errores.append(
                    f"Slot bloqueado violado: {slot_key} - "
                    f"Esperado: {slot_value_esperado}, "
                    f"Actual: {slot_value_actual}"
                )
        else:
            errores.append(f"Slot bloqueado faltante: {slot_key}")
    
    return len(errores) == 0, errores 