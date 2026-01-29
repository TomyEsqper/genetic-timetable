"""
Explicador de penalizaciones del fitness.

Proporciona explicaciones detalladas de por qué un horario tiene
cierto puntaje de fitness, desglosando las contribuciones de cada
restricción blanda para cursos y profesores específicos.
"""

import numpy as np
from typing import Dict, List, Tuple, Any
from dataclasses import dataclass
from .mascaras import MascarasOptimizadas
from .fitness_optimizado import calcular_fitness_unificado, ConfiguracionFitness

@dataclass
class PenalizacionDetallada:
    """Penalización detallada para una entidad específica"""
    entidad_id: int
    entidad_tipo: str  # 'curso' o 'profesor'
    entidad_nombre: str
    penalizacion_total: float
    contribuciones: Dict[str, float]
    detalles: Dict[str, Any]

@dataclass
class ExplicacionFitness:
    """Explicación completa del fitness de un horario"""
    fitness_total: float
    penalizacion_total: float
    penalizaciones_por_entidad: List[PenalizacionDetallada]
    resumen_por_tipo: Dict[str, Dict[str, Any]]
    recomendaciones: List[str]

class ExplicadorPenalizaciones:
    """
    Explica detalladamente las penalizaciones del fitness.
    Permite entender por qué un horario tiene cierto puntaje.
    """
    
    def __init__(self, mascaras: MascarasOptimizadas):
        self.mascaras = mascaras
        self.config_fitness = ConfiguracionFitness()
    
    def explicar_fitness_completo(
        self, 
        cromosoma: Dict[Tuple[int, str, int], Tuple[int, int]]
    ) -> ExplicacionFitness:
        """
        Explica completamente el fitness de un horario.
        
        Args:
            cromosoma: Horario a analizar
        
        Returns:
            ExplicacionFitness con análisis detallado
        """
        # Calcular fitness general
        resultado_fitness = calcular_fitness_unificado(cromosoma, self.mascaras, self.config_fitness)
        
        # Analizar penalizaciones por entidad
        penalizaciones_por_entidad = []
        
        # Analizar por curso
        penalizaciones_curso = self._analizar_penalizaciones_por_curso(cromosoma)
        penalizaciones_por_entidad.extend(penalizaciones_curso)
        
        # Analizar por profesor
        penalizaciones_profesor = self._analizar_penalizaciones_por_profesor(cromosoma)
        penalizaciones_por_entidad.extend(penalizaciones_profesor)
        
        # Crear resumen por tipo de penalización
        resumen_por_tipo = self._crear_resumen_por_tipo(penalizaciones_por_entidad)
        
        # Generar recomendaciones
        recomendaciones = self._generar_recomendaciones(penalizaciones_por_entidad, resultado_fitness)
        
        return ExplicacionFitness(
            fitness_total=resultado_fitness.fitness_total,
            penalizacion_total=resultado_fitness.fitness_total * -1,  # Convertir a positivo
            penalizaciones_por_entidad=penalizaciones_por_entidad,
            resumen_por_tipo=resumen_por_tipo,
            recomendaciones=recomendaciones
        )
    
    def _analizar_penalizaciones_por_curso(
        self, 
        cromosoma: Dict[Tuple[int, str, int], Tuple[int, int]]
    ) -> List[PenalizacionDetallada]:
        """Analiza penalizaciones específicas por curso"""
        from .models import Curso
        
        penalizaciones = []
        
        # Agrupar asignaciones por curso
        asignaciones_por_curso = {}
        for (curso_id, dia, bloque), (materia_id, profesor_id) in cromosoma.items():
            if curso_id not in asignaciones_por_curso:
                asignaciones_por_curso[curso_id] = []
            asignaciones_por_curso[curso_id].append({
                'dia': dia,
                'bloque': bloque,
                'materia_id': materia_id,
                'profesor_id': profesor_id
            })
        
        # Analizar cada curso
        for curso_id, asignaciones in asignaciones_por_curso.items():
            try:
                curso = Curso.objects.get(id=curso_id)
                penalizacion = self._calcular_penalizacion_curso(curso, asignaciones)
                penalizaciones.append(penalizacion)
            except Curso.DoesNotExist:
                continue
        
        return penalizaciones
    
    def _analizar_penalizaciones_por_profesor(
        self, 
        cromosoma: Dict[Tuple[int, str, int], Tuple[int, int]]
    ) -> List[PenalizacionDetallada]:
        """Analiza penalizaciones específicas por profesor"""
        from .models import Profesor
        
        penalizaciones = []
        
        # Agrupar asignaciones por profesor
        asignaciones_por_profesor = {}
        for (curso_id, dia, bloque), (materia_id, profesor_id) in cromosoma.items():
            if profesor_id not in asignaciones_por_profesor:
                asignaciones_por_profesor[profesor_id] = []
            asignaciones_por_profesor[profesor_id].append({
                'dia': dia,
                'bloque': bloque,
                'curso_id': curso_id,
                'materia_id': materia_id
            })
        
        # Analizar cada profesor
        for profesor_id, asignaciones in asignaciones_por_profesor.items():
            try:
                profesor = Profesor.objects.get(id=profesor_id)
                penalizacion = self._calcular_penalizacion_profesor(profesor, asignaciones)
                penalizaciones.append(penalizacion)
            except Profesor.DoesNotExist:
                continue
        
        return penalizaciones
    
    def _calcular_penalizacion_curso(
        self, 
        curso: 'Curso', 
        asignaciones: List[Dict]
    ) -> PenalizacionDetallada:
        """Calcula penalizaciones específicas para un curso"""
        contribuciones = {
            'huecos': 0.0,
            'primeras_ultimas': 0.0,
            'balance_dia': 0.0,
            'bloques_semana': 0.0
        }
        
        detalles = {
            'huecos_detectados': [],
            'bloques_primeras_ultimas': [],
            'distribucion_por_dia': {},
            'bloques_por_materia': {}
        }
        
        # 1. Calcular huecos
        huecos, detalles_huecos = self._calcular_huecos_curso(asignaciones)
        contribuciones['huecos'] = huecos * self.config_fitness.peso_huecos
        detalles['huecos_detectados'] = detalles_huecos
        
        # 2. Calcular primeras/últimas franjas
        primeras_ultimas, detalles_primeras = self._calcular_primeras_ultimas_curso(asignaciones)
        contribuciones['primeras_ultimas'] = primeras_ultimas * self.config_fitness.peso_primeras_ultimas
        detalles['bloques_primeras_ultimas'] = detalles_primeras
        
        # 3. Calcular balance por día
        balance_dia, detalles_balance = self._calcular_balance_dia_curso(asignaciones)
        contribuciones['balance_dia'] = balance_dia * self.config_fitness.peso_balance_dia
        detalles['distribucion_por_dia'] = detalles_balance
        
        # 4. Calcular bloques por semana
        bloques_semana, detalles_bloques = self._calcular_bloques_semana_curso(curso, asignaciones)
        contribuciones['bloques_semana'] = bloques_semana * self.config_fitness.peso_bloques_semana
        detalles['bloques_por_materia'] = detalles_bloques
        
        penalizacion_total = sum(contribuciones.values())
        
        return PenalizacionDetallada(
            entidad_id=curso.id,
            entidad_tipo='curso',
            entidad_nombre=curso.nombre,
            penalizacion_total=penalizacion_total,
            contribuciones=contribuciones,
            detalles=detalles
        )
    
    def _calcular_penalizacion_profesor(
        self, 
        profesor: 'Profesor', 
        asignaciones: List[Dict]
    ) -> PenalizacionDetallada:
        """Calcula penalizaciones específicas para un profesor"""
        contribuciones = {
            'primeras_ultimas': 0.0,
            'balance_dia': 0.0,
            'distribucion_equitativa': 0.0
        }
        
        detalles = {
            'bloques_primeras_ultimas': [],
            'distribucion_por_dia': {},
            'carga_por_dia': {}
        }
        
        # 1. Calcular primeras/últimas franjas
        primeras_ultimas, detalles_primeras = self._calcular_primeras_ultimas_profesor(asignaciones)
        contribuciones['primeras_ultimas'] = primeras_ultimas * self.config_fitness.peso_primeras_ultimas
        detalles['bloques_primeras_ultimas'] = detalles_primeras
        
        # 2. Calcular balance por día
        balance_dia, detalles_balance = self._calcular_balance_dia_profesor(asignaciones)
        contribuciones['balance_dia'] = balance_dia * self.config_fitness.peso_balance_dia
        detalles['distribucion_por_dia'] = detalles_balance
        
        # 3. Calcular distribución equitativa
        distribucion_equitativa, detalles_distribucion = self._calcular_distribucion_equitativa_profesor(asignaciones)
        contribuciones['distribucion_equitativa'] = distribucion_equitativa * 2.0  # Peso adicional
        detalles['carga_por_dia'] = detalles_distribucion
        
        penalizacion_total = sum(contribuciones.values())
        
        return PenalizacionDetallada(
            entidad_id=profesor.id,
            entidad_tipo='profesor',
            entidad_nombre=profesor.nombre,
            penalizacion_total=penalizacion_total,
            contribuciones=contribuciones,
            detalles=detalles
        )
    
    def _calcular_huecos_curso(
        self, 
        asignaciones: List[Dict]
    ) -> Tuple[float, List[Dict]]
    ):
        """Calcula huecos en el horario de un curso"""
        # Agrupar por día
        asignaciones_por_dia = {}
        for asignacion in asignaciones:
            dia = asignacion['dia']
            if dia not in asignaciones_por_dia:
                asignaciones_por_dia[dia] = []
            asignaciones_por_dia[dia].append(asignacion['bloque'])
        
        huecos_totales = 0
        detalles_huecos = []
        
        for dia, bloques in asignaciones_por_dia.items():
            if len(bloques) > 1:
                bloques_ordenados = sorted(bloques)
                huecos_dia = 0
                
                for i in range(len(bloques_ordenados) - 1):
                    hueco = bloques_ordenados[i + 1] - bloques_ordenados[i] - 1
                    if hueco > 0:
                        huecos_dia += hueco
                        detalles_huecos.append({
                            'dia': dia,
                            'bloque_inicio': bloques_ordenados[i],
                            'bloque_fin': bloques_ordenados[i + 1],
                            'huecos': hueco
                        })
                
                huecos_totales += huecos_dia
        
        return float(huecos_totales), detalles_huecos
    
    def _calcular_primeras_ultimas_curso(
        self, 
        asignaciones: List[Dict]
    ) -> Tuple[float, List[Dict]]
    ):
        """Calcula penalización por bloques en primeras/últimas franjas"""
        umbral = self.config_fitness.umbral_primeras_ultimas
        bloques_primeras_ultimas = []
        
        for asignacion in asignaciones:
            bloque = asignacion['bloque']
            dia = asignacion['dia']
            
            # Primera franja (bloques 1-2)
            if 1 <= bloque <= umbral:
                bloques_primeras_ultimas.append({
                    'dia': dia,
                    'bloque': bloque,
                    'tipo': 'primera_franja',
                    'materia_id': asignacion['materia_id']
                })
            
            # Última franja (últimos 2 bloques)
            elif bloque > self.mascaras.bloques_por_dia - umbral:
                bloques_primeras_ultimas.append({
                    'dia': dia,
                    'bloque': bloque,
                    'tipo': 'ultima_franja',
                    'materia_id': asignacion['materia_id']
                })
        
        return float(len(bloques_primeras_ultimas)), bloques_primeras_ultimas
    
    def _calcular_balance_dia_curso(
        self, 
        asignaciones: List[Dict]
    ) -> Tuple[float, Dict[str, int]]
    :
        """Calcula balance de materias por día para un curso"""
        # Contar materias por día
        materias_por_dia = {}
        for asignacion in asignaciones:
            dia = asignacion['dia']
            materias_por_dia[dia] = materias_por_dia.get(dia, 0) + 1
        
        if len(materias_por_dia) <= 1:
            return 0.0, materias_por_dia
        
        # Calcular desviación estándar
        valores = list(materias_por_dia.values())
        desviacion = float(np.std(valores))
        
        return desviacion, materias_por_dia
    
    def _calcular_bloques_semana_curso(
        self, 
        curso: 'Curso', 
        asignaciones: List[Dict]
    ) -> Tuple[float, Dict[str, Any]]
    :
        """Calcula desvío de bloques por semana requeridos"""
        from .models import MateriaGrado
        
        # Obtener bloques requeridos por materia
        bloques_requeridos = {}
        for mg in MateriaGrado.objects.filter(grado=curso.grado):
            bloques_requeridos[mg.materia_id] = mg.materia.bloques_por_semana
        
        # Contar bloques asignados por materia
        bloques_asignados = {}
        for asignacion in asignaciones:
            materia_id = asignacion['materia_id']
            bloques_asignados[materia_id] = bloques_asignados.get(materia_id, 0) + 1
        
        # Calcular desvío total
        desvio_total = 0.0
        detalles = {
            'materias': {},
            'desvio_total': 0.0
        }
        
        for materia_id, requeridos in bloques_requeridos.items():
            asignados = bloques_asignados.get(materia_id, 0)
            desvio = abs(asignados - requeridos)
            desvio_total += desvio
            
            detalles['materias'][materia_id] = {
                'requeridos': requeridos,
                'asignados': asignados,
                'desvio': desvio
            }
        
        detalles['desvio_total'] = desvio_total
        
        return desvio_total, detalles
    
    def _calcular_primeras_ultimas_profesor(
        self, 
        asignaciones: List[Dict]
    ) -> Tuple[float, List[Dict]]
    :
        """Calcula penalización por bloques en primeras/últimas franjas para un profesor"""
        umbral = self.config_fitness.umbral_primeras_ultimas
        bloques_primeras_ultimas = []
        
        for asignacion in asignaciones:
            bloque = asignacion['bloque']
            dia = asignacion['dia']
            
            # Primera franja (bloques 1-2)
            if 1 <= bloque <= umbral:
                bloques_primeras_ultimas.append({
                    'dia': dia,
                    'bloque': bloque,
                    'tipo': 'primera_franja',
                    'curso_id': asignacion['curso_id'],
                    'materia_id': asignacion['materia_id']
                })
            
            # Última franja (últimos 2 bloques)
            elif bloque > self.mascaras.bloques_por_dia - umbral:
                bloques_primeras_ultimas.append({
                    'dia': dia,
                    'bloque': bloque,
                    'tipo': 'ultima_franja',
                    'curso_id': asignacion['curso_id'],
                    'materia_id': asignacion['materia_id']
                })
        
        return float(len(bloques_primeras_ultimas)), bloques_primeras_ultimas
    
    def _calcular_balance_dia_profesor(
        self, 
        asignaciones: List[Dict]
    ) -> Tuple[float, Dict[str, int]]
    :
        """Calcula balance de carga por día para un profesor"""
        # Contar asignaciones por día
        asignaciones_por_dia = {}
        for asignacion in asignaciones:
            dia = asignacion['dia']
            asignaciones_por_dia[dia] = asignaciones_por_dia.get(dia, 0) + 1
        
        if len(asignaciones_por_dia) <= 1:
            return 0.0, asignaciones_por_dia
        
        # Calcular desviación estándar
        valores = list(asignaciones_por_dia.values())
        desviacion = float(np.std(valores))
        
        return desviacion, asignaciones_por_dia
    
    def _calcular_distribucion_equitativa_profesor(
        self, 
        asignaciones: List[Dict]
    ) -> Tuple[float, Dict[str, Any]]
    :
        """Calcula penalización por distribución no equitativa de carga"""
        # Agrupar por día
        carga_por_dia = {}
        for asignacion in asignaciones:
            dia = asignacion['dia']
            carga_por_dia[dia] = carga_por_dia.get(dia, 0) + 1
        
        if len(carga_por_dia) <= 1:
            return 0.0, carga_por_dia
        
        # Calcular desviación estándar
        valores = list(carga_por_dia.values())
        desviacion = float(np.std(valores))
        
        # Penalización adicional si hay días muy sobrecargados
        penalizacion_adicional = 0.0
        max_carga = max(valores)
        min_carga = min(valores)
        
        if max_carga > min_carga * 2:  # Día con más del doble de carga
            penalizacion_adicional = (max_carga - min_carga) * 0.5
        
        return desviacion + penalizacion_adicional, {
            'carga_por_dia': carga_por_dia,
            'max_carga': max_carga,
            'min_carga': min_carga,
            'penalizacion_adicional': penalizacion_adicional
        }
    
    def _crear_resumen_por_tipo(
        self, 
        penalizaciones: List[PenalizacionDetallada]
    ) -> Dict[str, Dict[str, Any]]:
        """Crea resumen agregado por tipo de penalización"""
        resumen = {
            'huecos': {'total': 0.0, 'entidades_afectadas': []},
            'primeras_ultimas': {'total': 0.0, 'entidades_afectadas': []},
            'balance_dia': {'total': 0.0, 'entidades_afectadas': []},
            'bloques_semana': {'total': 0.0, 'entidades_afectadas': []},
            'distribucion_equitativa': {'total': 0.0, 'entidades_afectadas': []}
        }
        
        for penalizacion in penalizaciones:
            for tipo, valor in penalizacion.contribuciones.items():
                if tipo in resumen:
                    resumen[tipo]['total'] += valor
                    if valor > 0:
                        resumen[tipo]['entidades_afectadas'].append({
                            'id': penalizacion.entidad_id,
                            'tipo': penalizacion.entidad_tipo,
                            'nombre': penalizacion.entidad_nombre,
                            'valor': valor
                        })
        
        return resumen
    
    def _generar_recomendaciones(
        self, 
        penalizaciones: List[PenalizacionDetallada],
        resultado_fitness: Any
    ) -> List[str]:
        """Genera recomendaciones específicas para mejorar el horario"""
        recomendaciones = []
        
        # Analizar penalizaciones por tipo
        resumen = self._crear_resumen_por_tipo(penalizaciones)
        
        # Recomendaciones por huecos
        if resumen['huecos']['total'] > 50:
            recomendaciones.append("🔴 ALTO: Muchos huecos en horarios de cursos. Considerar reorganizar materias para reducir espacios vacíos.")
        
        # Recomendaciones por primeras/últimas franjas
        if resumen['primeras_ultimas']['total'] > 30:
            recomendaciones.append("🟡 MEDIO: Muchas materias en bloques 1-2 o últimos bloques. Revisar preferencias de horarios.")
        
        # Recomendaciones por balance diario
        if resumen['balance_dia']['total'] > 20:
            recomendaciones.append("🟡 MEDIO: Distribución desigual de materias por día. Buscar mejor equilibrio.")
        
        # Recomendaciones por bloques por semana
        if resumen['bloques_semana']['total'] > 25:
            recomendaciones.append("🔴 ALTO: Desvío significativo en bloques por semana requeridos. Verificar plan de estudios.")
        
        # Recomendaciones por distribución equitativa de profesores
        if resumen['distribucion_equitativa']['total'] > 15:
            recomendaciones.append("🟡 MEDIO: Carga de trabajo desigual entre días para algunos profesores. Buscar mejor distribución.")
        
        # Recomendaciones generales
        if resultado_fitness.num_solapes > 0:
            recomendaciones.append("❌ CRÍTICO: Eliminar todos los solapes antes de optimizar restricciones blandas.")
        
        if not recomendaciones:
            recomendaciones.append("✅ El horario actual tiene buena calidad. Solo ajustes menores recomendados.")
        
        return recomendaciones

