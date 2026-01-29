#!/usr/bin/env python3
"""
Sistema completo de reportes y diagnósticos para horarios.
Genera reportes detallados por curso, profesor y sistema general.
"""

from typing import Dict, List, Tuple, Set, Optional
from collections import defaultdict, Counter
from dataclasses import dataclass
import logging

from horarios.models import (
    Horario, Curso, Materia, Profesor, Aula,
    ConfiguracionColegio, ConfiguracionCurso, MateriaRelleno
)

logger = logging.getLogger(__name__)

@dataclass
class ResumenCurso:
    """Resumen estadístico de un curso"""
    curso_id: int
    curso_nombre: str
    ocupacion_porcentaje: float
    total_slots: int
    slots_ocupados: int
    huecos: int
    materias_obligatorias_cumplidas: int
    materias_obligatorias_total: int
    bloques_relleno: int
    distribucion_por_dia: Dict[str, int]
    materias_por_dia: Dict[str, List[str]]
    problemas: List[str]
    calidad_general: str  # "Excelente", "Buena", "Regular", "Deficiente"

@dataclass
class ResumenProfesor:
    """Resumen estadístico de un profesor"""
    profesor_id: int
    profesor_nombre: str
    carga_semanal_total: int
    bloques_libres: int
    numero_primeras: int
    numero_ultimas: int
    huecos_jornada: int
    cursos_asignados: List[str]
    materias_dictadas: List[str]
    distribucion_por_dia: Dict[str, int]
    eficiencia: float  # 0.0 a 1.0
    problemas: List[str]

@dataclass
class AlertaPrevia:
    """Alerta detectada antes de generar horarios"""
    tipo: str
    severidad: str  # "critica", "alta", "media", "baja"
    descripcion: str
    materia: Optional[str] = None
    curso: Optional[str] = None
    profesor: Optional[str] = None
    solucion_sugerida: str = ""

