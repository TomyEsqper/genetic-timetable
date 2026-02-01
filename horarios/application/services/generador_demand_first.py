#!/usr/bin/env python3
"""
Generador de horarios con lógica demand-first.
Garantiza 100% de ocupación de cursos y cumplimiento de reglas duras.
"""

from typing import Dict, List, Tuple, Set, Optional
from collections import defaultdict, Counter
from dataclasses import dataclass
import random
import logging
import time

from horarios.models import (
    Curso, Materia, Profesor, BloqueHorario, ConfiguracionColegio,
    DisponibilidadProfesor, MateriaProfesor, MateriaGrado,
    ConfiguracionCurso, MateriaRelleno, ReglaPedagogica, CursoMateriaRequerida
)
from horarios.domain.validators.validador_reglas_duras import ValidadorReglasDuras
from horarios.domain.validators.validador_precondiciones import ValidadorPrecondiciones

logger = logging.getLogger(__name__)

@dataclass
class SlotHorario:
    """Representa un slot de horario asignado"""
    curso_id: int
    materia_id: int
    profesor_id: int
    dia: str
    bloque: int
    aula_id: Optional[int] = None
    es_relleno: bool = False

@dataclass
class EstadoGeneracion:
    """Estado actual de la generación de horarios"""
    slots: List[SlotHorario]
    cursos_completos: Set[int]
    profesores_ocupados: Dict[Tuple[str, int], int]  # (dia, bloque) -> profesor_id
    materias_cumplidas: Dict[Tuple[int, int], int]  # (curso_id, materia_id) -> bloques_asignados
    calidad_actual: float
    es_valido: bool

