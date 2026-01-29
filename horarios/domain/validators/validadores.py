"""
Validadores robustos para el generador de horarios.

Este módulo implementa validaciones exhaustivas para asegurar que los horarios
cumplan todas las restricciones antes de ser persistidos en la base de datos.
"""

import logging
from typing import Dict, List, Set, Tuple, Any, Optional
from dataclasses import dataclass
from collections import defaultdict, Counter
from django.db.models import Q

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
        # Cargar disponibilidad de profesores de manera más eficiente
        disponibilidad = {}
        profesores_sin_disponibilidad = set()
        
        # Cargar todos los profesores
        todos_profesores = set(Profesor.objects.values_list('id', flat=True))
        
        # Cargar disponibilidad
        for disp in DisponibilidadProfesor.objects.select_related('profesor').all():
            if disp.profesor_id not in disponibilidad:
                disponibilidad[disp.profesor_id] = set()
            for bloque in range(disp.bloque_inicio, disp.bloque_fin + 1):
                disponibilidad[disp.profesor_id].add((disp.dia, bloque))
        
        # Identificar profesores sin disponibilidad
        profesores_sin_disponibilidad = todos_profesores - set(disponibilidad.keys())
        
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
                        'materia_id': horario['materia_id'],
                        'causa': 'fuera_disponibilidad'
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
            # Agrupar por causa para mejor diagnóstico
            por_causa = defaultdict(list)
            for asignacion in asignaciones_invalidas:
                por_causa[asignacion['causa']].append(asignacion)
            
            # Crear mensajes específicos por causa
            mensajes = []
            for causa, asignaciones in por_causa.items():
                if causa == 'profesor_sin_disponibilidad':
                    mensajes.append(f"{len(asignaciones)} asignaciones de profesores sin disponibilidad definida")
                elif causa == 'fuera_disponibilidad':
                    mensajes.append(f"{len(asignaciones)} asignaciones fuera de la disponibilidad del profesor")
            
            self.errores.append(ErrorValidacion(
                tipo="disponibilidad_profesor",
                mensaje=f"Se encontraron {len(asignaciones_invalidas)} asignaciones fuera de disponibilidad: {'; '.join(mensajes)}",
                detalles={'asignaciones_invalidas': asignaciones_invalidas},
                severidad="error"
            ))
        
        # Advertencia sobre profesores sin disponibilidad
        if profesores_sin_disponibilidad:
            nombres_profesores = list(Profesor.objects.filter(id__in=profesores_sin_disponibilidad).values_list('nombre', flat=True))
            self.advertencias.append(ErrorValidacion(
                tipo="profesores_sin_disponibilidad",
                mensaje=f"Hay {len(profesores_sin_disponibilidad)} profesores sin disponibilidad definida: {', '.join(nombres_profesores[:5])}{'...' if len(nombres_profesores) > 5 else ''}",
                detalles={'profesores_sin_disponibilidad': list(profesores_sin_disponibilidad)},
                severidad="advertencia"
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

# Utilitarios de prevalidación data-driven

def construir_semana_tipo_desde_bd() -> Dict[str, Any]:
    """
    Construye la "semana tipo" 100% desde datos en BD, sin asumir cantidades fijas.
    Retorna un diccionario con:
      - dias: lista ordenada de días presentes en datos (DisponibilidadProfesor o Horario)
      - bloques_clase: lista ordenada de números de bloque con tipo='clase' (desde BloqueHorario)
      - slots: lista de tuplas (dia, bloque) para cada combinación válida
      - slot_to_idx: dict {(dia, bloque) -> idx}
    Lanza ValueError si no hay datos suficientes (p.ej., no hay bloques tipo 'clase').
    """
    # Derivar días
    dias_set = set(DisponibilidadProfesor.objects.values_list('dia', flat=True))
    if not dias_set:
        dias_set = set(Horario.objects.values_list('dia', flat=True))
    dias = sorted(list(dias_set))
    
    # Derivar bloques de clase
    bloques_clase_qs = BloqueHorario.objects.filter(tipo='clase').values_list('numero', flat=True)
    bloques_clase = sorted(set(bloques_clase_qs))

    if not dias or not bloques_clase:
        raise ValueError("Datos insuficientes para construir semana tipo: faltan días o bloques tipo 'clase'")

    slots = []
    slot_to_idx = {}
    for dia in dias:
        for bloque in bloques_clase:
            slots.append((dia, bloque))
            slot_to_idx[(dia, bloque)] = len(slots) - 1

    return {
        'dias': dias,
        'bloques_clase': bloques_clase,
        'slots': slots,
        'slot_to_idx': slot_to_idx,
    }


def calcular_oferta_vs_demanda_por_materia() -> Dict[str, Any]:
    """
    Calcula Demanda y Oferta por materia de forma data-driven.
    - Demanda (por materia): suma de bloques_por_semana de todos los cursos que requieren esa materia.
      Un curso requiere una materia si existe MateriaGrado(grado=curso.grado, materia).
      Si no existe ninguna relación, la materia no se cuenta para ese curso.
    - Oferta (por materia): suma de slots disponibles reales de profesores habilitados para esa materia,
      considerando únicamente (dia, bloque) que sean tipo 'clase' y pertenezcan a la semana tipo derivada de BD.
    Retorna un dict con:
      - tabla: lista de filas {materia_id, materia_nombre, demanda_total, oferta_total, diferencia}
      - resumen: {'materias_con_deficit': int, 'faltantes_totales': int}
      - dimensiones: {'num_cursos', 'num_materias', 'num_profesores', 'num_slots'}
      - semana_tipo: {'dias', 'bloques_clase'} para trazabilidad
    """
    semana = construir_semana_tipo_desde_bd()
    dias = semana['dias']
    bloques_clase = set(semana['bloques_clase'])
    slots = semana['slots']

    # Índices para performance
    cursos = list(Curso.objects.select_related('grado').all())
    materias = list(Materia.objects.all())
    profesores = list(Profesor.objects.all())

    # Mapear requerimientos curso->materias
    mg_rel = set(MateriaGrado.objects.values_list('grado_id', 'materia_id'))

    # Demanda por materia
    demanda_por_materia = {m.id: 0 for m in materias}
    for curso in cursos:
        for materia in materias:
            if (curso.grado_id, materia.id) in mg_rel:
                demanda_por_materia[materia.id] += max(0, int(getattr(materia, 'bloques_por_semana', 0)))

    # Oferta por materia: sumar slots disponibles de profesores habilitados
    # Precomputar disponibilidad por profesor como set de (dia, bloque) filtrado a bloques tipo 'clase'
    disp_por_prof = {}
    for disp in DisponibilidadProfesor.objects.all():
        rango = range(int(disp.bloque_inicio), int(disp.bloque_fin) + 1)
        if disp.profesor_id not in disp_por_prof:
            disp_por_prof[disp.profesor_id] = set()
        for b in rango:
            if b in bloques_clase:
                disp_por_prof[disp.profesor_id].add((disp.dia, b))

    # Profesores habilitados por materia
    profs_por_materia = {}
    for mp in MateriaProfesor.objects.values_list('materia_id', 'profesor_id'):
        profs_por_materia.setdefault(mp[0], set()).add(mp[1])

    oferta_por_materia = {m.id: 0 for m in materias}
    for materia in materias:
        profesores_hab = profs_por_materia.get(materia.id, set())
        oferta = 0
        for pid in profesores_hab:
            slots_prof = disp_por_prof.get(pid, set())
            # Limitar a semana tipo (dia presente y bloque de clase). slots_prof ya filtrado por bloque.
            oferta += sum(1 for (d, b) in slots_prof if d in dias)
        oferta_por_materia[materia.id] = oferta

    # Construir tabla
    tabla = []
    materias_con_deficit = 0
    faltantes_totales = 0
    for materia in materias:
        dem = demanda_por_materia.get(materia.id, 0)
        ofe = oferta_por_materia.get(materia.id, 0)
        diff = ofe - dem
        if diff < 0:
            materias_con_deficit += 1
            faltantes_totales += (-diff)
        tabla.append({
            'materia_id': materia.id,
            'materia_nombre': materia.nombre,
            'demanda_total': int(dem),
            'oferta_total': int(ofe),
            'diferencia': int(diff),
        })

    dimensiones = {
        'num_cursos': len(cursos),
        'num_materias': len(materias),
        'num_profesores': len(profesores),
        'num_slots': len(slots),
    }

    resumen = {
        'materias_con_deficit': materias_con_deficit,
        'faltantes_totales': int(faltantes_totales),
    }

    return {
        'tabla': tabla,
        'resumen': resumen,
        'dimensiones': dimensiones,
        'semana_tipo': {'dias': dias, 'bloques_clase': sorted(list(bloques_clase))},
    }


def prevalidar_factibilidad_dataset() -> Dict[str, Any]:
    """
    Orquesta la prevalidación de factibilidad.
    Si alguna materia tiene oferta < demanda, retorna {'viable': False, 'oferta_vs_demanda': ..., 'motivo': 'instancia_inviable'}.
    En caso contrario, retorna {'viable': True, 'oferta_vs_demanda': ..., 'motivo': 'ok'}.
    """
    datos = calcular_oferta_vs_demanda_por_materia()
    deficit = [fila for fila in datos['tabla'] if fila['diferencia'] < 0]
    if deficit:
        return {
            'viable': False,
            'motivo': 'instancia_inviable',
            'oferta_vs_demanda': datos,
        }
    return {
        'viable': True,
        'motivo': 'ok',
        'oferta_vs_demanda': datos,
    } 