def crear_explicador_penalizaciones(mascaras: MascarasOptimizadas) -> ExplicadorPenalizaciones:
    """Función de conveniencia para crear un explicador de penalizaciones"""
    return ExplicadorPenalizaciones(mascaras)

def explicar_penalizaciones_curso(
    curso_id: int,
    cromosoma: Dict[Tuple[int, str, int], Tuple[int, int]],
    mascaras: MascarasOptimizadas
) -> PenalizacionDetallada:
    """
    Explica penalizaciones específicas para un curso.
    
    Args:
        curso_id: ID del curso a analizar
        cromosoma: Horario completo
        mascaras: Máscaras optimizadas
    
    Returns:
        PenalizacionDetallada para el curso
    """
    explicador = crear_explicador_penalizaciones(mascaras)
    
    # Filtrar asignaciones del curso
    asignaciones_curso = {}
    for (c_id, dia, bloque), (materia_id, profesor_id) in cromosoma.items():
        if c_id == curso_id:
            asignaciones_curso[(c_id, dia, bloque)] = (materia_id, profesor_id)
    
    # Calcular penalizaciones
    from .models import Curso
    curso = Curso.objects.get(id=curso_id)
    asignaciones = [
        {
            'dia': dia,
            'bloque': bloque,
            'materia_id': materia_id,
            'profesor_id': profesor_id
        }
        for (_, dia, bloque), (materia_id, profesor_id) in asignaciones_curso.items()
    ]
    
    return explicador._calcular_penalizacion_curso(curso, asignaciones)

