"""
Prevalidaciones amistosas para el algoritmo genético.

Proporciona validaciones comprehensivas y amigables que detectan
problemas de factibilidad antes de ejecutar el GA, con explicaciones
claras y sugerencias de solución.
"""

from typing import Dict, List, Tuple, Any, Optional
from dataclasses import dataclass
from django.db.models import Q, Count, Sum
from horarios.models import (
    Profesor, Materia, Curso, Aula, BloqueHorario, 
    MateriaGrado, MateriaProfesor, DisponibilidadProfesor, ConfiguracionColegio
)

@dataclass
class ProblemaFactibilidad:
    """Representa un problema de factibilidad detectado"""
    tipo: str
    severidad: str  # 'critico', 'alto', 'medio', 'bajo'
    titulo: str
    descripcion: str
    entidades_afectadas: List[str]
    impacto: str
    solucion_sugerida: str
    prioridad: int  # 1 = más crítico

@dataclass
class ReporteFactibilidad:
    """Reporte completo de factibilidad del sistema"""
    es_factible: bool
    problemas_criticos: int
    problemas_altos: int
    problemas_medios: int
    problemas_bajos: int
    problemas: List[ProblemaFactibilidad]
    resumen: str
    recomendaciones: List[str]
    metricas_sistema: Dict[str, Any]