class SistemaReportes:
    """
    Sistema completo de reportes y diagnósticos para horarios.
    Proporciona análisis detallado del estado del sistema.
    """
    
    def __init__(self):
        self.config_colegio = self._obtener_configuracion()
        
    def generar_reporte_completo(self, horarios: Optional[List[Dict]] = None) -> Dict:
        """
        Genera reporte completo del sistema de horarios.
        
        Args:
            horarios: Lista de horarios a analizar. Si None, usa los de la BD.
            
        Returns:
            Dict con reporte completo
        """
        logger.info("Generando reporte completo del sistema")
        
        if horarios is None:
            horarios = self._obtener_horarios_bd()
        
        # Generar todos los reportes
        resumen_cursos = self.generar_resumen_cursos(horarios)
        resumen_profesores = self.generar_resumen_profesores(horarios)
        alertas_previas = self.generar_alertas_previas()
        estadisticas_generales = self.calcular_estadisticas_generales(horarios)
        
        reporte = {
            'timestamp': self._obtener_timestamp(),
            'resumen_cursos': resumen_cursos,
            'resumen_profesores': resumen_profesores,
            'alertas_previas': alertas_previas,
            'estadisticas_generales': estadisticas_generales,
            'recomendaciones': self._generar_recomendaciones(resumen_cursos, resumen_profesores, alertas_previas),
            'calidad_global': self._calcular_calidad_global(resumen_cursos, resumen_profesores, alertas_previas)
        }
        
        logger.info("Reporte completo generado exitosamente")
        return reporte
    
    def generar_resumen_cursos(self, horarios: List[Dict]) -> List[ResumenCurso]:
        """Genera resumen detallado por curso"""
        logger.debug("Generando resumen por cursos")
        
        resumenes = []
        horarios_por_curso = self._agrupar_por_curso(horarios)
        
        for curso in Curso.objects.all():
            horarios_curso = horarios_por_curso.get(curso.id, [])
            resumen = self._analizar_curso(curso, horarios_curso)
            resumenes.append(resumen)
        
        return resumenes
    
    def generar_resumen_profesores(self, horarios: List[Dict]) -> List[ResumenProfesor]:
        """Genera resumen detallado por profesor"""
        logger.debug("Generando resumen por profesores")
        
        resumenes = []
        horarios_por_profesor = self._agrupar_por_profesor(horarios)
        
        for profesor in Profesor.objects.all():
            horarios_profesor = horarios_por_profesor.get(profesor.id, [])
            resumen = self._analizar_profesor(profesor, horarios_profesor)
            resumenes.append(resumen)
        
        return resumenes
    
    def generar_alertas_previas(self) -> List[AlertaPrevia]:
        """Genera alertas sobre problemas detectados antes de generar"""
        logger.debug("Generando alertas previas")
        
        alertas = []
        
        # Importar validador de precondiciones
        from .validador_precondiciones import ValidadorPrecondiciones
        validador = ValidadorPrecondiciones()
        resultado = validador.validar_factibilidad_completa()
        
        # Convertir problemas a alertas
        for problema in resultado.problemas:
            severidad = "critica" if problema.tipo in ['deficit_semanal', 'sin_profesores_relleno'] else "alta"
            if problema.tipo in ['cuello_botella_diario', 'disponibilidad_concentrada']:
                severidad = "media"
            
            alerta = AlertaPrevia(
                tipo=problema.tipo,
                severidad=severidad,
                descripcion=problema.descripcion,
                materia=problema.materia,
                curso=problema.curso,
                solucion_sugerida=problema.solucion_sugerida
            )
            alertas.append(alerta)
        
        # Alertas adicionales específicas del sistema
        alertas.extend(self._detectar_alertas_configuracion())
        
        return alertas
    
    def calcular_estadisticas_generales(self, horarios: List[Dict]) -> Dict:
        """Calcula estadísticas generales del sistema"""
        logger.debug("Calculando estadísticas generales")
        
        total_slots_posibles = Curso.objects.count() * self.config_colegio['slots_por_semana']
        slots_ocupados = len(horarios)
        
        # Contadores por tipo
        materias_obligatorias = 0
        materias_relleno = 0
        
        for h in horarios:
            materia_id = h.get('materia_id')
            if materia_id:
                try:
                    materia = Materia.objects.get(id=materia_id)
                    if materia.es_relleno:
                        materias_relleno += 1
                    else:
                        materias_obligatorias += 1
                except Materia.DoesNotExist:
                    pass
        
        # Distribución por día
        distribucion_dias = Counter(h.get('dia') for h in horarios)
        
        # Profesores activos
        profesores_activos = len(set(h.get('profesor_id') for h in horarios if h.get('profesor_id')))
        
        # Aulas utilizadas
        aulas_utilizadas = len(set(h.get('aula_id') for h in horarios if h.get('aula_id')))
        
        estadisticas = {
            'ocupacion_global': {
                'slots_ocupados': slots_ocupados,
                'slots_posibles': total_slots_posibles,
                'porcentaje': (slots_ocupados / total_slots_posibles * 100) if total_slots_posibles > 0 else 0
            },
            'distribucion_materias': {
                'obligatorias': materias_obligatorias,
                'relleno': materias_relleno,
                'porcentaje_relleno': (materias_relleno / slots_ocupados * 100) if slots_ocupados > 0 else 0
            },
            'distribucion_dias': dict(distribucion_dias),
            'recursos_utilizados': {
                'profesores_activos': profesores_activos,
                'profesores_totales': Profesor.objects.count(),
                'aulas_utilizadas': aulas_utilizadas,
                'aulas_totales': Aula.objects.count()
            },
            'configuracion': {
                'cursos_totales': Curso.objects.count(),
                'materias_totales': Materia.objects.count(),
                'materias_relleno_configuradas': Materia.objects.filter(es_relleno=True).count(),
                'slots_por_semana': self.config_colegio['slots_por_semana']
            }
        }
        
        return estadisticas
    
    def _analizar_curso(self, curso: Curso, horarios_curso: List[Dict]) -> ResumenCurso:
        """Analiza un curso específico"""
        slots_objetivo = self._obtener_slots_objetivo(curso)
        slots_ocupados = len(horarios_curso)
        ocupacion_porcentaje = (slots_ocupados / slots_objetivo * 100) if slots_objetivo > 0 else 0
        
        # Calcular huecos
        huecos = self._calcular_huecos_curso(horarios_curso)
        
        # Analizar materias obligatorias
        materias_obligatorias = self._obtener_materias_obligatorias(curso)
        materias_cumplidas = self._verificar_materias_cumplidas(curso, horarios_curso, materias_obligatorias)
        
        # Contar bloques de relleno
        bloques_relleno = 0
        for h in horarios_curso:
            materia_id = h.get('materia_id')
            if materia_id:
                try:
                    materia = Materia.objects.get(id=materia_id)
                    if materia.es_relleno:
                        bloques_relleno += 1
                except Materia.DoesNotExist:
                    pass
        
        # Distribución por día
        distribucion_por_dia = defaultdict(int)
        materias_por_dia = defaultdict(list)
        
        for h in horarios_curso:
            dia = h.get('dia')
            materia_id = h.get('materia_id')
            
            if dia:
                distribucion_por_dia[dia] += 1
                
                if materia_id:
                    try:
                        materia = Materia.objects.get(id=materia_id)
                        if materia.nombre not in materias_por_dia[dia]:
                            materias_por_dia[dia].append(materia.nombre)
                    except Materia.DoesNotExist:
                        pass
        
        # Detectar problemas
        problemas = []
        if ocupacion_porcentaje < 100:
            problemas.append(f"Ocupación incompleta: {ocupacion_porcentaje:.1f}%")
        if huecos > 0:
            problemas.append(f"{huecos} huecos en el horario")
        if materias_cumplidas < len(materias_obligatorias):
            problemas.append(f"Materias obligatorias incompletas: {materias_cumplidas}/{len(materias_obligatorias)}")
        
        # Calcular calidad general
        if ocupacion_porcentaje == 100 and huecos == 0 and materias_cumplidas == len(materias_obligatorias):
            calidad = "Excelente"
        elif ocupacion_porcentaje >= 95 and huecos <= 1:
            calidad = "Buena"
        elif ocupacion_porcentaje >= 80:
            calidad = "Regular"
        else:
            calidad = "Deficiente"
        
        return ResumenCurso(
            curso_id=curso.id,
            curso_nombre=curso.nombre,
            ocupacion_porcentaje=ocupacion_porcentaje,
            total_slots=slots_objetivo,
            slots_ocupados=slots_ocupados,
            huecos=huecos,
            materias_obligatorias_cumplidas=materias_cumplidas,
            materias_obligatorias_total=len(materias_obligatorias),
            bloques_relleno=bloques_relleno,
            distribucion_por_dia=dict(distribucion_por_dia),
            materias_por_dia=dict(materias_por_dia),
            problemas=problemas,
            calidad_general=calidad
        )
    
    def _analizar_profesor(self, profesor: Profesor, horarios_profesor: List[Dict]) -> ResumenProfesor:
        """Analiza un profesor específico"""
        carga_semanal = len(horarios_profesor)
        
        # Calcular bloques libres (basado en disponibilidad)
        from .models import DisponibilidadProfesor
        disponibilidades = DisponibilidadProfesor.objects.filter(profesor=profesor)
        bloques_disponibles_total = 0
        
        for disp in disponibilidades:
            bloques_dia = disp.bloque_fin - disp.bloque_inicio + 1
            bloques_disponibles_total += bloques_dia
        
        bloques_libres = max(0, bloques_disponibles_total - carga_semanal)
        
        # Analizar distribución por día
        distribucion_por_dia = defaultdict(int)
        for h in horarios_profesor:
            dia = h.get('dia')
            if dia:
                distribucion_por_dia[dia] += 1
        
        # Calcular primeras y últimas
        primeras, ultimas = self._calcular_primeras_ultimas(horarios_profesor)
        
        # Calcular huecos en jornada
        huecos = self._calcular_huecos_profesor(horarios_profesor)
        
        # Obtener cursos y materias
        cursos_asignados = list(set(h.get('curso', 'Desconocido') for h in horarios_profesor))
        materias_dictadas = []
        
        for h in horarios_profesor:
            materia_id = h.get('materia_id')
            if materia_id:
                try:
                    materia = Materia.objects.get(id=materia_id)
                    if materia.nombre not in materias_dictadas:
                        materias_dictadas.append(materia.nombre)
                except Materia.DoesNotExist:
                    pass
        
        # Calcular eficiencia (carga vs disponibilidad)
        eficiencia = (carga_semanal / bloques_disponibles_total) if bloques_disponibles_total > 0 else 0
        
        # Detectar problemas
        problemas = []
        if carga_semanal > profesor.max_bloques_por_semana:
            problemas.append(f"Sobrecarga: {carga_semanal}/{profesor.max_bloques_por_semana} bloques")
        if eficiencia > 0.9:
            problemas.append("Eficiencia muy alta (posible sobrecarga)")
        if huecos > 5:
            problemas.append(f"Muchos huecos en jornada: {huecos}")
        
        return ResumenProfesor(
            profesor_id=profesor.id,
            profesor_nombre=profesor.nombre,
            carga_semanal_total=carga_semanal,
            bloques_libres=bloques_libres,
            numero_primeras=primeras,
            numero_ultimas=ultimas,
            huecos_jornada=huecos,
            cursos_asignados=cursos_asignados,
            materias_dictadas=materias_dictadas,
            distribucion_por_dia=dict(distribucion_por_dia),
            eficiencia=eficiencia,
            problemas=problemas
        )
    
    def _detectar_alertas_configuracion(self) -> List[AlertaPrevia]:
        """Detecta alertas específicas de configuración"""
        alertas = []
        
        # Verificar materias sin profesor
        materias_sin_profesor = []
        for materia in Materia.objects.filter(es_relleno=False):
            if not materia.materiaprofesor_set.exists():
                materias_sin_profesor.append(materia.nombre)
        
        if materias_sin_profesor:
            alertas.append(AlertaPrevia(
                tipo="materias_sin_profesor",
                severidad="critica",
                descripcion=f"Materias obligatorias sin profesor: {', '.join(materias_sin_profesor)}",
                solucion_sugerida="Asignar profesores a estas materias"
            ))
        
        # Verificar cursos sin configuración
        cursos_sin_config = []
        for curso in Curso.objects.all():
            try:
                ConfiguracionCurso.objects.get(curso=curso)
            except ConfiguracionCurso.DoesNotExist:
                cursos_sin_config.append(curso.nombre)
        
        if cursos_sin_config:
            alertas.append(AlertaPrevia(
                tipo="cursos_sin_configuracion",
                severidad="media",
                descripcion=f"Cursos sin configuración específica: {', '.join(cursos_sin_config)}",
                solucion_sugerida="Crear configuración específica para estos cursos"
            ))
        
        return alertas
    
    def _calcular_huecos_curso(self, horarios_curso: List[Dict]) -> int:
        """Calcula huecos en el horario de un curso"""
        if not horarios_curso:
            return 0
        
        # Agrupar por día
        por_dia = defaultdict(list)
        for h in horarios_curso:
            dia = h.get('dia')
            bloque = h.get('bloque')
            if dia and bloque:
                por_dia[dia].append(bloque)
        
        huecos_total = 0
        for dia, bloques in por_dia.items():
            if len(bloques) > 1:
                bloques_ordenados = sorted(bloques)
                for i in range(len(bloques_ordenados) - 1):
                    huecos = bloques_ordenados[i+1] - bloques_ordenados[i] - 1
                    huecos_total += max(0, huecos)
        
        return huecos_total
    
    def _calcular_huecos_profesor(self, horarios_profesor: List[Dict]) -> int:
        """Calcula huecos en la jornada de un profesor"""
        return self._calcular_huecos_curso(horarios_profesor)  # Misma lógica
    
    def _calcular_primeras_ultimas(self, horarios_profesor: List[Dict]) -> Tuple[int, int]:
        """Calcula número de primeras y últimas horas de un profesor"""
        por_dia = defaultdict(list)
        for h in horarios_profesor:
            dia = h.get('dia')
            bloque = h.get('bloque')
            if dia and bloque:
                por_dia[dia].append(bloque)
        
        primeras = 0
        ultimas = 0
        
        for dia, bloques in por_dia.items():
            if bloques:
                bloques_ordenados = sorted(bloques)
                if bloques_ordenados[0] == 1:  # Primera hora del día
                    primeras += 1
                if bloques_ordenados[-1] == self.config_colegio['bloques_por_dia']:  # Última hora
                    ultimas += 1
        
        return primeras, ultimas
    
    def _obtener_configuracion(self) -> Dict:
        """Obtiene configuración del colegio"""
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
    
    def _obtener_horarios_bd(self) -> List[Dict]:
        """Obtiene horarios de la base de datos"""
        horarios = []
        for h in Horario.objects.select_related('curso', 'materia', 'profesor', 'aula').all():
            horario = {
                'curso_id': h.curso.id,
                'materia_id': h.materia.id,
                'profesor_id': h.profesor.id,
                'dia': h.dia,
                'bloque': h.bloque,
                'curso': h.curso.nombre,
                'materia': h.materia.nombre,
                'profesor': h.profesor.nombre
            }
            
            if h.aula:
                horario['aula_id'] = h.aula.id
                horario['aula'] = h.aula.nombre
            
            horarios.append(horario)
        
        return horarios
    
    def _agrupar_por_curso(self, horarios: List[Dict]) -> Dict[int, List[Dict]]:
        """Agrupa horarios por curso"""
        por_curso = defaultdict(list)
        for h in horarios:
            curso_id = h.get('curso_id')
            if curso_id:
                por_curso[curso_id].append(h)
        return dict(por_curso)
    
    def _agrupar_por_profesor(self, horarios: List[Dict]) -> Dict[int, List[Dict]]:
        """Agrupa horarios por profesor"""
        por_profesor = defaultdict(list)
        for h in horarios:
            profesor_id = h.get('profesor_id')
            if profesor_id:
                por_profesor[profesor_id].append(h)
        return dict(por_profesor)
    
    def _obtener_slots_objetivo(self, curso: Curso) -> int:
        """Obtiene slots objetivo para un curso"""
        try:
            config_curso = ConfiguracionCurso.objects.get(curso=curso)
            return config_curso.slots_objetivo
        except ConfiguracionCurso.DoesNotExist:
            return self.config_colegio['slots_por_semana']
    
    def _obtener_materias_obligatorias(self, curso: Curso) -> List:
        """Obtiene materias obligatorias de un curso"""
        from horarios.models import MateriaGrado
        return list(MateriaGrado.objects.filter(
            grado=curso.grado,
            materia__es_relleno=False
        ).select_related('materia'))
    
    def _verificar_materias_cumplidas(self, curso: Curso, horarios_curso: List[Dict], materias_obligatorias: List) -> int:
        """Verifica cuántas materias obligatorias están cumplidas"""
        bloques_por_materia = defaultdict(int)
        
        for h in horarios_curso:
            materia_id = h.get('materia_id')
            if materia_id:
                bloques_por_materia[materia_id] += 1
        
        cumplidas = 0
        for mg in materias_obligatorias:
            bloques_asignados = bloques_por_materia.get(mg.materia.id, 0)
            bloques_requeridos = mg.materia.bloques_por_semana
            
            if bloques_asignados >= bloques_requeridos:
                cumplidas += 1
        
        return cumplidas
    
    def _generar_recomendaciones(self, resumen_cursos: List[ResumenCurso], 
                                resumen_profesores: List[ResumenProfesor], 
                                alertas: List[AlertaPrevia]) -> List[str]:
        """Genera recomendaciones basadas en el análisis"""
        recomendaciones = []
        
        # Analizar cursos con problemas
        cursos_problematicos = [c for c in resumen_cursos if c.problemas]
        if cursos_problematicos:
            recomendaciones.append(f"Revisar {len(cursos_problematicos)} cursos con problemas detectados")
        
        # Analizar profesores sobrecargados
        profesores_sobrecargados = [p for p in resumen_profesores if any('Sobrecarga' in prob for prob in p.problemas)]
        if profesores_sobrecargados:
            recomendaciones.append(f"Redistribuir carga de {len(profesores_sobrecargados)} profesores sobrecargados")
        
        # Analizar alertas críticas
        alertas_criticas = [a for a in alertas if a.severidad == "critica"]
        if alertas_criticas:
            recomendaciones.append(f"Resolver {len(alertas_criticas)} alertas críticas antes de generar horarios")
        
        # Recomendaciones de optimización
        ocupacion_promedio = sum(c.ocupacion_porcentaje for c in resumen_cursos) / len(resumen_cursos) if resumen_cursos else 0
        if ocupacion_promedio < 95:
            recomendaciones.append("Mejorar ocupación general de cursos agregando materias de relleno")
        
        return recomendaciones
    
    def _calcular_calidad_global(self, resumen_cursos: List[ResumenCurso], 
                                resumen_profesores: List[ResumenProfesor], 
                                alertas: List[AlertaPrevia]) -> Dict:
        """Calcula calidad global del sistema"""
        if not resumen_cursos:
            return {"puntuacion": 0, "nivel": "Sin datos", "descripcion": "No hay datos para evaluar"}
        
        # Calcular métricas
        ocupacion_promedio = sum(c.ocupacion_porcentaje for c in resumen_cursos) / len(resumen_cursos)
        cursos_excelentes = len([c for c in resumen_cursos if c.calidad_general == "Excelente"])
        cursos_problematicos = len([c for c in resumen_cursos if c.problemas])
        alertas_criticas = len([a for a in alertas if a.severidad == "critica"])
        
        # Calcular puntuación (0-100)
        puntuacion = 0
        puntuacion += min(40, ocupacion_promedio * 0.4)  # Máximo 40 puntos por ocupación
        puntuacion += min(30, (cursos_excelentes / len(resumen_cursos)) * 30)  # Máximo 30 por calidad
        puntuacion += max(0, 20 - (cursos_problematicos * 2))  # Restar por problemas
        puntuacion += max(0, 10 - (alertas_criticas * 5))  # Restar por alertas críticas
        
        # Determinar nivel
        if puntuacion >= 90:
            nivel = "Excelente"
            descripcion = "Sistema optimizado y funcionando correctamente"
        elif puntuacion >= 75:
            nivel = "Buena"
            descripcion = "Sistema en buen estado con mejoras menores necesarias"
        elif puntuacion >= 60:
            nivel = "Regular"
            descripcion = "Sistema funcional pero requiere optimizaciones"
        else:
            nivel = "Deficiente"
            descripcion = "Sistema requiere mejoras importantes"
        
        return {
            "puntuacion": round(puntuacion, 1),
            "nivel": nivel,
            "descripcion": descripcion,
            "metricas": {
                "ocupacion_promedio": round(ocupacion_promedio, 1),
                "cursos_excelentes": cursos_excelentes,
                "cursos_problematicos": cursos_problematicos,
                "alertas_criticas": alertas_criticas
            }
        }
    
    def _obtener_timestamp(self) -> str:
        """Obtiene timestamp actual"""
        from datetime import datetime
        return datetime.now().isoformat() 