def explicar_penalizaciones_profesor(
    profesor_id: int,
    cromosoma: Dict[Tuple[int, str, int], Tuple[int, int]],
    mascaras: MascarasOptimizadas
) -> PenalizacionDetallada:
    """
    Explica penalizaciones específicas para un profesor.
    
    Args:
        profesor_id: ID del profesor a analizar
        cromosoma: Horario completo
        mascaras: Máscaras optimizadas
    
    Returns:
        PenalizacionDetallada para el profesor
    """
    explicador = crear_explicador_penalizaciones(mascaras)
    
    # Filtrar asignaciones del profesor
    asignaciones_profesor = {}
    for (curso_id, dia, bloque), (materia_id, p_id) in cromosoma.items():
        if p_id == profesor_id:
            asignaciones_profesor[(curso_id, dia, bloque)] = (materia_id, p_id)
    
    # Calcular penalizaciones
    from .models import Profesor
    profesor = Profesor.objects.get(id=profesor_id)
    asignaciones = [
        {
            'dia': dia,
            'bloque': bloque,
            'curso_id': curso_id,
            'materia_id': materia_id
        }
        for (curso_id, dia, bloque), (materia_id, _) in asignaciones_profesor.items()
    ]
    
    return explicador._calcular_penalizacion_profesor(profesor, asignaciones) 