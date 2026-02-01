#!/usr/bin/env python3
"""
Validador de precondiciones para generación de horarios.
Verifica factibilidad ANTES de intentar generar horarios.
"""

from typing import Dict, List, Tuple, Set, Optional
from collections import defaultdict, Counter
from dataclasses import dataclass
import logging

from horarios.models import (
    Curso, Materia, Profesor, BloqueHorario, ConfiguracionColegio,
    DisponibilidadProfesor, MateriaProfesor, MateriaGrado,
    ConfiguracionCurso, MateriaRelleno
)

logger = logging.getLogger(__name__)

@dataclass
class ProblemaFactibilidad:
    """Representa un problema de factibilidad detectado"""
    tipo: str
    descripcion: str
    materia: Optional[str] = None
    curso: Optional[str] = None
    dia: Optional[str] = None
    oferta: int = 0
    demanda: int = 0
    deficit: int = 0
    solucion_sugerida: str = ""

@dataclass
class ResultadoFactibilidad:
    """Resultado del análisis de factibilidad"""
    es_factible: bool
    problemas: List[ProblemaFactibilidad]
    estadisticas: Dict
    reporte_detallado: str

class ValidadorPrecondiciones:
    """
    Validador de precondiciones para generación de horarios.
    Implementa validaciones de oferta vs demanda y cuellos de botella.
    """
    
    def __init__(self):
        self.problemas = []
        self.estadisticas = {}
        
    def validar_factibilidad_completa(self) -> ResultadoFactibilidad:
        """
        Ejecuta todas las validaciones de factibilidad.
        
        Returns:
            ResultadoFactibilidad con análisis completo
        """
        logger.info("Iniciando validación de factibilidad")
        
        self.problemas = []
        self.estadisticas = {}
        
        # Obtener configuración base
        config_colegio = self._obtener_configuracion_colegio()
        
        # Ejecutar validaciones
        self._validar_configuracion_basica(config_colegio)
        self._validar_balance_global_bloques()  # Nueva validación crítica
        self._validar_oferta_vs_demanda_semanal()
        self._validar_oferta_vs_demanda_diaria()
        self._validar_completitud_profesores_relleno()
        self._validar_disponibilidad_distribuida()
        
        # Generar estadísticas y reporte
        self._calcular_estadisticas()
        reporte = self._generar_reporte_detallado()
        
        es_factible = len([p for p in self.problemas if p.tipo in [
            'deficit_semanal', 'deficit_diario_critico', 'sin_profesores_relleno'
        ]]) == 0
        
        logger.info(f"Factibilidad: {'SÍ' if es_factible else 'NO'} - {len(self.problemas)} problemas detectados")
        
        return ResultadoFactibilidad(
            es_factible=es_factible,
            problemas=self.problemas.copy(),
            estadisticas=self.estadisticas.copy(),
            reporte_detallado=reporte
        )
    
    def _obtener_configuracion_colegio(self) -> Dict:
        """Obtiene configuración base del colegio"""
        config = ConfiguracionColegio.objects.first()
        if config:
            dias_clase = [d.strip() for d in config.dias_clase.split(',')]
            return {
                'bloques_por_dia': config.bloques_por_dia,
                'dias_clase': dias_clase,
                'slots_por_semana': config.bloques_por_dia * len(dias_clase)
            }
        else:
            return {
                'bloques_por_dia': 6,
                'dias_clase': ['lunes', 'martes', 'miércoles', 'jueves', 'viernes'],
                'slots_por_semana': 30
            }
    
    def _validar_configuracion_basica(self, config_colegio: Dict):
        """Valida que la configuración básica sea coherente"""
        
        # Verificar que hay bloques de clase configurados
        bloques_clase = BloqueHorario.objects.filter(tipo='clase').count()
        if bloques_clase < config_colegio['bloques_por_dia']:
            self.problemas.append(ProblemaFactibilidad(
                tipo="configuracion_bloques",
                descripcion=f"Configurados {bloques_clase} bloques de clase, pero se necesitan {config_colegio['bloques_por_dia']}",
                solucion_sugerida=f"Crear {config_colegio['bloques_por_dia'] - bloques_clase} bloques adicionales de tipo 'clase'"
            ))
        
        # Verificar que hay cursos
        total_cursos = Curso.objects.count()
        if total_cursos == 0:
            self.problemas.append(ProblemaFactibilidad(
                tipo="sin_cursos",
                descripcion="No hay cursos configurados",
                solucion_sugerida="Crear al menos un curso"
            ))
        
        # Verificar que hay profesores
        total_profesores = Profesor.objects.count()
        if total_profesores == 0:
            self.problemas.append(ProblemaFactibilidad(
                tipo="sin_profesores",
                descripcion="No hay profesores configurados",
                solucion_sugerida="Crear al menos un profesor"
            ))
    
    def _validar_balance_global_bloques(self):
        """
        Validación INTELIGENTE: Verifica que la oferta TOTAL de bloques supere a la demanda TOTAL.
        Evita el problema de 'doble conteo' cuando un profesor dicta múltiples materias.
        """
        # 1. Calcular Demanda Total (suma de todos los bloques requeridos por todos los cursos)
        demanda_por_materia = self._calcular_demanda_semanal()
        demanda_total = sum(demanda_por_materia.values())
        
        # 2. Calcular Oferta Total REAL (sin doble conteo por materia)
        oferta_total = 0
        for profesor in Profesor.objects.all():
            # Disponibilidad horaria física (cuántos bloques marcó en verde)
            disponibilidades = DisponibilidadProfesor.objects.filter(profesor=profesor)
            bloques_fisicos = 0
            for disp in disponibilidades:
                bloques_fisicos += (disp.bloque_fin - disp.bloque_inicio + 1)
            
            # La capacidad real es el mínimo entre disponibilidad física y su contrato/tope
            capacidad_real = min(bloques_fisicos, profesor.max_bloques_por_semana)
            oferta_total += capacidad_real
            
        # 3. Validar Balance Global
        if oferta_total < demanda_total:
            self.problemas.append(ProblemaFactibilidad(
                tipo="deficit_global_critico",
                descripcion=f"DÉFICIT CRÍTICO GLOBAL: El colegio necesita {demanda_total} bloques totales, pero los profesores solo pueden cubrir {oferta_total}.",
                oferta=oferta_total,
                demanda=demanda_total,
                deficit=demanda_total - oferta_total,
                solucion_sugerida="Contratar más profesores urgentemente. El horario es matemáticamente imposible."
            ))

    def _validar_oferta_vs_demanda_semanal(self):
        """Valida oferta vs demanda semanal por materia"""
        
        # Calcular demanda por materia (incluyendo relleno)
        demanda_por_materia = self._calcular_demanda_semanal()
        
        # Calcular oferta por materia
        oferta_por_materia = self._calcular_oferta_semanal()
        
        # Verificar déficits
        for materia_id, demanda in demanda_por_materia.items():
            oferta = oferta_por_materia.get(materia_id, 0)
            
            if oferta < demanda:
                deficit = demanda - oferta
                try:
                    materia = Materia.objects.get(id=materia_id)
                    materia_nombre = materia.nombre
                    es_relleno = materia.es_relleno
                except Materia.DoesNotExist:
                    materia_nombre = f"Materia ID {materia_id}"
                    es_relleno = False
                
                self.problemas.append(ProblemaFactibilidad(
                    tipo="deficit_semanal",
                    descripcion=f"Déficit semanal en {materia_nombre}: faltan {deficit} bloques",
                    materia=materia_nombre,
                    oferta=oferta,
                    demanda=demanda,
                    deficit=deficit,
                    solucion_sugerida=self._sugerir_solucion_deficit(materia_nombre, deficit, es_relleno)
                ))
    
    def _calcular_demanda_semanal(self) -> Dict[int, int]:
        """Calcula demanda semanal total por materia"""
        demanda = defaultdict(int)
        
        # Demanda de materias obligatorias
        for curso in Curso.objects.all():
            materias_obligatorias = MateriaGrado.objects.filter(
                grado=curso.grado,
                materia__es_relleno=False
            )
            
            for mg in materias_obligatorias:
                demanda[mg.materia.id] += mg.materia.bloques_por_semana
        
        # Demanda de relleno
        for curso in Curso.objects.all():
            try:
                config_curso = ConfiguracionCurso.objects.get(curso=curso)
                bloques_faltantes = config_curso.calcular_bloques_faltantes()
            except ConfiguracionCurso.DoesNotExist:
                # Calcular manualmente
                config_colegio = self._obtener_configuracion_colegio()
                materias_obligatorias = MateriaGrado.objects.filter(
                    grado=curso.grado,
                    materia__es_relleno=False
                )
                total_obligatorios = sum(mg.materia.bloques_por_semana for mg in materias_obligatorias)
                bloques_faltantes = max(0, config_colegio['slots_por_semana'] - total_obligatorios)
            
            if bloques_faltantes > 0:
                # Distribuir entre materias de relleno disponibles para este grado
                materias_relleno = self._obtener_materias_relleno_para_grado(curso.grado)
                if materias_relleno:
                    # Distribución simple: dividir equitativamente
                    bloques_por_materia = max(1, bloques_faltantes // len(materias_relleno))
                    resto = bloques_faltantes % len(materias_relleno)
                    
                    for i, materia in enumerate(materias_relleno):
                        bloques_asignados = bloques_por_materia
                        if i < resto:
                            bloques_asignados += 1
                        demanda[materia.id] += bloques_asignados
        
        return dict(demanda)
    
    def _calcular_oferta_semanal(self) -> Dict[int, int]:
        """Calcula oferta semanal por materia basada en disponibilidad de profesores"""
        oferta = defaultdict(int)
        
        for materia in Materia.objects.all():
            # Obtener profesores aptos para esta materia
            profesores_aptos = self._obtener_profesores_aptos(materia)
            
            for profesor in profesores_aptos:
                # Calcular bloques disponibles del profesor
                disponibilidades = DisponibilidadProfesor.objects.filter(profesor=profesor)
                bloques_disponibles = 0
                
                for disp in disponibilidades:
                    bloques_dia = disp.bloque_fin - disp.bloque_inicio + 1
                    bloques_disponibles += bloques_dia
                
                # Limitar por máximo semanal del profesor
                bloques_disponibles = min(bloques_disponibles, profesor.max_bloques_por_semana)
                oferta[materia.id] += bloques_disponibles
        
        return dict(oferta)
    
    def _validar_oferta_vs_demanda_diaria(self):
        """Valida cuellos de botella diarios"""
        config_colegio = self._obtener_configuracion_colegio()
        
        for dia in config_colegio['dias_clase']:
            # Calcular oferta por día
            oferta_dia = self._calcular_oferta_diaria(dia)
            
            # Estimar demanda por día (aproximación)
            demanda_semanal = self._calcular_demanda_semanal()
            
            for materia_id, demanda_total in demanda_semanal.items():
                # Aproximar demanda diaria (distribución uniforme)
                demanda_dia_aprox = demanda_total / len(config_colegio['dias_clase'])
                oferta_materia_dia = oferta_dia.get(materia_id, 0)
                
                if oferta_materia_dia < demanda_dia_aprox and demanda_dia_aprox > 2:
                    try:
                        materia = Materia.objects.get(id=materia_id)
                        materia_nombre = materia.nombre
                    except Materia.DoesNotExist:
                        materia_nombre = f"Materia ID {materia_id}"
                    
                    self.problemas.append(ProblemaFactibilidad(
                        tipo="cuello_botella_diario",
                        descripcion=f"Posible cuello de botella en {materia_nombre} los {dia}",
                        materia=materia_nombre,
                        dia=dia,
                        oferta=int(oferta_materia_dia),
                        demanda=int(demanda_dia_aprox),
                        solucion_sugerida=f"Aumentar disponibilidad de profesores de {materia_nombre} los {dia}"
                    ))
    
    def _calcular_oferta_diaria(self, dia: str) -> Dict[int, int]:
        """Calcula oferta por materia en un día específico"""
        oferta = defaultdict(int)
        
        for materia in Materia.objects.all():
            profesores_aptos = self._obtener_profesores_aptos(materia)
            
            for profesor in profesores_aptos:
                # Verificar disponibilidad en este día
                disponibilidad = DisponibilidadProfesor.objects.filter(
                    profesor=profesor,
                    dia=dia
                ).first()
                
                if disponibilidad:
                    bloques_dia = disponibilidad.bloque_fin - disponibilidad.bloque_inicio + 1
                    oferta[materia.id] += bloques_dia
        
        return dict(oferta)
    
    def _validar_completitud_profesores_relleno(self):
        """Valida que haya profesores aptos para relleno"""
        materias_relleno = Materia.objects.filter(es_relleno=True)
        
        for materia in materias_relleno:
            profesores_aptos = self._obtener_profesores_aptos(materia)
            
            if not profesores_aptos:
                self.problemas.append(ProblemaFactibilidad(
                    tipo="sin_profesores_relleno",
                    descripcion=f"Materia de relleno {materia.nombre} no tiene profesores aptos",
                    materia=materia.nombre,
                    solucion_sugerida=f"Asignar profesores a {materia.nombre} o marcar profesores como aptos para relleno"
                ))
    
    def _validar_disponibilidad_distribuida(self):
        """Valida que la disponibilidad esté distribuida en la semana"""
        config_colegio = self._obtener_configuracion_colegio()
        
        for profesor in Profesor.objects.all():
            disponibilidades = DisponibilidadProfesor.objects.filter(profesor=profesor)
            dias_disponibles = set(d.dia for d in disponibilidades)
            
            # Verificar distribución mínima
            if len(dias_disponibles) < 2 and len(dias_disponibles) > 0:
                materias_profesor = MateriaProfesor.objects.filter(profesor=profesor)
                if materias_profesor.exists():
                    self.problemas.append(ProblemaFactibilidad(
                        tipo="disponibilidad_concentrada",
                        descripcion=f"Profesor {profesor.nombre} solo disponible {len(dias_disponibles)} día(s): {', '.join(dias_disponibles)}",
                        solucion_sugerida=f"Aumentar disponibilidad de {profesor.nombre} a más días de la semana"
                    ))
    
    def _obtener_profesores_aptos(self, materia: Materia) -> List[Profesor]:
        """Obtiene lista de profesores aptos para una materia"""
        if materia.es_relleno:
            # Para relleno: profesores específicamente asignados O que pueden dictar relleno
            profesores_especificos = MateriaProfesor.objects.filter(materia=materia).values_list('profesor', flat=True)
            profesores_relleno = Profesor.objects.filter(puede_dictar_relleno=True)
            
            # Combinar ambos conjuntos
            ids_especificos = set(profesores_especificos)
            ids_relleno = set(profesores_relleno.values_list('id', flat=True))
            ids_finales = ids_especificos.union(ids_relleno)
            
            return list(Profesor.objects.filter(id__in=ids_finales))
        else:
            # Para materias obligatorias: solo profesores específicamente asignados
            return list(Profesor.objects.filter(materiaprofesor__materia=materia))
    
    def _obtener_materias_relleno_para_grado(self, grado) -> List[Materia]:
        """Obtiene materias de relleno compatibles con un grado"""
        materias_relleno = []
        
        for config in MateriaRelleno.objects.filter(activa=True):
            if config.grados_compatibles.filter(id=grado.id).exists() or not config.grados_compatibles.exists():
                materias_relleno.append(config.materia)
        
        return materias_relleno
    
    def _sugerir_solucion_deficit(self, materia_nombre: str, deficit: int, es_relleno: bool) -> str:
        """Sugiere solución para déficit de una materia"""
        if es_relleno:
            return f"Asignar {deficit} profesores adicionales a {materia_nombre} o marcar más profesores como aptos para relleno"
        else:
            return f"Asignar {deficit} profesores adicionales a {materia_nombre} o aumentar disponibilidad de profesores existentes"
    
    def _calcular_estadisticas(self):
        """Calcula estadísticas del análisis de factibilidad"""
        self.estadisticas = {
            'total_problemas': len(self.problemas),
            'problemas_criticos': len([p for p in self.problemas if p.tipo in ['deficit_semanal', 'sin_profesores_relleno']]),
            'problemas_por_tipo': Counter(p.tipo for p in self.problemas),
            'materias_con_deficit': len(set(p.materia for p in self.problemas if p.materia and p.deficit > 0)),
            'deficit_total': sum(p.deficit for p in self.problemas if p.deficit > 0),
        }
        
        # Estadísticas de configuración
        self.estadisticas.update({
            'total_cursos': Curso.objects.count(),
            'total_profesores': Profesor.objects.count(),
            'total_materias': Materia.objects.count(),
            'materias_relleno': Materia.objects.filter(es_relleno=True).count(),
            'profesores_relleno': Profesor.objects.filter(puede_dictar_relleno=True).count(),
        })
    
    def _generar_reporte_detallado(self) -> str:
        """Genera reporte detallado de factibilidad"""
        lineas = []
        lineas.append("=" * 60)
        lineas.append("📋 REPORTE DE FACTIBILIDAD PARA GENERACIÓN DE HORARIOS")
        lineas.append("=" * 60)
        
        # Resumen general
        es_factible = len([p for p in self.problemas if p.tipo in [
            'deficit_semanal', 'deficit_diario_critico', 'sin_profesores_relleno'
        ]]) == 0
        
        lineas.append(f"\n🎯 RESULTADO GENERAL: {'✅ FACTIBLE' if es_factible else '❌ NO FACTIBLE'}")
        lineas.append(f"   • Problemas detectados: {self.estadisticas['total_problemas']}")
        lineas.append(f"   • Problemas críticos: {self.estadisticas['problemas_criticos']}")
        
        # Estadísticas de configuración
        lineas.append(f"\n📊 CONFIGURACIÓN ACTUAL:")
        lineas.append(f"   • Cursos: {self.estadisticas['total_cursos']}")
        lineas.append(f"   • Profesores: {self.estadisticas['total_profesores']}")
        lineas.append(f"   • Materias: {self.estadisticas['total_materias']} ({self.estadisticas['materias_relleno']} de relleno)")
        lineas.append(f"   • Profesores para relleno: {self.estadisticas['profesores_relleno']}")
        
        # Problemas por categoría
        if self.problemas:
            lineas.append(f"\n⚠️ PROBLEMAS DETECTADOS:")
            
            problemas_por_tipo = defaultdict(list)
            for problema in self.problemas:
                problemas_por_tipo[problema.tipo].append(problema)
            
            for tipo, problemas in problemas_por_tipo.items():
                lineas.append(f"\n   📌 {tipo.upper().replace('_', ' ')} ({len(problemas)}):")
                for problema in problemas[:5]:  # Mostrar máximo 5 por tipo
                    lineas.append(f"      • {problema.descripcion}")
                    if problema.solucion_sugerida:
                        lineas.append(f"        💡 {problema.solucion_sugerida}")
                
                if len(problemas) > 5:
                    lineas.append(f"      ... y {len(problemas) - 5} más")
        
        # Recomendaciones finales
        lineas.append(f"\n💡 RECOMENDACIONES:")
        if es_factible:
            lineas.append("   ✅ El sistema está listo para generar horarios")
            if self.problemas:
                lineas.append("   📝 Considerar resolver las advertencias para mejor calidad")
        else:
            lineas.append("   🚨 DEBE resolver los problemas críticos antes de generar horarios")
            lineas.append("   📋 Priorizar: déficits semanales y asignación de profesores a relleno")
        
        return "\n".join(lineas)

    def generar_checklist_previo(self) -> Dict[str, bool]:
        """Genera checklist previo a generación según especificaciones"""
        config_colegio = self._obtener_configuracion_colegio()
        checklist = {}
        
        # Para cada curso: Slots semanales calculados y visibles
        for curso in Curso.objects.all():
            try:
                config_curso = ConfiguracionCurso.objects.get(curso=curso)
                slots_objetivo = config_curso.slots_objetivo
            except ConfiguracionCurso.DoesNotExist:
                slots_objetivo = config_colegio['slots_por_semana']
            
            checklist[f"slots_curso_{curso.nombre}"] = slots_objetivo == config_colegio['slots_por_semana']
        
        # Para cada curso: Demanda obligatoria sumada
        demanda_ok = True
        for curso in Curso.objects.all():
            materias_obligatorias = MateriaGrado.objects.filter(
                grado=curso.grado,
                materia__es_relleno=False
            )
            total_obligatorios = sum(mg.materia.bloques_por_semana for mg in materias_obligatorias)
            if total_obligatorios > config_colegio['slots_por_semana']:
                demanda_ok = False
                break
        
        checklist["demanda_obligatoria_viable"] = demanda_ok
        
        # Bloques de relleno necesarios calculados
        relleno_calculado = True
        for curso in Curso.objects.all():
            try:
                config_curso = ConfiguracionCurso.objects.get(curso=curso)
                bloques_faltantes = config_curso.calcular_bloques_faltantes()
                relleno_calculado = relleno_calculado and (bloques_faltantes >= 0)
            except ConfiguracionCurso.DoesNotExist:
                relleno_calculado = False
        
        checklist["relleno_calculado"] = relleno_calculado
        
        # Para cada materia: Oferta semanal ≥ Demanda semanal
        demanda_semanal = self._calcular_demanda_semanal()
        oferta_semanal = self._calcular_oferta_semanal()
        
        oferta_suficiente = True
        for materia_id, demanda in demanda_semanal.items():
            oferta = oferta_semanal.get(materia_id, 0)
            if oferta < demanda:
                oferta_suficiente = False
                break
        
        checklist["oferta_suficiente"] = oferta_suficiente
        
        # Profesores aptos para relleno definidos
        profesores_relleno_ok = True
        for materia in Materia.objects.filter(es_relleno=True):
            profesores_aptos = self._obtener_profesores_aptos(materia)
            if not profesores_aptos:
                profesores_relleno_ok = False
                break
        
        checklist["profesores_relleno_definidos"] = profesores_relleno_ok
        
        # Disponibilidad repartida en la semana
        disponibilidad_repartida = True
        for profesor in Profesor.objects.all():
            disponibilidades = DisponibilidadProfesor.objects.filter(profesor=profesor)
            dias_disponibles = set(d.dia for d in disponibilidades)
            if len(dias_disponibles) < 2 and MateriaProfesor.objects.filter(profesor=profesor).exists():
                disponibilidad_repartida = False
                break
        
        checklist["disponibilidad_repartida"] = disponibilidad_repartida
        
        # Reglas pedagógicas activas configuradas
        from horarios.models import ReglaPedagogica
        reglas_activas = ReglaPedagogica.objects.filter(activa=True).count()
        checklist["reglas_pedagogicas_configuradas"] = reglas_activas > 0
        
        return checklist 