#!/usr/bin/env python3
"""
Generador corregido con lógica demand-first que garantiza:
1. bloques_por_semana exactos para materias obligatorias (REGLA DURA)
2. Cursos 100% llenos con relleno
3. Compatibilidades realistas sin sobreasignación de profesores
"""

from typing import Dict, List, Tuple, Set, Optional
from collections import defaultdict, Counter
from dataclasses import dataclass
import random
import logging
import time

from .models import (
    Curso, Materia, Profesor, BloqueHorario, ConfiguracionColegio,
    DisponibilidadProfesor, MateriaProfesor, MateriaGrado,
    ConfiguracionCurso, MateriaRelleno
)

logger = logging.getLogger(__name__)

@dataclass
class SlotAsignacion:
    """Representa una asignación específica de slot"""
    curso_id: int
    materia_id: int
    profesor_id: int
    dia: str
    bloque: int
    aula_id: Optional[int] = None
    es_relleno: bool = False

@dataclass
class EstadoConstruccion:
    """Estado durante la construcción demand-first"""
    asignaciones: List[SlotAsignacion]
    slots_ocupados_curso: Dict[Tuple[int, str, int], bool]  # (curso_id, dia, bloque) -> ocupado
    slots_ocupados_profesor: Dict[Tuple[int, str, int], bool]  # (profesor_id, dia, bloque) -> ocupado
    bloques_asignados_materia: Dict[Tuple[int, int], int]  # (curso_id, materia_id) -> count
    es_valido: bool = True
    errores: List[str] = None

    def __post_init__(self):
        if self.errores is None:
            self.errores = []