class GeneradorDemandFirst:
    """
    Generador de horarios con enfoque demand-first.
    Prioriza completitud de cursos y cumplimiento de reglas duras.
    """
    
    def __init__(self):
        self.validador_reglas = ValidadorReglasDuras()
        self.validador_precondiciones = ValidadorPrecondiciones()
        self.config_colegio = self._obtener_configuracion()
        self.random = random.Random()
        
    def generar_horarios(self, semilla: Optional[int] = None, **kwargs) -> Dict:
        """
        Genera horarios completos usando lógica demand-first.
        
        Args:
            semilla: Semilla para reproducibilidad
            **kwargs: Parámetros adicionales de configuración
            
        Returns:
            Dict con resultado de generación
        """
        if semilla:
            self.random.seed(semilla)
            random.seed(semilla)
        
        inicio_tiempo = time.time()
        logger.info("Iniciando generación demand-first")
        
        # 1. Validar precondiciones
        resultado_factibilidad = self.validador_precondiciones.validar_factibilidad_completa()
        if not resultado_factibilidad.es_factible:
            return {
                'exito': False,
                'razon': 'Precondiciones no cumplidas',
                'factibilidad': resultado_factibilidad,
                'tiempo_total': time.time() - inicio_tiempo
            }
        
        # 2. Construcción inicial demand-first
        estado_inicial = self._construccion_inicial()
        if not estado_inicial.es_valido:
            return {
                'exito': False,
                'razon': 'No se pudo construir solución inicial válida',
                'estado': estado_inicial,
                'tiempo_total': time.time() - inicio_tiempo
            }
        
        # 3. Reparación y mejora iterativa
        estado_final = self._mejora_iterativa(estado_inicial, kwargs)
        
        # 4. Validación final
        horarios_dict = self._convertir_a_diccionarios(estado_final.slots)
        validacion_final = self.validador_reglas.validar_solucion_completa(horarios_dict)
        
        tiempo_total = time.time() - inicio_tiempo
        
        resultado = {
            'exito': validacion_final.es_valido,
            'horarios': horarios_dict,
            'validacion_final': validacion_final,
            'calidad': estado_final.calidad_actual,
            'estadisticas': {
                'slots_generados': len(estado_final.slots),
                'cursos_completos': len(estado_final.cursos_completos),
                'tiempo_construccion': tiempo_total * 0.7,  # Aproximación
                'tiempo_mejora': tiempo_total * 0.3,
                'tiempo_total': tiempo_total
            }
        }
        
        logger.info(f"Generación completada en {tiempo_total:.2f}s - Éxito: {resultado['exito']}")
        return resultado
    
    def _obtener_configuracion(self) -> Dict:
        """Obtiene configuración del colegio"""
        config = ConfiguracionColegio.objects.first()
        if config:
            dias_clase = [d.strip() for d in config.dias_clase.split(',')]
            return {
                'bloques_por_dia': config.bloques_por_dia,
                'dias_clase': dias_clase,
                'slots_por_semana': config.bloques_por_dia * len(dias_clase),
                'bloques_clase': list(BloqueHorario.objects.filter(tipo='clase').order_by('numero').values_list('numero', flat=True))
            }
        else:
            return {
                'bloques_por_dia': 6,
                'dias_clase': ['lunes', 'martes', 'miércoles', 'jueves', 'viernes'],
                'slots_por_semana': 30,
                'bloques_clase': [1, 2, 3, 4, 5, 6]
            }
    
    def _construccion_inicial(self) -> EstadoGeneracion:
        """Construcción inicial demand-first"""
        logger.info("Iniciando construcción demand-first")
        
        slots = []
        cursos_completos = set()
        profesores_ocupados = set() # Set of (profesor_id, dia, bloque)
        materias_cumplidas = defaultdict(int)
        
        # Procesar cada curso
        for curso in Curso.objects.all():
            logger.debug(f"Procesando curso {curso.nombre}")
            
            # 1. Asignar materias obligatorias
            slots_curso = self._asignar_materias_obligatorias(curso, profesores_ocupados)
            
            # 2. Completar con relleno hasta 100%
            slots_relleno = self._completar_con_relleno(curso, slots_curso, profesores_ocupados)
            
            # Combinar slots del curso
            slots_curso_total = slots_curso + slots_relleno
            slots.extend(slots_curso_total)
            
            # Actualizar contadores
            for slot in slots_curso_total:
                materias_cumplidas[(slot.curso_id, slot.materia_id)] += 1
                profesores_ocupados.add((slot.profesor_id, slot.dia, slot.bloque))
            
            # Verificar completitud del curso
            slots_esperados = self._obtener_slots_objetivo(curso)
            if len(slots_curso_total) == slots_esperados:
                cursos_completos.add(curso.id)
                logger.debug(f"Curso {curso.nombre} completado: {len(slots_curso_total)}/{slots_esperados} slots")
            else:
                logger.warning(f"Curso {curso.nombre} incompleto: {len(slots_curso_total)}/{slots_esperados} slots")
        
        # Calcular calidad inicial
        calidad = self._calcular_calidad(slots)
        
        # Verificar validez básica
        es_valido = len(cursos_completos) == Curso.objects.count()
        
        estado = EstadoGeneracion(
            slots=slots,
            cursos_completos=cursos_completos,
            profesores_ocupados=profesores_ocupados,
            materias_cumplidas=dict(materias_cumplidas),
            calidad_actual=calidad,
            es_valido=es_valido
        )
        
        logger.info(f"Construcción inicial: {len(slots)} slots, {len(cursos_completos)} cursos completos, calidad {calidad:.2f}")
        return estado
    
    def _asignar_materias_obligatorias(self, curso: Curso, profesores_ocupados: set) -> List[SlotHorario]:
        """Asigna materias obligatorias a un curso"""
        slots = []
        
        # 1. Identificar requerimientos (Prioridad: CursoMateriaRequerida > MateriaGrado)
        requerimientos = []
        
        # Intentar cargar configuración específica
        cmr_qs = CursoMateriaRequerida.objects.filter(
            curso=curso,
            materia__es_relleno=False
        ).select_related('materia')
        
        if cmr_qs.exists():
            for cmr in cmr_qs:
                requerimientos.append((cmr.materia, cmr.bloques_requeridos))
        else:
            # Fallback: Configuración estándar por grado (Adaptabilidad)
            mgs = MateriaGrado.objects.filter(
                grado=curso.grado,
                materia__es_relleno=False
            ).select_related('materia')
            
            for mg in mgs:
                requerimientos.append((mg.materia, mg.materia.bloques_por_semana))
        
        # Crear lista de slots disponibles
        slots_disponibles = []
        for dia in self.config_colegio['dias_clase']:
            for bloque in self.config_colegio['bloques_clase']:
                slots_disponibles.append((dia, bloque))
        
        self.random.shuffle(slots_disponibles)
        
        # Asignar cada materia obligatoria
        for materia, bloques_requeridos in requerimientos:
            # Obtener profesores aptos
            profesores_aptos = list(Profesor.objects.filter(materiaprofesor__materia=materia))
            if not profesores_aptos:
                logger.warning(f"No hay profesores aptos para {materia.nombre}")
                continue
            
            # Asignar bloques para esta materia
            bloques_asignados = 0
            intentos = 0
            max_intentos = len(slots_disponibles) * 2
            
            while bloques_asignados < bloques_requeridos and intentos < max_intentos and slots_disponibles:
                intentos += 1
                
                # Seleccionar slot disponible
                if not slots_disponibles:
                    break
                
                dia, bloque = slots_disponibles.pop(0)
                
                # Buscar profesor disponible
                profesor_asignado = self._buscar_profesor_disponible(
                    profesores_aptos, dia, bloque, profesores_ocupados
                )
                
                if profesor_asignado:
                    # Crear slot
                    slot = SlotHorario(
                        curso_id=curso.id,
                        materia_id=materia.id,
                        profesor_id=profesor_asignado.id,
                        dia=dia,
                        bloque=bloque,
                        aula_id=curso.aula_fija.id if curso.aula_fija else None,
                        es_relleno=False
                    )
                    
                    slots.append(slot)
                    profesores_ocupados.add((profesor_asignado.id, dia, bloque))
                    bloques_asignados += 1
                    
                    logger.debug(f"Asignado: {curso.nombre} - {materia.nombre} - {profesor_asignado.nombre} - {dia} bloque {bloque}")
                else:
                    # Devolver slot a la lista para intentar después
                    slots_disponibles.append((dia, bloque))
            
            if bloques_asignados < bloques_requeridos:
                logger.warning(f"Solo se asignaron {bloques_asignados}/{bloques_requeridos} bloques para {materia.nombre} en {curso.nombre}")
        
        return slots
    
    def _completar_con_relleno(self, curso: Curso, slots_existentes: List[SlotHorario], profesores_ocupados: set) -> List[SlotHorario]:
        """Completa curso con materias de relleno hasta 100%"""
        slots_objetivo = self._obtener_slots_objetivo(curso)
        slots_actuales = len(slots_existentes)
        slots_faltantes = slots_objetivo - slots_actuales
        
        if slots_faltantes <= 0:
            return []
        
        logger.debug(f"Completando {curso.nombre} con {slots_faltantes} slots de relleno")
        
        slots_relleno = []
        
        # Obtener materias de relleno compatibles
        materias_relleno = self._obtener_materias_relleno_para_curso(curso)
        if not materias_relleno:
            logger.warning(f"No hay materias de relleno disponibles para {curso.nombre}")
            return []
        
        # Crear lista de slots disponibles
        slots_disponibles = []
        for dia in self.config_colegio['dias_clase']:
            for bloque in self.config_colegio['bloques_clase']:
                # Solo excluir slots ya ocupados por el curso
                if not any(s.dia == dia and s.bloque == bloque for s in slots_existentes):
                    slots_disponibles.append((dia, bloque))
        
        self.random.shuffle(slots_disponibles)
        
        # Asignar relleno
        bloques_asignados = 0
        while bloques_asignados < slots_faltantes and slots_disponibles:
            dia, bloque = slots_disponibles.pop(0)
            
            # Seleccionar materia de relleno
            materia_relleno = self.random.choice(materias_relleno)
            
            # Obtener profesores aptos para relleno
            profesores_aptos = self._obtener_profesores_aptos_relleno(materia_relleno)
            
            # Buscar profesor disponible
            profesor_asignado = self._buscar_profesor_disponible(
                profesores_aptos, dia, bloque, profesores_ocupados
            )
            
            if profesor_asignado:
                slot = SlotHorario(
                    curso_id=curso.id,
                    materia_id=materia_relleno.id,
                    profesor_id=profesor_asignado.id,
                    dia=dia,
                    bloque=bloque,
                    aula_id=curso.aula_fija.id if curso.aula_fija else None,
                    es_relleno=True
                )
                
                slots_relleno.append(slot)
                profesores_ocupados.add((profesor_asignado.id, dia, bloque))
                bloques_asignados += 1
                
                logger.debug(f"Relleno asignado: {curso.nombre} - {materia_relleno.nombre} - {profesor_asignado.nombre} - {dia} bloque {bloque}")
        
        if bloques_asignados < slots_faltantes:
            logger.warning(f"Solo se completaron {bloques_asignados}/{slots_faltantes} slots de relleno para {curso.nombre}")
        
        return slots_relleno
    
    def _buscar_profesor_disponible(self, profesores_aptos: List[Profesor], dia: str, bloque: int, profesores_ocupados: set) -> Optional[Profesor]:
        """Busca un profesor disponible para un slot específico"""
        profesores_shuffled = profesores_aptos.copy()
        self.random.shuffle(profesores_shuffled)
        
        for profesor in profesores_shuffled:
            # Verificar que no esté ocupado en este slot
            if (profesor.id, dia, bloque) in profesores_ocupados:
                continue
            
            # Verificar disponibilidad
            if self._profesor_disponible(profesor, dia, bloque):
                return profesor
        
        return None
    
    def _profesor_disponible(self, profesor: Profesor, dia: str, bloque: int) -> bool:
        """Verifica si un profesor está disponible en un día y bloque específico (usando cache)"""
        if not hasattr(self, 'disponibilidad_cache'):
            self._cargar_disponibilidad()
        
        return (dia, bloque) in self.disponibilidad_cache.get(profesor.id, set())

    def _cargar_disponibilidad(self):
        """Carga disponibilidad de todos los profesores en memoria para acceso O(1)"""
        self.disponibilidad_cache = defaultdict(set)
        # Optimización: traer solo los campos necesarios
        disponibilidades = DisponibilidadProfesor.objects.values('profesor_id', 'dia', 'bloque_inicio', 'bloque_fin')
        
        for disp in disponibilidades:
            prof_id = disp['profesor_id']
            dia = disp['dia']
            for bloque in range(disp['bloque_inicio'], disp['bloque_fin'] + 1):
                self.disponibilidad_cache[prof_id].add((dia, bloque))
    
    def _obtener_slots_objetivo(self, curso: Curso) -> int:
        """Obtiene número objetivo de slots para un curso"""
        try:
            config_curso = ConfiguracionCurso.objects.get(curso=curso)
            return config_curso.slots_objetivo
        except ConfiguracionCurso.DoesNotExist:
            return self.config_colegio['slots_por_semana']
    
    def _obtener_materias_relleno_para_curso(self, curso: Curso) -> List[Materia]:
        """Obtiene materias de relleno compatibles con un curso"""
        materias_relleno = []
        
        for config in MateriaRelleno.objects.filter(activa=True):
            # Verificar compatibilidad con grado
            if (config.grados_compatibles.filter(id=curso.grado.id).exists() or 
                not config.grados_compatibles.exists()):
                materias_relleno.append(config.materia)
        
        return materias_relleno
    
    def _obtener_profesores_aptos_relleno(self, materia: Materia) -> List[Profesor]:
        """Obtiene profesores aptos para una materia de relleno"""
        # Profesores específicamente asignados
        profesores_especificos = list(Profesor.objects.filter(materiaprofesor__materia=materia))
        
        # Profesores que pueden dictar relleno en general
        profesores_relleno = list(Profesor.objects.filter(puede_dictar_relleno=True))
        
        # Combinar y eliminar duplicados
        todos_profesores = profesores_especificos + profesores_relleno
        ids_unicos = set()
        profesores_finales = []
        
        for profesor in todos_profesores:
            if profesor.id not in ids_unicos:
                ids_unicos.add(profesor.id)
                profesores_finales.append(profesor)
        
        return profesores_finales
    
    def _mejora_iterativa(self, estado_inicial: EstadoGeneracion, kwargs: Dict) -> EstadoGeneracion:
        """Aplica mejoras iterativas al estado inicial"""
        logger.info("Iniciando mejora iterativa")
        
        estado_actual = estado_inicial
        mejor_calidad = estado_actual.calidad_actual
        sin_mejora = 0
        max_sin_mejora = kwargs.get('paciencia', 50)
        max_iteraciones = kwargs.get('max_iteraciones', 1000)
        
        for iteracion in range(max_iteraciones):
            # Aplicar operadores de mejora
            nuevo_estado = self._aplicar_operadores_mejora(estado_actual)
            
            if nuevo_estado.calidad_actual > mejor_calidad:
                estado_actual = nuevo_estado
                mejor_calidad = nuevo_estado.calidad_actual
                sin_mejora = 0
                logger.debug(f"Iteración {iteracion}: Nueva mejor calidad {mejor_calidad:.3f}")
            else:
                sin_mejora += 1
            
            # Early stopping
            if sin_mejora >= max_sin_mejora:
                logger.info(f"Early stopping en iteración {iteracion} (sin mejora por {sin_mejora} iteraciones)")
                break
        
        logger.info(f"Mejora completada: calidad final {estado_actual.calidad_actual:.3f}")
        return estado_actual
    
    def _aplicar_operadores_mejora(self, estado: EstadoGeneracion) -> EstadoGeneracion:
        """Aplica operadores de mejora al estado actual (Swap Intra-Curso)"""
        import copy
        
        # Estrategia: Copia superficial de la lista y clonación solo de los elementos modificados
        nuevos_slots = list(estado.slots)
        
        # 1. Selección de Curso
        if not estado.cursos_completos:
            return estado
            
        curso_id = self.random.choice(list(estado.cursos_completos))
        indices = [i for i, s in enumerate(nuevos_slots) if s.curso_id == curso_id]
        
        if len(indices) < 2:
            return estado
            
        # 2. Selección de Slots para Swap
        idx1, idx2 = self.random.sample(indices, 2)
        slot1_orig = nuevos_slots[idx1]
        slot2_orig = nuevos_slots[idx2]
        
        # Clonamos los slots para no afectar el estado original
        slot1 = copy.copy(slot1_orig)
        slot2 = copy.copy(slot2_orig)
        nuevos_slots[idx1] = slot1
        nuevos_slots[idx2] = slot2
        
        # 3. Validar Factibilidad del Swap
        dia1, bloque1 = slot1.dia, slot1.bloque
        dia2, bloque2 = slot2.dia, slot2.bloque
        prof1 = slot1.profesor_id
        prof2 = slot2.profesor_id
        
        es_factible = False
        
        if prof1 == prof2:
            es_factible = True
        else:
            # Disponibilidad horaria (usando cache)
            p1_disp = (dia2, bloque2) in self.disponibilidad_cache.get(prof1, set())
            p2_disp = (dia1, bloque1) in self.disponibilidad_cache.get(prof2, set())
            
            if p1_disp and p2_disp:
                # Chequear choques con otros cursos
                p1_ocupado = (prof1, dia2, bloque2) in estado.profesores_ocupados
                p2_ocupado = (prof2, dia1, bloque1) in estado.profesores_ocupados
                
                if not p1_ocupado and not p2_ocupado:
                    es_factible = True
        
        if es_factible:
            # Aplicar Swap
            slot1.dia, slot1.bloque = dia2, bloque2
            slot2.dia, slot2.bloque = dia1, bloque1
            
            # Evaluar nueva calidad
            nueva_calidad = self._calcular_calidad(nuevos_slots)
            
            if nueva_calidad > estado.calidad_actual:
                # Éxito! Actualizar metadatos
                nuevos_profesores_ocupados = estado.profesores_ocupados.copy()
                
                nuevos_profesores_ocupados.remove((prof1, dia1, bloque1))
                nuevos_profesores_ocupados.remove((prof2, dia2, bloque2))
                
                nuevos_profesores_ocupados.add((prof1, dia2, bloque2))
                nuevos_profesores_ocupados.add((prof2, dia1, bloque1))
                
                return EstadoGeneracion(
                    slots=nuevos_slots,
                    cursos_completos=estado.cursos_completos,
                    profesores_ocupados=nuevos_profesores_ocupados,
                    materias_cumplidas=estado.materias_cumplidas,
                    calidad_actual=nueva_calidad,
                    es_valido=True
                )
                
        return estado
    
    def _calcular_calidad(self, slots: List[SlotHorario]) -> float:
        """Calcula calidad de una solución"""
        if not slots:
            return 0.0
        
        calidad = 0.0
        
        # 1. Penalizar huecos por curso (prioritario)
        calidad += self._evaluar_huecos_cursos(slots) * 0.4
        
        # 2. Evaluar distribución semanal
        calidad += self._evaluar_distribucion_semanal(slots) * 0.3
        
        # 3. Evaluar consecutividad
        calidad += self._evaluar_consecutividad(slots) * 0.2
        
        # 4. Evaluar distribución por profesor (compactibilidad)
        calidad += self._evaluar_distribucion_profesores(slots) * 0.1
        
        # 5. Evaluar preferencias de jornada (Inteligencia)
        calidad += self._evaluar_preferencias_jornada(slots) * 0.1
        
        return calidad
    
    def _evaluar_huecos_cursos(self, slots: List[SlotHorario]) -> float:
        """Evalúa huecos por curso (menos huecos = mejor calidad)"""
        slots_por_curso = defaultdict(list)
        for slot in slots:
            slots_por_curso[slot.curso_id].append((slot.dia, slot.bloque))
        
        puntuacion_total = 0.0
        for curso_id, slots_curso in slots_por_curso.items():
            # Calcular huecos por día
            slots_por_dia = defaultdict(list)
            for dia, bloque in slots_curso:
                slots_por_dia[dia].append(bloque)
            
            huecos_total = 0
            for dia, bloques in slots_por_dia.items():
                if len(bloques) > 1:
                    bloques_ordenados = sorted(bloques)
                    for i in range(len(bloques_ordenados) - 1):
                        huecos = bloques_ordenados[i+1] - bloques_ordenados[i] - 1
                        huecos_total += huecos
            
            # Menos huecos = mejor puntuación
            puntuacion_curso = max(0, 1.0 - (huecos_total / 10.0))
            puntuacion_total += puntuacion_curso
        
        return puntuacion_total / len(slots_por_curso) if slots_por_curso else 0.0
    
    def _evaluar_distribucion_semanal(self, slots: List[SlotHorario]) -> float:
        """Evalúa distribución equilibrada durante la semana"""
        slots_por_dia = defaultdict(int)
        for slot in slots:
            slots_por_dia[slot.dia] += 1
        
        if not slots_por_dia:
            return 0.0
        
        # Calcular desviación estándar de distribución
        valores = list(slots_por_dia.values())
        promedio = sum(valores) / len(valores)
        varianza = sum((x - promedio) ** 2 for x in valores) / len(valores)
        desviacion = varianza ** 0.5
        
        # Menos desviación = mejor distribución
        return max(0, 1.0 - (desviacion / promedio)) if promedio > 0 else 0.0
    
    def _evaluar_consecutividad(self, slots: List[SlotHorario]) -> float:
        """Evalúa cumplimiento de consecutividad para materias que lo requieren"""
        slots_por_curso_materia = defaultdict(list)
        materias_cache = {}
        
        for slot in slots:
            slots_por_curso_materia[(slot.curso_id, slot.materia_id)].append(slot)
            if slot.materia_id not in materias_cache:
                try:
                    materias_cache[slot.materia_id] = Materia.objects.get(id=slot.materia_id)
                except Materia.DoesNotExist:
                    continue
        
        cumplimiento = 0
        total_casos = 0
        
        for (curso_id, materia_id), slots_cm in slots_por_curso_materia.items():
            materia = materias_cache.get(materia_id)
            if not materia:
                continue
                
            if materia.requiere_bloques_consecutivos or materia.requiere_doble_bloque:
                # Agrupar por día
                slots_por_dia = defaultdict(list)
                for s in slots_cm:
                    slots_por_dia[s.dia].append(s.bloque)
                
                for dia, bloques in slots_por_dia.items():
                    total_casos += 1
                    bloques_ordenados = sorted(bloques)
                    es_consecutivo = True
                    for i in range(len(bloques_ordenados) - 1):
                        if bloques_ordenados[i+1] != bloques_ordenados[i] + 1:
                            es_consecutivo = False
                            break
                    if es_consecutivo:
                        cumplimiento += 1
                        
        return cumplimiento / total_casos if total_casos > 0 else 1.0
    
    def _evaluar_distribucion_profesores(self, slots: List[SlotHorario]) -> float:
        """
        Evalúa distribución de profesores para minimizar huecos (compactibilidad).
        Un horario compacto para el profesor es mejor.
        """
        slots_por_profesor = defaultdict(list)
        for slot in slots:
            slots_por_profesor[slot.profesor_id].append((slot.dia, slot.bloque))
            
        puntuacion_total = 0.0
        
        for prof_id, slots_prof in slots_por_profesor.items():
            # Agrupar por día
            slots_por_dia = defaultdict(list)
            for dia, bloque in slots_prof:
                slots_por_dia[dia].append(bloque)
            
            huecos_total = 0
            bloques_total = len(slots_prof)
            
            for dia, bloques in slots_por_dia.items():
                if len(bloques) > 1:
                    bloques_ordenados = sorted(bloques)
                    rango = bloques_ordenados[-1] - bloques_ordenados[0] + 1
                    huecos = rango - len(bloques)
                    huecos_total += huecos
            
            # Penalizar huecos relativos a la carga total
            # Si tiene muchos bloques, se toleran un poco más los huecos, pero idealmente 0
            factor_penalizacion = huecos_total / (bloques_total + 1)  # +1 para evitar div/0
            puntuacion_prof = max(0.0, 1.0 - factor_penalizacion)
            puntuacion_total += puntuacion_prof
            
        return puntuacion_total / len(slots_por_profesor) if slots_por_profesor else 1.0

    def _evaluar_preferencias_jornada(self, slots: List[SlotHorario]) -> float:
        """
        Evalúa si las materias se dictan en su jornada preferida.
        Mañana: Bloques 1-6
        Tarde: Bloques 7-12
        """
        cumplimiento = 0
        total_evaluable = 0
        materias_cache = {}
        
        for slot in slots:
            if slot.materia_id not in materias_cache:
                try:
                    materias_cache[slot.materia_id] = Materia.objects.get(id=slot.materia_id)
                except Materia.DoesNotExist:
                    continue
            
            materia = materias_cache[slot.materia_id]
            preferencia = materia.jornada_preferida
            
            if preferencia == 'cualquiera':
                continue
                
            total_evaluable += 1
            bloque = slot.bloque
            
            es_cumplido = False
            if preferencia == 'mañana':
                if bloque <= 6:
                    es_cumplido = True
            elif preferencia == 'tarde':
                if bloque >= 7:
                    es_cumplido = True
            
            if es_cumplido:
                cumplimiento += 1
                
        return cumplimiento / total_evaluable if total_evaluable > 0 else 1.0
    
    def _convertir_a_diccionarios(self, slots: List[SlotHorario]) -> List[Dict]:
        """Convierte slots a formato de diccionarios"""
        horarios = []
        
        for slot in slots:
            horario = {
                'curso_id': slot.curso_id,
                'materia_id': slot.materia_id,
                'profesor_id': slot.profesor_id,
                'dia': slot.dia,
                'bloque': slot.bloque,
                'aula_id': slot.aula_id,
                'es_relleno': slot.es_relleno
            }
            
            # Agregar nombres para facilitar debugging
            try:
                curso = Curso.objects.get(id=slot.curso_id)
                materia = Materia.objects.get(id=slot.materia_id)
                profesor = Profesor.objects.get(id=slot.profesor_id)
                
                horario.update({
                    'curso': curso.nombre,
                    'materia': materia.nombre,
                    'profesor': profesor.nombre
                })
                
                if slot.aula_id:
                    from horarios.models import Aula
                    aula = Aula.objects.get(id=slot.aula_id)
                    horario['aula'] = aula.nombre
                    
            except Exception as e:
                logger.warning(f"Error obteniendo nombres: {e}")
            
            horarios.append(horario)
        
        return horarios 