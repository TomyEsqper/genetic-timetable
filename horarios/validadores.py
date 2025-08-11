"""
Validadores robustos para el generador de horarios.

Este módulo implementa validaciones exhaustivas para asegurar que los horarios
cumplan todas las restricciones antes de ser persistidos en la base de datos.
"""

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
class ErrorValidacion:
    tipo: str
    mensaje: str
    detalles: Dict[str, Any]
    severidad: str = "error"  # error, warning, info

@dataclass
class ResultadoValidacion:
    es_valido: bool
    errores: List[ErrorValidacion]
    advertencias: List[ErrorValidacion]
    estadisticas: Dict[str, Any]

class ValidadorHorarios:
    """
    Validador robusto para horarios escolares.
    
    Verifica todas las restricciones duras y blandas antes de la persistencia.
    """
    
    def __init__(self):
        self.errores = []
        self.advertencias = []
        self.estadisticas = {}
    
    def validar_horario_completo(self, horarios: List[Dict]) -> ResultadoValidacion:
        """
        Valida un conjunto completo de horarios.
        
        Args:
            horarios: Lista de diccionarios con estructura de horario
            
        Returns:
            ResultadoValidacion con todos los errores y advertencias encontrados
        """
        self.errores = []
        self.advertencias = []
        self.estadisticas = {}
        
        logger.info(f"Validando {len(horarios)} horarios...")
        
        # Validaciones de restricciones duras
        self._validar_unicidad_curso_dia_bloque(horarios)
        self._validar_unicidad_profesor_dia_bloque(horarios)
        self._validar_disponibilidad_profesores(horarios)
        self._validar_bloques_por_semana(horarios)
        self._validar_bloques_tipo_clase(horarios)
        self._validar_aulas_fijas(horarios)
        
        # Validaciones de restricciones blandas
        self._validar_distribucion_materias(horarios)
        self._validar_preferencias_profesores(horarios)
        
        # Calcular estadísticas
        self._calcular_estadisticas(horarios)
        
        es_valido = len(self.errores) == 0
        
        logger.info(f"Validación completada. Válido: {es_valido}, "
                   f"Errores: {len(self.errores)}, Advertencias: {len(self.advertencias)}")
        
        return ResultadoValidacion(
            es_valido=es_valido,
            errores=self.errores,
            advertencias=self.advertencias,
            estadisticas=self.estadisticas
        )
    
    def _validar_unicidad_curso_dia_bloque(self, horarios: List[Dict]):
        """Valida que no haya duplicados en (curso, día, bloque)."""
        slots_curso = set()
        duplicados = []
        
        for horario in horarios:
            key = (horario['curso_id'], horario['dia'], horario['bloque'])
            if key in slots_curso:
                duplicados.append({
                    'curso_id': horario['curso_id'],
                    'curso_nombre': horario.get('curso_nombre', ''),
                    'dia': horario['dia'],
                    'bloque': horario['bloque'],
                    'materia_id': horario['materia_id'],
                    'profesor_id': horario['profesor_id']
                })
            else:
                slots_curso.add(key)
        
        if duplicados:
            self.errores.append(ErrorValidacion(
                tipo="duplicado_curso_dia_bloque",
                mensaje=f"Se encontraron {len(duplicados)} duplicados en (curso, día, bloque)",
                detalles={'duplicados': duplicados},
                severidad="error"
            ))
    
    def _validar_unicidad_profesor_dia_bloque(self, horarios: List[Dict]):
        """Valida que no haya choques de profesores en (profesor, día, bloque)."""
        slots_profesor = set()
        choques = []
        
        for horario in horarios:
            key = (horario['profesor_id'], horario['dia'], horario['bloque'])
            if key in slots_profesor:
                choques.append({
                    'profesor_id': horario['profesor_id'],
                    'profesor_nombre': horario.get('profesor_nombre', ''),
                    'dia': horario['dia'],
                    'bloque': horario['bloque'],
                    'curso_id': horario['curso_id'],
                    'materia_id': horario['materia_id']
                })
            else:
                slots_profesor.add(key)
        
        if choques:
            self.errores.append(ErrorValidacion(
                tipo="choque_profesor_dia_bloque",
                mensaje=f"Se encontraron {len(choques)} choques de profesores",
                detalles={'choques': choques},
                severidad="error"
            ))
    
    def _validar_disponibilidad_profesores(self, horarios: List[Dict]):
        """Valida que los profesores solo estén asignados en bloques disponibles."""
        # Cargar disponibilidad de profesores
        disponibilidad = {}
        for disp in DisponibilidadProfesor.objects.all():
            if disp.profesor_id not in disponibilidad:
                disponibilidad[disp.profesor_id] = set()
            for bloque in range(disp.bloque_inicio, disp.bloque_fin + 1):
                disponibilidad[disp.profesor_id].add((disp.dia, bloque))
        
        asignaciones_invalidas = []
        
        for horario in horarios:
            profesor_id = horario['profesor_id']
            dia = horario['dia']
            bloque = horario['bloque']
            
            if profesor_id in disponibilidad:
                if (dia, bloque) not in disponibilidad[profesor_id]:
                    asignaciones_invalidas.append({
                        'profesor_id': profesor_id,
                        'profesor_nombre': horario.get('profesor_nombre', ''),
                        'dia': dia,
                        'bloque': bloque,
                        'curso_id': horario['curso_id'],
                        'materia_id': horario['materia_id']
                    })
            else:
                # Profesor sin disponibilidad definida
                asignaciones_invalidas.append({
                    'profesor_id': profesor_id,
                    'profesor_nombre': horario.get('profesor_nombre', ''),
                    'dia': dia,
                    'bloque': bloque,
                    'curso_id': horario['curso_id'],
                    'materia_id': horario['materia_id'],
                    'causa': 'profesor_sin_disponibilidad'
                })
        
        if asignaciones_invalidas:
            self.errores.append(ErrorValidacion(
                tipo="disponibilidad_profesor",
                mensaje=f"Se encontraron {len(asignaciones_invalidas)} asignaciones fuera de disponibilidad",
                detalles={'asignaciones_invalidas': asignaciones_invalidas},
                severidad="error"
            ))
    
    def _validar_bloques_por_semana(self, horarios: List[Dict]):
        """Valida que cada materia cumpla exactamente con bloques_por_semana."""
        # Cargar bloques requeridos por materia
        bloques_requeridos = {}
        for materia in Materia.objects.all():
            bloques_requeridos[materia.id] = materia.bloques_por_semana
        
        # Contar bloques asignados por curso y materia
        bloques_asignados = defaultdict(int)
        for horario in horarios:
            key = (horario['curso_id'], horario['materia_id'])
            bloques_asignados[key] += 1
        
        # Verificar diferencias
        diferencias = []
        for (curso_id, materia_id), asignados in bloques_asignados.items():
            requeridos = bloques_requeridos.get(materia_id, 0)
            if asignados != requeridos:
                diferencias.append({
                    'curso_id': curso_id,
                    'curso_nombre': next((h.get('curso_nombre', '') for h in horarios if h['curso_id'] == curso_id), ''),
                    'materia_id': materia_id,
                    'materia_nombre': next((h.get('materia_nombre', '') for h in horarios if h['materia_id'] == materia_id), ''),
                    'asignados': asignados,
                    'requeridos': requeridos,
                    'diferencia': asignados - requeridos
                })
        
        if diferencias:
            self.errores.append(ErrorValidacion(
                tipo="bloques_por_semana",
                mensaje=f"Se encontraron {len(diferencias)} materias con bloques incorrectos",
                detalles={'diferencias': diferencias},
                severidad="error"
            ))
    
    def _validar_bloques_tipo_clase(self, horarios: List[Dict]):
        """Valida que solo se usen bloques de tipo 'clase'."""
        # Cargar bloques válidos
        bloques_validos = set(BloqueHorario.objects.filter(tipo='clase').values_list('numero', flat=True))
        
        bloques_invalidos = []
        for horario in horarios:
            if horario['bloque'] not in bloques_validos:
                bloques_invalidos.append({
                    'curso_id': horario['curso_id'],
                    'curso_nombre': horario.get('curso_nombre', ''),
                    'dia': horario['dia'],
                    'bloque': horario['bloque'],
                    'materia_id': horario['materia_id'],
                    'profesor_id': horario['profesor_id']
                })
        
        if bloques_invalidos:
            self.errores.append(ErrorValidacion(
                tipo="bloque_tipo_invalido",
                mensaje=f"Se encontraron {len(bloques_invalidos)} asignaciones en bloques no válidos",
                detalles={'bloques_invalidos': bloques_invalidos},
                severidad="error"
            ))
    
    def _validar_aulas_fijas(self, horarios: List[Dict]):
        """Valida que cada curso use su aula fija asignada."""
        # Cargar aulas fijas de cursos
        aulas_fijas = {}
        for curso in Curso.objects.all():
            if curso.aula_fija:
                aulas_fijas[curso.id] = curso.aula_fija.id
        
        aulas_incorrectas = []
        for horario in horarios:
            curso_id = horario['curso_id']
            aula_asignada = horario.get('aula_id')
            aula_fija = aulas_fijas.get(curso_id)
            
            if aula_fija and aula_asignada != aula_fija:
                aulas_incorrectas.append({
                    'curso_id': curso_id,
                    'curso_nombre': horario.get('curso_nombre', ''),
                    'aula_asignada': aula_asignada,
                    'aula_fija': aula_fija,
                    'dia': horario['dia'],
                    'bloque': horario['bloque']
                })
        
        if aulas_incorrectas:
            self.errores.append(ErrorValidacion(
                tipo="aula_fija",
                mensaje=f"Se encontraron {len(aulas_incorrectas)} asignaciones con aula incorrecta",
                detalles={'aulas_incorrectas': aulas_incorrectas},
                severidad="error"
            ))
    
    def _validar_distribucion_materias(self, horarios: List[Dict]):
        """Valida la distribución de materias (restricción blanda)."""
        # Verificar que no haya materias consecutivas en el mismo día
        materias_consecutivas = []
        
        for curso_id in set(h['curso_id'] for h in horarios):
            horarios_curso = [h for h in horarios if h['curso_id'] == curso_id]
            
            for dia in ['lunes', 'martes', 'miércoles', 'jueves', 'viernes']:
                horarios_dia = [h for h in horarios_curso if h['dia'] == dia]
                horarios_dia.sort(key=lambda x: x['bloque'])
                
                for i in range(len(horarios_dia) - 1):
                    if (horarios_dia[i]['materia_id'] == horarios_dia[i+1]['materia_id'] and
                        horarios_dia[i+1]['bloque'] - horarios_dia[i]['bloque'] == 1):
                        materias_consecutivas.append({
                            'curso_id': curso_id,
                            'curso_nombre': horarios_dia[i].get('curso_nombre', ''),
                            'materia_id': horarios_dia[i]['materia_id'],
                            'materia_nombre': horarios_dia[i].get('materia_nombre', ''),
                            'dia': dia,
                            'bloques': [horarios_dia[i]['bloque'], horarios_dia[i+1]['bloque']]
                        })
        
        if materias_consecutivas:
            self.advertencias.append(ErrorValidacion(
                tipo="materias_consecutivas",
                mensaje=f"Se encontraron {len(materias_consecutivas)} materias consecutivas",
                detalles={'materias_consecutivas': materias_consecutivas},
                severidad="warning"
            ))
    
    def _validar_preferencias_profesores(self, horarios: List[Dict]):
        """Valida preferencias de profesores (restricción blanda)."""
        # Esta validación se puede expandir según las preferencias específicas
        # Por ahora, solo registramos estadísticas
        pass
    
    def _calcular_estadisticas(self, horarios: List[Dict]):
        """Calcula estadísticas del horario generado."""
        if not horarios:
            return
        
        # Estadísticas básicas
        self.estadisticas = {
            'total_asignaciones': len(horarios),
            'cursos_unicos': len(set(h['curso_id'] for h in horarios)),
            'materias_unicas': len(set(h['materia_id'] for h in horarios)),
            'profesores_unicos': len(set(h['profesor_id'] for h in horarios)),
            'dias_utilizados': len(set(h['dia'] for h in horarios)),
            'bloques_utilizados': len(set(h['bloque'] for h in horarios))
        }
        
        # Distribución por día
        distribucion_dias = Counter(h['dia'] for h in horarios)
        self.estadisticas['distribucion_dias'] = dict(distribucion_dias)
        
        # Distribución por curso
        distribucion_cursos = Counter(h['curso_id'] for h in horarios)
        self.estadisticas['distribucion_cursos'] = dict(distribucion_cursos)
        
        # Distribución por materia
        distribucion_materias = Counter(h['materia_id'] for h in horarios)
        self.estadisticas['distribucion_materias'] = dict(distribucion_materias)

def validar_antes_de_persistir(horarios: List[Dict]) -> ResultadoValidacion:
    """
    Función de conveniencia para validar horarios antes de persistir.
    
    Args:
        horarios: Lista de horarios a validar
        
    Returns:
        ResultadoValidacion con el resultado de la validación
    """
    validador = ValidadorHorarios()
    return validador.validar_horario_completo(horarios) 