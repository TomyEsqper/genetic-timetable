#!/usr/bin/env python3
"""
Validador de reglas duras para el sistema de horarios.
Implementa todas las validaciones que DEBEN cumplirse siempre.
"""

from typing import Dict, List, Tuple, Set, Optional
from collections import defaultdict, Counter
from dataclasses import dataclass
import logging

from horarios.models import (
    Horario, Curso, Materia, Profesor, BloqueHorario,
    DisponibilidadProfesor, MateriaProfesor, MateriaGrado,
    ConfiguracionCurso, MateriaRelleno, ReglaPedagogica
)

logger = logging.getLogger(__name__)

@dataclass
class ViolacionRegla:
    """Representa una violación de regla dura"""
    tipo: str
    descripcion: str
    curso: Optional[str] = None
    profesor: Optional[str] = None
    materia: Optional[str] = None
    dia: Optional[str] = None
    bloque: Optional[int] = None
    gravedad: str = "alta"  # alta, media, baja

@dataclass
class ResultadoValidacion:
    """Resultado de validación de reglas duras"""
    es_valido: bool
    violaciones: List[ViolacionRegla]
    estadisticas: Dict
    tiempo_validacion: float

class ValidadorReglasDuras:
    """
    Validador completo de reglas duras del sistema de horarios.
    Garantiza que todas las restricciones obligatorias se cumplan.
    """
    
    def __init__(self):
        self.violaciones = []
        self.estadisticas = {}
        
    def validar_solucion_completa(self, horarios: List[Dict]) -> ResultadoValidacion:
        """
        Valida una solución completa de horarios contra todas las reglas duras.
        
        Args:
            horarios: Lista de diccionarios con información de horarios
            
        Returns:
            ResultadoValidacion con el resultado completo
        """
        import time
        inicio = time.time()
        
        self.violaciones = []
        self.estadisticas = {}
        
        logger.info(f"Iniciando validación de {len(horarios)} horarios")
        
        # Convertir horarios a estructura más manejable
        horarios_por_curso = self._agrupar_horarios_por_curso(horarios)
        horarios_por_profesor = self._agrupar_horarios_por_profesor(horarios)
        
        # Ejecutar todas las validaciones de reglas duras
        self._validar_unicidad_curso_dia_bloque(horarios_por_curso)
        self._validar_unicidad_profesor_dia_bloque(horarios_por_profesor)
        self._validar_disponibilidad_profesores(horarios)
        self._validar_aptitud_profesores(horarios)
        self._validar_diferencias_materias_obligatorias(horarios_por_curso)
        self._validar_solo_bloques_clase(horarios)
        self._validar_aulas_fijas(horarios_por_curso)
        self._validar_completitud_cursos(horarios_por_curso)
        self._validar_reglas_pedagogicas(horarios_por_curso)
        
        # Calcular estadísticas
        self._calcular_estadisticas(horarios_por_curso, horarios_por_profesor)
        
        tiempo_total = time.time() - inicio
        
        es_valido = len(self.violaciones) == 0
        
        logger.info(f"Validación completada en {tiempo_total:.2f}s - Válido: {es_valido}")
        if not es_valido:
            logger.warning(f"Encontradas {len(self.violaciones)} violaciones")
        
        return ResultadoValidacion(
            es_valido=es_valido,
            violaciones=self.violaciones.copy(),
            estadisticas=self.estadisticas.copy(),
            tiempo_validacion=tiempo_total
        )
    
    def _agrupar_horarios_por_curso(self, horarios: List[Dict]) -> Dict:
        """Agrupa horarios por curso"""
        por_curso = defaultdict(list)
        for h in horarios:
            curso_id = h.get('curso_id') or h.get('curso')
            por_curso[curso_id].append(h)
        return dict(por_curso)
    
    def _agrupar_horarios_por_profesor(self, horarios: List[Dict]) -> Dict:
        """Agrupa horarios por profesor"""
        por_profesor = defaultdict(list)
        for h in horarios:
            profesor_id = h.get('profesor_id') or h.get('profesor')
            por_profesor[profesor_id].append(h)
        return dict(por_profesor)
    
    def _validar_unicidad_curso_dia_bloque(self, horarios_por_curso: Dict):
        """REGLA DURA: (curso, día, bloque) único"""
        for curso_id, horarios in horarios_por_curso.items():
            slots_ocupados = set()
            
            for h in horarios:
                dia = h.get('dia')
                bloque = h.get('bloque')
                slot = (dia, bloque)
                
                if slot in slots_ocupados:
                    self.violaciones.append(ViolacionRegla(
                        tipo="unicidad_curso_slot",
                        descripcion=f"Curso {curso_id} tiene múltiples materias en {dia} bloque {bloque}",
                        curso=str(curso_id),
                        dia=dia,
                        bloque=bloque
                    ))
                else:
                    slots_ocupados.add(slot)
    
    def _validar_unicidad_profesor_dia_bloque(self, horarios_por_profesor: Dict):
        """REGLA DURA: (profesor, día, bloque) único"""
        for profesor_id, horarios in horarios_por_profesor.items():
            slots_ocupados = set()
            
            for h in horarios:
                dia = h.get('dia')
                bloque = h.get('bloque')
                slot = (dia, bloque)
                
                if slot in slots_ocupados:
                    curso1 = next(h2.get('curso') for h2 in horarios if h2.get('dia') == dia and h2.get('bloque') == bloque)
                    self.violaciones.append(ViolacionRegla(
                        tipo="unicidad_profesor_slot",
                        descripcion=f"Profesor {profesor_id} asignado a múltiples cursos en {dia} bloque {bloque}",
                        profesor=str(profesor_id),
                        dia=dia,
                        bloque=bloque
                    ))
                else:
                    slots_ocupados.add(slot)
    
    def _validar_disponibilidad_profesores(self, horarios: List[Dict]):
        """REGLA DURA: DisponibilidadProfesor respetada"""
        for h in horarios:
            profesor_id = h.get('profesor_id') or h.get('profesor')
            dia = h.get('dia')
            bloque = h.get('bloque')
            
            # Verificar disponibilidad
            try:
                if isinstance(profesor_id, int):
                    profesor = Profesor.objects.get(id=profesor_id)
                else:
                    profesor = Profesor.objects.get(nombre=profesor_id)
                
                disponible = DisponibilidadProfesor.objects.filter(
                    profesor=profesor,
                    dia=dia,
                    bloque_inicio__lte=bloque,
                    bloque_fin__gte=bloque
                ).exists()
                
                if not disponible:
                    self.violaciones.append(ViolacionRegla(
                        tipo="disponibilidad_profesor",
                        descripcion=f"Profesor {profesor.nombre} no disponible en {dia} bloque {bloque}",
                        profesor=profesor.nombre,
                        dia=dia,
                        bloque=bloque
                    ))
                    
            except Profesor.DoesNotExist:
                self.violaciones.append(ViolacionRegla(
                    tipo="profesor_inexistente",
                    descripcion=f"Profesor {profesor_id} no existe",
                    profesor=str(profesor_id)
                ))
    
    def _validar_aptitud_profesores(self, horarios: List[Dict]):
        """REGLA DURA: MateriaProfesor válida (incluyendo relleno)"""
        for h in horarios:
            profesor_id = h.get('profesor_id') or h.get('profesor')
            materia_id = h.get('materia_id') or h.get('materia')
            
            try:
                if isinstance(profesor_id, int):
                    profesor = Profesor.objects.get(id=profesor_id)
                else:
                    profesor = Profesor.objects.get(nombre=profesor_id)
                
                if isinstance(materia_id, int):
                    materia = Materia.objects.get(id=materia_id)
                else:
                    materia = Materia.objects.get(nombre=materia_id)
                
                # Verificar aptitud
                es_apto = MateriaProfesor.objects.filter(
                    profesor=profesor,
                    materia=materia
                ).exists()
                
                # Si es materia de relleno, verificar también si puede dictar relleno
                if materia.es_relleno and not es_apto:
                    if not profesor.puede_dictar_relleno:
                        self.violaciones.append(ViolacionRegla(
                            tipo="aptitud_profesor_relleno",
                            descripcion=f"Profesor {profesor.nombre} no puede dictar relleno ({materia.nombre})",
                            profesor=profesor.nombre,
                            materia=materia.nombre
                        ))
                elif not materia.es_relleno and not es_apto:
                    self.violaciones.append(ViolacionRegla(
                        tipo="aptitud_profesor_materia",
                        descripcion=f"Profesor {profesor.nombre} no es apto para {materia.nombre}",
                        profesor=profesor.nombre,
                        materia=materia.nombre
                    ))
                    
            except (Profesor.DoesNotExist, Materia.DoesNotExist) as e:
                self.violaciones.append(ViolacionRegla(
                    tipo="entidad_inexistente",
                    descripcion=f"Error de referencia: {str(e)}",
                    profesor=str(profesor_id),
                    materia=str(materia_id)
                ))
    
    def _validar_diferencias_materias_obligatorias(self, horarios_por_curso: Dict):
        """REGLA DURA: diferencias=0 por (curso, materia) obligatoria"""
        for curso_id, horarios in horarios_por_curso.items():
            try:
                if isinstance(curso_id, int):
                    curso = Curso.objects.get(id=curso_id)
                else:
                    curso = Curso.objects.get(nombre=curso_id)
                
                # Obtener materias obligatorias del curso
                materias_obligatorias = MateriaGrado.objects.filter(
                    grado=curso.grado,
                    materia__es_relleno=False
                )
                
                # Contar bloques asignados por materia
                bloques_asignados = Counter()
                for h in horarios:
                    materia_id = h.get('materia_id') or h.get('materia')
                    try:
                        if isinstance(materia_id, int):
                            materia = Materia.objects.get(id=materia_id)
                        else:
                            materia = Materia.objects.get(nombre=materia_id)
                        
                        if not materia.es_relleno:
                            bloques_asignados[materia.id] += 1
                    except Materia.DoesNotExist:
                        continue
                
                # Verificar diferencias
                for mg in materias_obligatorias:
                    bloques_requeridos = mg.materia.bloques_por_semana
                    bloques_actuales = bloques_asignados.get(mg.materia.id, 0)
                    diferencia = bloques_actuales - bloques_requeridos
                    
                    if diferencia != 0:
                        self.violaciones.append(ViolacionRegla(
                            tipo="diferencia_materia_obligatoria",
                            descripcion=f"Curso {curso.nombre}: {mg.materia.nombre} tiene diferencia {diferencia} (requiere {bloques_requeridos}, tiene {bloques_actuales})",
                            curso=curso.nombre,
                            materia=mg.materia.nombre
                        ))
                        
            except Curso.DoesNotExist:
                self.violaciones.append(ViolacionRegla(
                    tipo="curso_inexistente",
                    descripcion=f"Curso {curso_id} no existe",
                    curso=str(curso_id)
                ))
    
    def _validar_solo_bloques_clase(self, horarios: List[Dict]):
        """REGLA DURA: Solo bloques tipo 'clase'"""
        for h in horarios:
            bloque_num = h.get('bloque')
            
            try:
                bloque_obj = BloqueHorario.objects.filter(numero=bloque_num).first()
                if bloque_obj and bloque_obj.tipo != 'clase':
                    self.violaciones.append(ViolacionRegla(
                        tipo="bloque_no_clase",
                        descripcion=f"Bloque {bloque_num} es tipo '{bloque_obj.tipo}', no 'clase'",
                        bloque=bloque_num
                    ))
            except Exception:
                # Si no existe el bloque, será detectado en otras validaciones
                pass
    
    def _validar_aulas_fijas(self, horarios_por_curso: Dict):
        """REGLA DURA: Aula fija por curso (no mover aulas)"""
        for curso_id, horarios in horarios_por_curso.items():
            try:
                if isinstance(curso_id, int):
                    curso = Curso.objects.get(id=curso_id)
                else:
                    curso = Curso.objects.get(nombre=curso_id)
                
                if curso.aula_fija:
                    # Verificar que todos los horarios usen el aula fija
                    for h in horarios:
                        aula_id = h.get('aula_id') or h.get('aula')
                        if aula_id and aula_id != curso.aula_fija.id:
                            self.violaciones.append(ViolacionRegla(
                                tipo="aula_fija_violada",
                                descripcion=f"Curso {curso.nombre} debe usar aula fija {curso.aula_fija.nombre}",
                                curso=curso.nombre
                            ))
                            
            except Curso.DoesNotExist:
                continue
    
    def _validar_completitud_cursos(self, horarios_por_curso: Dict):
        """REGLA DURA: Cursos 100% llenos (0 huecos)"""
        from .models import ConfiguracionColegio
        
        config_colegio = ConfiguracionColegio.objects.first()
        if config_colegio:
            dias_semana = len(config_colegio.dias_clase.split(','))
            slots_totales = config_colegio.bloques_por_dia * dias_semana
        else:
            slots_totales = 30  # Default
        
        for curso_id, horarios in horarios_por_curso.items():
            bloques_asignados = len(horarios)
            
            try:
                if isinstance(curso_id, int):
                    curso = Curso.objects.get(id=curso_id)
                    curso_nombre = curso.nombre
                else:
                    curso_nombre = str(curso_id)
                
                # Verificar configuración específica del curso
                try:
                    config_curso = ConfiguracionCurso.objects.get(curso__id=curso_id)
                    slots_objetivo = config_curso.slots_objetivo
                except ConfiguracionCurso.DoesNotExist:
                    slots_objetivo = slots_totales
                
                if bloques_asignados != slots_objetivo:
                    self.violaciones.append(ViolacionRegla(
                        tipo="curso_incompleto",
                        descripcion=f"Curso {curso_nombre} tiene {bloques_asignados}/{slots_objetivo} slots (debe estar 100% lleno)",
                        curso=curso_nombre
                    ))
                    
            except Curso.DoesNotExist:
                if bloques_asignados != slots_totales:
                    self.violaciones.append(ViolacionRegla(
                        tipo="curso_incompleto",
                        descripcion=f"Curso {curso_id} tiene {bloques_asignados}/{slots_totales} slots",
                        curso=str(curso_id)
                    ))
    
    def _validar_reglas_pedagogicas(self, horarios_por_curso: Dict):
        """Validar reglas pedagógicas activas"""
        reglas_activas = ReglaPedagogica.objects.filter(activa=True)
        
        for regla in reglas_activas:
            if regla.tipo_regla == 'max_materia_dia':
                self._validar_max_materia_por_dia(horarios_por_curso, regla)
            elif regla.tipo_regla == 'bloques_consecutivos':
                self._validar_bloques_consecutivos(horarios_por_curso, regla)
    
    def _validar_max_materia_por_dia(self, horarios_por_curso: Dict, regla: ReglaPedagogica):
        """Validar máximo de bloques de una materia por día"""
        max_bloques = regla.parametros.get('max_bloques', 2)
        
        for curso_id, horarios in horarios_por_curso.items():
            # Agrupar por día y materia
            por_dia_materia = defaultdict(lambda: defaultdict(int))
            
            for h in horarios:
                dia = h.get('dia')
                materia_id = h.get('materia_id') or h.get('materia')
                por_dia_materia[dia][materia_id] += 1
            
            # Verificar límites
            for dia, materias in por_dia_materia.items():
                for materia_id, count in materias.items():
                    if count > max_bloques:
                        try:
                            if isinstance(materia_id, int):
                                materia = Materia.objects.get(id=materia_id)
                                materia_nombre = materia.nombre
                            else:
                                materia_nombre = str(materia_id)
                        except Materia.DoesNotExist:
                            materia_nombre = str(materia_id)
                        
                        self.violaciones.append(ViolacionRegla(
                            tipo="max_materia_dia_excedido",
                            descripcion=f"Curso {curso_id}: {materia_nombre} tiene {count} bloques en {dia} (máximo {max_bloques})",
                            curso=str(curso_id),
                            materia=materia_nombre,
                            dia=dia,
                            gravedad="media"
                        ))
    
    def _validar_bloques_consecutivos(self, horarios_por_curso: Dict, regla: ReglaPedagogica):
        """Validar bloques consecutivos para materias que lo requieren"""
        materias_doble_bloque = regla.parametros.get('materias_doble_bloque', [])
        
        for curso_id, horarios in horarios_por_curso.items():
            # Agrupar por día y materia
            por_dia_materia = defaultdict(lambda: defaultdict(list))
            
            for h in horarios:
                dia = h.get('dia')
                bloque = h.get('bloque')
                materia_id = h.get('materia_id') or h.get('materia')
                
                try:
                    if isinstance(materia_id, int):
                        materia = Materia.objects.get(id=materia_id)
                        materia_nombre = materia.nombre
                    else:
                        materia_nombre = str(materia_id)
                        materia = Materia.objects.get(nombre=materia_nombre)
                    
                    # Verificar si requiere doble bloque
                    if (materia.requiere_doble_bloque or 
                        materia_nombre in materias_doble_bloque):
                        por_dia_materia[dia][materia_nombre].append(bloque)
                        
                except Materia.DoesNotExist:
                    continue
            
            # Verificar consecutividad
            for dia, materias in por_dia_materia.items():
                for materia_nombre, bloques in materias.items():
                    if len(bloques) >= 2:
                        bloques_ordenados = sorted(bloques)
                        for i in range(len(bloques_ordenados) - 1):
                            if bloques_ordenados[i+1] - bloques_ordenados[i] != 1:
                                self.violaciones.append(ViolacionRegla(
                                    tipo="bloques_no_consecutivos",
                                    descripcion=f"Curso {curso_id}: {materia_nombre} en {dia} no tiene bloques consecutivos",
                                    curso=str(curso_id),
                                    materia=materia_nombre,
                                    dia=dia,
                                    gravedad="media"
                                ))
                                break
    
    def _calcular_estadisticas(self, horarios_por_curso: Dict, horarios_por_profesor: Dict):
        """Calcular estadísticas de la solución"""
        self.estadisticas = {
            'total_cursos': len(horarios_por_curso),
            'total_profesores': len(horarios_por_profesor),
            'total_horarios': sum(len(h) for h in horarios_por_curso.values()),
            'cursos_completos': 0,
            'profesores_activos': len([p for p in horarios_por_profesor.values() if len(p) > 0]),
            'materias_relleno_usadas': 0,
            'violaciones_por_tipo': Counter(v.tipo for v in self.violaciones),
            'violaciones_criticas': len([v for v in self.violaciones if v.gravedad == "alta"])
        }
        
        # Contar cursos completos
        from .models import ConfiguracionColegio
        config_colegio = ConfiguracionColegio.objects.first()
        if config_colegio:
            dias_semana = len(config_colegio.dias_clase.split(','))
            slots_esperados = config_colegio.bloques_por_dia * dias_semana
        else:
            slots_esperados = 30
        
        for curso_id, horarios in horarios_por_curso.items():
            if len(horarios) == slots_esperados:
                self.estadisticas['cursos_completos'] += 1
        
        # Contar materias de relleno usadas
        materias_relleno = set()
        for horarios in horarios_por_curso.values():
            for h in horarios:
                materia_id = h.get('materia_id') or h.get('materia')
                try:
                    if isinstance(materia_id, int):
                        materia = Materia.objects.get(id=materia_id)
                    else:
                        materia = Materia.objects.get(nombre=materia_id)
                    
                    if materia.es_relleno:
                        materias_relleno.add(materia.id)
                except Materia.DoesNotExist:
                    continue
        
        self.estadisticas['materias_relleno_usadas'] = len(materias_relleno) 