class GeneradorCorregido:
    """
    Generador corregido que implementa correctamente demand-first:
    1. Garantiza bloques_por_semana exactos (REGLA DURA)
    2. Completa cursos al 100% con relleno
    3. Respeta compatibilidades realistas
    """
    
    def __init__(self):
        self.config_colegio = self._obtener_configuracion()
        self.random = random.Random()
        
    def generar_horarios_completos(self, semilla: Optional[int] = None) -> Dict:
        """
        Genera horarios completos garantizando todas las reglas duras.
        
        Returns:
            Dict con resultado de generación
        """
        if semilla:
            self.random.seed(semilla)
            random.seed(semilla)
        
        inicio_tiempo = time.time()
        logger.info("🚀 Iniciando generación corregida demand-first")
        
        try:
            # 1. Validar precondiciones críticas
            if not self._validar_precondiciones_criticas():
                return {
                    'exito': False,
                    'razon': 'Precondiciones críticas no cumplidas',
                    'tiempo_total': time.time() - inicio_tiempo
                }
            
            # 2. Construcción demand-first con reglas duras
            estado = self._construccion_demand_first()
            
            if not estado.es_valido:
                return {
                    'exito': False,
                    'razon': 'No se pudo construir solución válida',
                    'errores': estado.errores,
                    'tiempo_total': time.time() - inicio_tiempo
                }
            
            # 3. Validar resultado final
            horarios_dict = self._convertir_a_diccionarios(estado.asignaciones)
            
            # 4. Verificar reglas duras
            if not self._verificar_reglas_duras_finales(estado):
                return {
                    'exito': False,
                    'razon': 'Solución generada viola reglas duras',
                    'tiempo_total': time.time() - inicio_tiempo
                }
            
            tiempo_total = time.time() - inicio_tiempo
            
            logger.info(f"✅ Generación exitosa en {tiempo_total:.2f}s")
            
            return {
                'exito': True,
                'horarios': horarios_dict,
                'estadisticas': {
                    'total_asignaciones': len(estado.asignaciones),
                    'cursos_completos': self._contar_cursos_completos(estado),
                    'materias_cumplidas': self._contar_materias_cumplidas(estado),
                    'tiempo_total': tiempo_total
                }
            }
            
        except Exception as e:
            logger.exception("Error durante la generación")
            return {
                'exito': False,
                'razon': f'Error interno: {str(e)}',
                'tiempo_total': time.time() - inicio_tiempo
            }
    
    def _validar_precondiciones_criticas(self) -> bool:
        """Valida precondiciones mínimas para poder generar"""
        
        # Verificar que hay cursos
        if not Curso.objects.exists():
            logger.error("No hay cursos configurados")
            return False
        
        # Verificar que hay profesores
        if not Profesor.objects.exists():
            logger.error("No hay profesores configurados")
            return False
        
        # Verificar que hay materias obligatorias
        materias_obligatorias = MateriaGrado.objects.filter(materia__es_relleno=False)
        if not materias_obligatorias.exists():
            logger.error("No hay materias obligatorias configuradas")
            return False
        
        # Verificar que hay materias de relleno
        materias_relleno = Materia.objects.filter(es_relleno=True)
        if not materias_relleno.exists():
            logger.warning("No hay materias de relleno configuradas")
        
        # Verificar oferta vs demanda básica
        for curso in Curso.objects.all():
            materias_curso = MateriaGrado.objects.filter(
                grado=curso.grado,
                materia__es_relleno=False
            )
            
            for mg in materias_curso:
                profesores_aptos = MateriaProfesor.objects.filter(materia=mg.materia)
                if not profesores_aptos.exists():
                    logger.error(f"Materia {mg.materia.nombre} no tiene profesores aptos")
                    return False
        
        return True
    
    def _construccion_demand_first(self) -> EstadoConstruccion:
        """Construcción demand-first con reglas duras garantizadas"""
        
        estado = EstadoConstruccion(
            asignaciones=[],
            slots_ocupados_curso={},
            slots_ocupados_profesor={},
            bloques_asignados_materia={}
        )
        
        logger.info("📚 Fase 1: Asignando materias obligatorias")
        
        # FASE 1: Asignar materias obligatorias con bloques_por_semana exactos
        for curso in Curso.objects.all():
            if not self._asignar_materias_obligatorias_curso(curso, estado):
                estado.es_valido = False
                estado.errores.append(f"No se pudieron asignar materias obligatorias para {curso.nombre}")
                return estado
        
        logger.info("🔧 Fase 2: Completando con relleno hasta 100%")
        
        # FASE 2: Completar cada curso al 100% con relleno
        for curso in Curso.objects.all():
            if not self._completar_curso_con_relleno(curso, estado):
                estado.es_valido = False
                estado.errores.append(f"No se pudo completar {curso.nombre} al 100%")
                return estado
        
        logger.info(f"✅ Construcción completada: {len(estado.asignaciones)} asignaciones")
        return estado
    
    def _asignar_materias_obligatorias_curso(self, curso: Curso, estado: EstadoConstruccion) -> bool:
        """Asigna materias obligatorias de un curso garantizando bloques_por_semana exactos"""
        
        materias_obligatorias = MateriaGrado.objects.filter(
            grado=curso.grado,
            materia__es_relleno=False
        ).select_related('materia')
        
        logger.debug(f"Asignando {materias_obligatorias.count()} materias obligatorias para {curso.nombre}")
        
        # Crear pool de slots disponibles para este curso
        slots_disponibles = []
        for dia in self.config_colegio['dias_clase']:
            for bloque in self.config_colegio['bloques_clase']:
                if (curso.id, dia, bloque) not in estado.slots_ocupados_curso:
                    slots_disponibles.append((dia, bloque))
        
        self.random.shuffle(slots_disponibles)
        
        # Asignar cada materia obligatoria
        for mg in materias_obligatorias:
            materia = mg.materia
            bloques_requeridos = materia.bloques_por_semana
            bloques_asignados = 0
            
            logger.debug(f"  Asignando {materia.nombre}: {bloques_requeridos} bloques")
            
            # Obtener profesores aptos para esta materia
            profesores_aptos = list(Profesor.objects.filter(
                materiaprofesor__materia=materia
            ).distinct())
            
            if not profesores_aptos:
                logger.error(f"No hay profesores aptos para {materia.nombre}")
                return False
            
            # Asignar bloques uno por uno
            intentos = 0
            max_intentos = len(slots_disponibles) * 2
            
            while bloques_asignados < bloques_requeridos and intentos < max_intentos:
                intentos += 1
                
                if not slots_disponibles:
                    logger.error(f"No hay más slots disponibles para {materia.nombre} en {curso.nombre}")
                    return False
                
                # Tomar siguiente slot disponible
                dia, bloque = slots_disponibles.pop(0)
                
                # Buscar profesor disponible
                profesor_asignado = self._buscar_profesor_disponible(
                    profesores_aptos, dia, bloque, estado
                )
                
                if profesor_asignado:
                    # Crear asignación
                    asignacion = SlotAsignacion(
                        curso_id=curso.id,
                        materia_id=materia.id,
                        profesor_id=profesor_asignado.id,
                        dia=dia,
                        bloque=bloque,
                        aula_id=curso.aula_fija.id if curso.aula_fija else None,
                        es_relleno=False
                    )
                    
                    # Registrar asignación
                    self._registrar_asignacion(asignacion, estado)
                    bloques_asignados += 1
                    
                    logger.debug(f"    ✅ {materia.nombre} - {profesor_asignado.nombre} - {dia} bloque {bloque}")
                else:
                    # Devolver slot a la lista para intentar después
                    slots_disponibles.append((dia, bloque))
            
            # Verificar que se cumplió la carga exacta (REGLA DURA)
            if bloques_asignados != bloques_requeridos:
                logger.error(f"❌ {materia.nombre} en {curso.nombre}: asignados {bloques_asignados}/{bloques_requeridos}")
                return False
            
            logger.debug(f"    ✅ {materia.nombre} completada: {bloques_asignados}/{bloques_requeridos}")
        
        return True
    
    def _completar_curso_con_relleno(self, curso: Curso, estado: EstadoConstruccion) -> bool:
        """Completa un curso al 100% con materias de relleno"""
        
        slots_objetivo = self._obtener_slots_objetivo(curso)
        slots_actuales = len([a for a in estado.asignaciones if a.curso_id == curso.id])
        slots_faltantes = slots_objetivo - slots_actuales
        
        if slots_faltantes <= 0:
            logger.debug(f"Curso {curso.nombre} ya completo: {slots_actuales}/{slots_objetivo}")
            return True
        
        logger.debug(f"Completando {curso.nombre}: faltan {slots_faltantes} slots")
        
        # Obtener materias de relleno disponibles
        materias_relleno = self._obtener_materias_relleno_para_curso(curso)
        if not materias_relleno:
            logger.error(f"No hay materias de relleno disponibles para {curso.nombre}")
            return False
        
        # Obtener slots disponibles para este curso
        slots_disponibles = []
        for dia in self.config_colegio['dias_clase']:
            for bloque in self.config_colegio['bloques_clase']:
                if (curso.id, dia, bloque) not in estado.slots_ocupados_curso:
                    slots_disponibles.append((dia, bloque))
        
        if len(slots_disponibles) < slots_faltantes:
            logger.error(f"No hay suficientes slots disponibles para completar {curso.nombre}")
            return False
        
        self.random.shuffle(slots_disponibles)
        
        # Asignar relleno
        bloques_asignados = 0
        for dia, bloque in slots_disponibles:
            if bloques_asignados >= slots_faltantes:
                break
            
            # Seleccionar materia de relleno
            materia_relleno = self.random.choice(materias_relleno)
            
            # Obtener profesores aptos para relleno
            profesores_aptos = self._obtener_profesores_aptos_relleno(materia_relleno)
            
            # Buscar profesor disponible
            profesor_asignado = self._buscar_profesor_disponible(
                profesores_aptos, dia, bloque, estado
            )
            
            if profesor_asignado:
                asignacion = SlotAsignacion(
                    curso_id=curso.id,
                    materia_id=materia_relleno.id,
                    profesor_id=profesor_asignado.id,
                    dia=dia,
                    bloque=bloque,
                    aula_id=curso.aula_fija.id if curso.aula_fija else None,
                    es_relleno=True
                )
                
                self._registrar_asignacion(asignacion, estado)
                bloques_asignados += 1
                
                logger.debug(f"    🔧 Relleno: {materia_relleno.nombre} - {profesor_asignado.nombre} - {dia} bloque {bloque}")
        
        # Verificar que se completó al 100% (REGLA DURA)
        slots_finales = len([a for a in estado.asignaciones if a.curso_id == curso.id])
        if slots_finales != slots_objetivo:
            logger.error(f"❌ {curso.nombre} no completado: {slots_finales}/{slots_objetivo}")
            return False
        
        logger.debug(f"✅ {curso.nombre} completado al 100%: {slots_finales}/{slots_objetivo}")
        return True
    
    def _buscar_profesor_disponible(self, profesores_aptos: List[Profesor], 
                                   dia: str, bloque: int, estado: EstadoConstruccion) -> Optional[Profesor]:
        """Busca un profesor disponible para un slot específico"""
        
        profesores_shuffled = profesores_aptos.copy()
        self.random.shuffle(profesores_shuffled)
        
        for profesor in profesores_shuffled:
            # Verificar que no esté ocupado en este slot
            if (profesor.id, dia, bloque) in estado.slots_ocupados_profesor:
                continue
            
            # Verificar disponibilidad en BD
            if not self._profesor_disponible(profesor, dia, bloque):
                continue
            
            # Verificar que no exceda su carga máxima semanal
            carga_actual = len([a for a in estado.asignaciones if a.profesor_id == profesor.id])
            if carga_actual >= profesor.max_bloques_por_semana:
                continue
            
            return profesor
        
        return None
    
    def _profesor_disponible(self, profesor: Profesor, dia: str, bloque: int) -> bool:
        """Verifica disponibilidad de profesor en BD"""
        return DisponibilidadProfesor.objects.filter(
            profesor=profesor,
            dia=dia,
            bloque_inicio__lte=bloque,
            bloque_fin__gte=bloque
        ).exists()
    
    def _registrar_asignacion(self, asignacion: SlotAsignacion, estado: EstadoConstruccion):
        """Registra una asignación en el estado"""
        estado.asignaciones.append(asignacion)
        
        # Marcar slots ocupados
        estado.slots_ocupados_curso[(asignacion.curso_id, asignacion.dia, asignacion.bloque)] = True
        estado.slots_ocupados_profesor[(asignacion.profesor_id, asignacion.dia, asignacion.bloque)] = True
        
        # Actualizar contadores de materias
        key = (asignacion.curso_id, asignacion.materia_id)
        estado.bloques_asignados_materia[key] = estado.bloques_asignados_materia.get(key, 0) + 1
    
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
        # Profesores específicamente asignados a esta materia
        profesores_especificos = list(Profesor.objects.filter(
            materiaprofesor__materia=materia
        ))
        
        # Si no hay específicos, usar profesores que pueden dictar relleno en general
        if not profesores_especificos:
            profesores_especificos = list(Profesor.objects.filter(
                puede_dictar_relleno=True
            ))
        
        return profesores_especificos
    
    def _verificar_reglas_duras_finales(self, estado: EstadoConstruccion) -> bool:
        """Verifica que se cumplan todas las reglas duras"""
        
        # 1. Verificar que cada materia obligatoria cumple bloques_por_semana exactos
        for curso in Curso.objects.all():
            materias_obligatorias = MateriaGrado.objects.filter(
                grado=curso.grado,
                materia__es_relleno=False
            )
            
            for mg in materias_obligatorias:
                key = (curso.id, mg.materia.id)
                bloques_asignados = estado.bloques_asignados_materia.get(key, 0)
                bloques_requeridos = mg.materia.bloques_por_semana
                
                if bloques_asignados != bloques_requeridos:
                    logger.error(f"❌ REGLA DURA VIOLADA: {curso.nombre} - {mg.materia.nombre}: {bloques_asignados}/{bloques_requeridos}")
                    return False
        
        # 2. Verificar que cada curso está 100% lleno
        for curso in Curso.objects.all():
            slots_objetivo = self._obtener_slots_objetivo(curso)
            slots_asignados = len([a for a in estado.asignaciones if a.curso_id == curso.id])
            
            if slots_asignados != slots_objetivo:
                logger.error(f"❌ REGLA DURA VIOLADA: {curso.nombre} no está 100% lleno: {slots_asignados}/{slots_objetivo}")
                return False
        
        # 3. Verificar que no hay choques de profesores
        slots_profesor = set()
        for asignacion in estado.asignaciones:
            key = (asignacion.profesor_id, asignacion.dia, asignacion.bloque)
            if key in slots_profesor:
                logger.error(f"❌ REGLA DURA VIOLADA: Choque de profesor en {asignacion.dia} bloque {asignacion.bloque}")
                return False
            slots_profesor.add(key)
        
        # 4. Verificar que no hay choques de cursos
        slots_curso = set()
        for asignacion in estado.asignaciones:
            key = (asignacion.curso_id, asignacion.dia, asignacion.bloque)
            if key in slots_curso:
                logger.error(f"❌ REGLA DURA VIOLADA: Choque de curso en {asignacion.dia} bloque {asignacion.bloque}")
                return False
            slots_curso.add(key)
        
        logger.info("✅ Todas las reglas duras verificadas")
        return True
    
    def _contar_cursos_completos(self, estado: EstadoConstruccion) -> int:
        """Cuenta cursos que están 100% completos"""
        completos = 0
        for curso in Curso.objects.all():
            slots_objetivo = self._obtener_slots_objetivo(curso)
            slots_asignados = len([a for a in estado.asignaciones if a.curso_id == curso.id])
            if slots_asignados == slots_objetivo:
                completos += 1
        return completos
    
    def _contar_materias_cumplidas(self, estado: EstadoConstruccion) -> int:
        """Cuenta materias obligatorias que cumplen bloques_por_semana exactos"""
        cumplidas = 0
        for curso in Curso.objects.all():
            materias_obligatorias = MateriaGrado.objects.filter(
                grado=curso.grado,
                materia__es_relleno=False
            )
            
            for mg in materias_obligatorias:
                key = (curso.id, mg.materia.id)
                bloques_asignados = estado.bloques_asignados_materia.get(key, 0)
                bloques_requeridos = mg.materia.bloques_por_semana
                
                if bloques_asignados == bloques_requeridos:
                    cumplidas += 1
        
        return cumplidas
    
    def _obtener_slots_objetivo(self, curso: Curso) -> int:
        """Obtiene número objetivo de slots para un curso"""
        try:
            config_curso = ConfiguracionCurso.objects.get(curso=curso)
            return config_curso.slots_objetivo
        except ConfiguracionCurso.DoesNotExist:
            return self.config_colegio['slots_por_semana']
    
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
    
    def _convertir_a_diccionarios(self, asignaciones: List[SlotAsignacion]) -> List[Dict]:
        """Convierte asignaciones a formato de diccionarios"""
        horarios = []
        
        for asignacion in asignaciones:
            horario = {
                'curso_id': asignacion.curso_id,
                'materia_id': asignacion.materia_id,
                'profesor_id': asignacion.profesor_id,
                'dia': asignacion.dia,
                'bloque': asignacion.bloque,
                'aula_id': asignacion.aula_id,
                'es_relleno': asignacion.es_relleno
            }
            
            # Agregar nombres para facilitar debugging
            try:
                curso = Curso.objects.get(id=asignacion.curso_id)
                materia = Materia.objects.get(id=asignacion.materia_id)
                profesor = Profesor.objects.get(id=asignacion.profesor_id)
                
                horario.update({
                    'curso': curso.nombre,
                    'materia': materia.nombre,
                    'profesor': profesor.nombre
                })
                
                if asignacion.aula_id:
                    from horarios.models import Aula
                    aula = Aula.objects.get(id=asignacion.aula_id)
                    horario['aula'] = aula.nombre
                    
            except Exception as e:
                logger.warning(f"Error obteniendo nombres: {e}")
            
            horarios.append(horario)
        
        return horarios 