class PrevalidacionesAmistosas:
    """
    Sistema de prevalidaciones comprehensivas y amigables.
    Detecta problemas de factibilidad antes de ejecutar el GA.
    """
    
    def __init__(self):
        self.problemas_detectados = []
        self.metricas_sistema = {}
    
    def validar_factibilidad_completa(self) -> ReporteFactibilidad:
        """
        Ejecuta todas las validaciones de factibilidad.
        
        Returns:
            ReporteFactibilidad completo
        """
        self.problemas_detectados = []
        
        # 1. Validaciones críticas (impiden ejecución)
        self._validar_profesores_sin_disponibilidad()
        self._validar_materias_sin_profesores()
        self._validar_factibilidad_bloques_por_semana()
        self._validar_bloques_tipo_clase()
        
        # 2. Validaciones de alto impacto
        self._validar_disponibilidad_insuficiente()
        self._validar_capacidad_aulas()
        self._validar_distribucion_profesores()
        
        # 3. Validaciones de medio impacto
        self._validar_balance_materias()
        self._validar_restricciones_especiales()
        
        # 4. Validaciones de bajo impacto
        self._validar_optimizaciones_posibles()
        
        # Calcular métricas del sistema
        self._calcular_metricas_sistema()
        
        # Generar reporte
        return self._generar_reporte()
    
    def _validar_profesores_sin_disponibilidad(self):
        """Valida que todos los profesores tengan disponibilidad"""
        profesores_sin_disponibilidad = Profesor.objects.exclude(
            id__in=DisponibilidadProfesor.objects.values_list('profesor', flat=True)
        )
        
        if profesores_sin_disponibilidad.exists():
            nombres = [p.nombre for p in profesores_sin_disponibilidad]
            self.problemas_detectados.append(ProblemaFactibilidad(
                tipo="profesores_sin_disponibilidad",
                severidad="critico",
                titulo="Profesores sin disponibilidad definida",
                descripcion=f"Los siguientes profesores no tienen disponibilidad definida: {', '.join(nombres)}",
                entidades_afectadas=nombres,
                impacto="El GA no puede asignar horarios a estos profesores",
                solucion_sugerida="Definir disponibilidad para cada profesor en DisponibilidadProfesor",
                prioridad=1
            ))
    
    def _validar_materias_sin_profesores(self):
        """Valida que todas las materias del plan tengan profesores habilitados"""
        materias_sin_profesor = MateriaGrado.objects.exclude(
            materia__in=MateriaProfesor.objects.values_list('materia', flat=True)
        )
        
        if materias_sin_profesor.exists():
            detalles = []
            for mg in materias_sin_profesor:
                detalles.append(f"{mg.materia.nombre} ({mg.grado.nombre})")
            
            self.problemas_detectados.append(ProblemaFactibilidad(
                tipo="materias_sin_profesor",
                severidad="critico",
                titulo="Materias del plan sin profesores habilitados",
                descripcion=f"Las siguientes materias no tienen profesores que puedan enseñarlas: {', '.join(detalles)}",
                entidades_afectadas=detalles,
                impacto="El GA no puede generar horarios para estas materias",
                solucion_sugerida="Asignar profesores a estas materias en MateriaProfesor o remover del plan",
                prioridad=1
            ))
    
    def _validar_factibilidad_bloques_por_semana(self):
        """Valida que sea posible cumplir con los bloques por semana requeridos"""
        try:
            config = ConfiguracionColegio.objects.first()
            if not config:
                self.problemas_detectados.append(ProblemaFactibilidad(
                    tipo="configuracion_faltante",
                    severidad="critico",
                    titulo="Configuración del colegio no encontrada",
                    descripcion="No se encontró configuración del colegio",
                    entidades_afectadas=["Sistema"],
                    impacto="No se puede calcular factibilidad sin configuración",
                    solucion_sugerida="Crear configuración del colegio con días y bloques por día",
                    prioridad=1
                ))
                return
            
            dias_clase = [dia.strip() for dia in config.dias_clase.split(',')]
            total_slots_disponibles = len(dias_clase) * config.bloques_por_dia
            total_bloques_requeridos = sum([mg.materia.bloques_por_semana for mg in MateriaGrado.objects.all()])
            
            if total_bloques_requeridos > total_slots_disponibles:
                self.problemas_detectados.append(ProblemaFactibilidad(
                    tipo="bloques_por_semana_insuficientes",
                    severidad="critico",
                    titulo="Slots insuficientes para bloques requeridos",
                    descripcion=f"Se requieren {total_bloques_requeridos} bloques pero solo hay {total_slots_disponibles} disponibles",
                    entidades_afectadas=[f"Requeridos: {total_bloques_requeridos}", f"Disponibles: {total_slots_disponibles}"],
                    impacto="Es matemáticamente imposible generar un horario válido",
                    solucion_sugerida="Reducir bloques por semana de materias o aumentar días/bloques por día",
                    prioridad=1
                ))
            
            # Factor de ocupación
            factor_ocupacion = total_bloques_requeridos / total_slots_disponibles
            if factor_ocupacion > 0.95:
                self.problemas_detectados.append(ProblemaFactibilidad(
                    tipo="factor_ocupacion_alto",
                    severidad="alto",
                    titulo="Factor de ocupación muy alto",
                    descripcion=f"Factor de ocupación: {factor_ocupacion:.1%} (muy cerca del límite)",
                    entidades_afectadas=[f"Factor: {factor_ocupacion:.1%}"],
                    impacto="El GA tendrá muy poca flexibilidad para optimizar",
                    solucion_sugerida="Considerar reducir bloques por semana o aumentar capacidad",
                    prioridad=2
                ))
                
        except Exception as e:
            self.problemas_detectados.append(ProblemaFactibilidad(
                tipo="error_calculo_factibilidad",
                severidad="critico",
                titulo="Error calculando factibilidad",
                descripcion=f"Error: {str(e)}",
                entidades_afectadas=["Sistema"],
                impacto="No se puede determinar si el sistema es factible",
                solucion_sugerida="Revisar integridad de datos y configuración",
                prioridad=1
            ))
    
    def _validar_bloques_tipo_clase(self):
        """Valida que existan bloques tipo 'clase' disponibles"""
        bloques_clase = BloqueHorario.objects.filter(tipo='clase')
        
        if not bloques_clase.exists():
            self.problemas_detectados.append(ProblemaFactibilidad(
                tipo="no_hay_bloques_clase",
                severidad="critico",
                titulo="No hay bloques tipo 'clase' definidos",
                descripcion="No se encontraron bloques de tipo 'clase' en el sistema",
                entidades_afectadas=["BloqueHorario"],
                impacto="El GA no puede asignar materias sin bloques disponibles",
                solucion_sugerida="Crear bloques de tipo 'clase' en BloqueHorario",
                prioridad=1
            ))
    
    def _validar_disponibilidad_insuficiente(self):
        """Valida que la disponibilidad sea suficiente para los requerimientos"""
        # Calcular disponibilidad total por profesor
        disponibilidad_por_profesor = {}
        for disp in DisponibilidadProfesor.objects.all():
            if disp.profesor_id not in disponibilidad_por_profesor:
                disponibilidad_por_profesor[disp.profesor_id] = 0
            disponibilidad_por_profesor[disp.profesor_id] += (disp.bloque_fin - disp.bloque_inicio + 1)
        
        # Calcular bloques requeridos por profesor
        bloques_requeridos_por_profesor = {}
        for mp in MateriaProfesor.objects.all():
            if mp.profesor_id not in bloques_requeridos_por_profesor:
                bloques_requeridos_por_profesor[mp.profesor_id] = 0
            bloques_requeridos_por_profesor[mp.profesor_id] += mp.materia.bloques_por_semana
        
        # Verificar cada profesor
        for profesor_id, bloques_requeridos in bloques_requeridos_por_profesor.items():
            disponibilidad = disponibilidad_por_profesor.get(profesor_id, 0)
            
            if disponibilidad < bloques_requeridos:
                try:
                    profesor = Profesor.objects.get(id=profesor_id)
                    self.problemas_detectados.append(ProblemaFactibilidad(
                        tipo="disponibilidad_insuficiente",
                        severidad="alto",
                        titulo=f"Disponibilidad insuficiente para {profesor.nombre}",
                        descripcion=f"Requiere {bloques_requeridos} bloques pero solo tiene {disponibilidad} disponibles",
                        entidades_afectadas=[profesor.nombre],
                        impacto="El GA no puede cumplir con todos los bloques requeridos",
                        solucion_sugerida="Aumentar disponibilidad del profesor o reducir materias asignadas",
                        prioridad=2
                    ))
                except Profesor.DoesNotExist:
                    continue
    
    def _validar_capacidad_aulas(self):
        """Valida que las aulas tengan capacidad suficiente"""
        # Verificar que todos los cursos tengan aula fija
        cursos_sin_aula = Curso.objects.filter(aula_fija__isnull=True)
        
        if cursos_sin_aula.exists():
            nombres = [c.nombre for c in cursos_sin_aula]
            self.problemas_detectados.append(ProblemaFactibilidad(
                tipo="cursos_sin_aula_fija",
                severidad="alto",
                titulo="Cursos sin aula fija asignada",
                descripcion=f"Los siguientes cursos no tienen aula fija: {', '.join(nombres)}",
                entidades_afectadas=nombres,
                impacto="El GA no puede asignar horarios sin aula definida",
                solucion_sugerida="Asignar aula fija a cada curso",
                prioridad=2
            ))
    
    def _validar_distribucion_profesores(self):
        """Valida distribución equitativa de carga entre profesores"""
        # Calcular carga por profesor
        carga_por_profesor = {}
        for mp in MateriaProfesor.objects.all():
            if mp.profesor_id not in carga_por_profesor:
                carga_por_profesor[mp.profesor_id] = 0
            carga_por_profesor[mp.profesor_id] += mp.materia.bloques_por_semana
        
        if carga_por_profesor:
            cargas = list(carga_por_profesor.values())
            max_carga = max(cargas)
            min_carga = min(cargas)
            
            if max_carga > min_carga * 3:  # Más del triple
                profesores_sobrecargados = [
                    Profesor.objects.get(id=pid).nombre 
                    for pid, carga in carga_por_profesor.items() 
                    if carga == max_carga
                ]
                
                self.problemas_detectados.append(ProblemaFactibilidad(
                    tipo="distribucion_carga_desigual",
                    severidad="medio",
                    titulo="Distribución de carga muy desigual entre profesores",
                    descripcion=f"Algunos profesores tienen {max_carga} bloques mientras otros solo {min_carga}",
                    entidades_afectadas=profesores_sobrecargados,
                    impacto="Puede causar problemas de equidad y disponibilidad",
                    solucion_sugerida="Revisar distribución de materias entre profesores",
                    prioridad=3
                ))
    
    def _validar_balance_materias(self):
        """Valida balance de materias por grado"""
        # Calcular bloques por grado
        bloques_por_grado = {}
        for mg in MateriaGrado.objects.all():
            if mg.grado_id not in bloques_por_grado:
                bloques_por_grado[mg.grado_id] = 0
            bloques_por_grado[mg.grado_id] += mg.materia.bloques_por_semana
        
        if len(bloques_por_grado) > 1:
            bloques = list(bloques_por_grado.values())
            max_bloques = max(bloques)
            min_bloques = min(bloques)
            
            if max_bloques > min_bloques * 1.5:  # Más del 50%
                self.problemas_detectados.append(ProblemaFactibilidad(
                    tipo="balance_materias_desigual",
                    severidad="medio",
                    titulo="Balance desigual de materias entre grados",
                    descripcion=f"El grado con más materias tiene {max_bloques} bloques vs {min_bloques} del menor",
                    entidades_afectadas=["Distribución entre grados"],
                    impacto="Puede causar problemas de optimización del horario",
                    solucion_sugerida="Revisar plan de estudios para balancear carga entre grados",
                    prioridad=3
                ))
    
    def _validar_restricciones_especiales(self):
        """Valida restricciones especiales de materias"""
        # Materias que requieren bloques consecutivos
        materias_consecutivas = Materia.objects.filter(requiere_bloques_consecutivos=True)
        
        if materias_consecutivas.exists():
            nombres = [m.nombre for m in materias_consecutivas]
            self.problemas_detectados.append(ProblemaFactibilidad(
                tipo="materias_requieren_consecutivos",
                severidad="medio",
                titulo="Materias que requieren bloques consecutivos",
                descripcion=f"Las siguientes materias requieren bloques consecutivos: {', '.join(nombres)}",
                entidades_afectadas=nombres,
                impacto="El GA debe considerar esta restricción adicional",
                solucion_sugerida="Verificar que la configuración del GA maneje bloques consecutivos",
                prioridad=3
            ))
        
        # Materias que requieren aula especial
        materias_aula_especial = Materia.objects.filter(requiere_aula_especial=True)
        
        if materias_aula_especial.exists():
            nombres = [m.nombre for m in materias_aula_especial]
            self.problemas_detectados.append(ProblemaFactibilidad(
                tipo="materias_aula_especial",
                severidad="medio",
                titulo="Materias que requieren aula especial",
                descripcion=f"Las siguientes materias requieren aula especial: {', '.join(nombres)}",
                entidades_afectadas=nombres,
                impacto="El GA debe asignar aulas apropiadas",
                solucion_sugerida="Verificar que existan aulas del tipo requerido",
                prioridad=3
            ))
    
    def _validar_optimizaciones_posibles(self):
        """Valida oportunidades de optimización"""
        # Verificar si hay muchos huecos potenciales
        try:
            config = ConfiguracionColegio.objects.first()
            if config:
                dias_clase = [dia.strip() for dia in config.dias_clase.split(',')]
                total_slots = len(dias_clase) * config.bloques_por_dia
                total_bloques_requeridos = sum([mg.materia.bloques_por_semana for mg in MateriaGrado.objects.all()])
                
                if total_bloques_requeridos < total_slots * 0.7:
                    self.problemas_detectados.append(ProblemaFactibilidad(
                        tipo="baja_utilizacion_slots",
                        severidad="bajo",
                        titulo="Baja utilización de slots disponibles",
                        descripcion=f"Se usan {total_bloques_requeridos}/{total_slots} slots ({total_bloques_requeridos/total_slots:.1%})",
                        entidades_afectadas=["Eficiencia del sistema"],
                        impacto="Muchos slots vacíos pueden causar huecos en horarios",
                        solucion_sugerida="Considerar reducir bloques por día o agregar más materias",
                        prioridad=4
                    ))
        except Exception:
            pass
    
    def _calcular_metricas_sistema(self):
        """Calcula métricas generales del sistema"""
        try:
            self.metricas_sistema = {
                "total_cursos": Curso.objects.count(),
                "total_profesores": Profesor.objects.count(),
                "total_materias": Materia.objects.count(),
                "total_aulas": Aula.objects.count(),
                "total_bloques_horario": BloqueHorario.objects.count(),
                "bloques_tipo_clase": BloqueHorario.objects.filter(tipo='clase').count(),
                "materias_con_profesor": MateriaProfesor.objects.count(),
                "materias_en_plan": MateriaGrado.objects.count(),
                "profesores_con_disponibilidad": DisponibilidadProfesor.objects.values('profesor').distinct().count(),
                "cursos_con_aula_fija": Curso.objects.filter(aula_fija__isnull=False).count()
            }
            
            # Calcular factibilidad
            if ConfiguracionColegio.objects.exists():
                config = ConfiguracionColegio.objects.first()
                dias_clase = [dia.strip() for dia in config.dias_clase.split(',')]
                total_slots_disponibles = len(dias_clase) * config.bloques_por_dia
                total_bloques_requeridos = sum([mg.materia.bloques_por_semana for mg in MateriaGrado.objects.all()])
                
                self.metricas_sistema.update({
                    "dias_clase": len(dias_clase),
                    "bloques_por_dia": config.bloques_por_dia,
                    "total_slots_disponibles": total_slots_disponibles,
                    "total_bloques_requeridos": total_bloques_requeridos,
                    "factor_ocupacion": total_bloques_requeridos / total_slots_disponibles if total_slots_disponibles > 0 else 0,
                    "slots_excedentes": total_slots_disponibles - total_bloques_requeridos
                })
                
        except Exception as e:
            self.metricas_sistema["error"] = str(e)
    
    def _generar_reporte(self) -> ReporteFactibilidad:
        """Genera el reporte final de factibilidad"""
        # Contar problemas por severidad
        problemas_criticos = len([p for p in self.problemas_detectados if p.severidad == 'critico'])
        problemas_altos = len([p for p in self.problemas_detectados if p.severidad == 'alto'])
        problemas_medios = len([p for p in self.problemas_detectados if p.severidad == 'medio'])
        problemas_bajos = len([p for p in self.problemas_detectados if p.severidad == 'bajo'])
        
        # Determinar si es factible
        es_factible = problemas_criticos == 0
        
        # Ordenar problemas por prioridad
        problemas_ordenados = sorted(self.problemas_detectados, key=lambda p: p.prioridad)
        
        # Generar resumen
        if es_factible:
            if problemas_altos == 0 and problemas_medios == 0:
                resumen = "✅ Sistema completamente factible. Se puede ejecutar el GA sin problemas."
            elif problemas_altos == 0:
                resumen = "✅ Sistema factible con algunas advertencias menores. Se puede ejecutar el GA."
            else:
                resumen = "⚠️ Sistema factible pero con problemas importantes. Se recomienda resolver antes de ejecutar."
        else:
            resumen = "❌ Sistema NO factible. Resolver problemas críticos antes de ejecutar el GA."
        
        # Generar recomendaciones
        recomendaciones = []
        if problemas_criticos > 0:
            recomendaciones.append("🔴 Resolver TODOS los problemas críticos antes de continuar")
        if problemas_altos > 0:
            recomendaciones.append("🟡 Resolver problemas de alto impacto para mejor rendimiento")
        if problemas_medios > 0:
            recomendaciones.append("🟡 Considerar resolver problemas de medio impacto")
        if problemas_bajos > 0:
            recomendaciones.append("🟢 Problemas de bajo impacto pueden ignorarse por ahora")
        
        return ReporteFactibilidad(
            es_factible=es_factible,
            problemas_criticos=problemas_criticos,
            problemas_altos=problemas_altos,
            problemas_medios=problemas_medios,
            problemas_bajos=problemas_bajos,
            problemas=problemas_ordenados,
            resumen=resumen,
            recomendaciones=recomendaciones,
            metricas_sistema=self.metricas_sistema
        )

def ejecutar_prevalidaciones_amistosas() -> ReporteFactibilidad:
    """Función de conveniencia para ejecutar todas las prevalidaciones"""
    validador = PrevalidacionesAmistosas()
    return validador.validar_factibilidad_completa()

def validar_factibilidad_rapida() -> bool:
    """Validación rápida que solo verifica problemas críticos"""
    validador = PrevalidacionesAmistosas()
    reporte = validador.validar_factibilidad_completa()
    return reporte.es_factible

def obtener_problemas_por_prioridad() -> Dict[int, List[ProblemaFactibilidad]]:
    """Obtiene problemas agrupados por prioridad"""
    validador = PrevalidacionesAmistosas()
    reporte = validador.validar_factibilidad_completa()
    
    problemas_por_prioridad = {}
    for problema in reporte.problemas:
        if problema.prioridad not in problemas_por_prioridad:
            problemas_por_prioridad[problema.prioridad] = []
        problemas_por_prioridad[problema.prioridad].append(problema)
    
    return problemas_por_prioridad 