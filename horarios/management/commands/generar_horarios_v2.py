#!/usr/bin/env python3
"""
Comando para generar horarios con sistema v2.
Implementa reglas duras, validaciones previas y lógica demand-first.
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
import json
import time
import logging

from horarios.models import Horario
from horarios.domain.validators.validador_precondiciones import ValidadorPrecondiciones
from horarios.application.services.generador_demand_first import GeneradorDemandFirst
from horarios.infrastructure.adapters.sistema_reportes import SistemaReportes

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Genera horarios usando sistema v2 con reglas duras y lógica demand-first'

    def add_arguments(self, parser):
        parser.add_argument(
            '--semilla',
            type=int,
            default=None,
            help='Semilla para reproducibilidad (opcional)'
        )
        
        parser.add_argument(
            '--max-iteraciones',
            type=int,
            default=1000,
            help='Máximo número de iteraciones para mejora'
        )
        
        parser.add_argument(
            '--paciencia',
            type=int,
            default=50,
            help='Número de iteraciones sin mejora antes de parar'
        )
        
        parser.add_argument(
            '--validar-solo',
            action='store_true',
            help='Solo validar precondiciones sin generar'
        )
        
        parser.add_argument(
            '--reporte-solo',
            action='store_true',
            help='Solo generar reporte del estado actual'
        )
        
        parser.add_argument(
            '--limpiar-antes',
            action='store_true',
            help='Limpiar horarios existentes antes de generar'
        )
        
        parser.add_argument(
            '--guardar-reporte',
            type=str,
            default=None,
            help='Archivo para guardar reporte detallado (JSON)'
        )
        
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Mostrar información detallada'
        )

    def handle(self, *args, **options):
        """Maneja la ejecución del comando"""
        
        # Configurar logging
        if options['verbose']:
            logging.basicConfig(level=logging.DEBUG)
        else:
            logging.basicConfig(level=logging.INFO)
        
        self.stdout.write(self.style.SUCCESS('🚀 Iniciando generación de horarios v2'))
        
        try:
            # 1. Validar precondiciones
            resultado_validacion = self._validar_precondiciones(options)
            if not resultado_validacion and not options['reporte_solo']:
                return
            
            # 2. Generar reporte si se solicita
            if options['reporte_solo']:
                self._generar_reporte_solo(options)
                return
            
            # 3. Validar solo si se solicita
            if options['validar_solo']:
                return
            
            # 4. Limpiar horarios existentes si se solicita
            if options['limpiar_antes']:
                self._limpiar_horarios_existentes()
            
            # 5. Generar horarios
            resultado_generacion = self._generar_horarios(options)
            
            # 6. Guardar resultados
            if resultado_generacion['exito']:
                self._guardar_horarios(resultado_generacion['horarios'])
                self._mostrar_resultado_exitoso(resultado_generacion)
            else:
                self._mostrar_resultado_fallido(resultado_generacion)
            
            # 7. Generar reporte final
            self._generar_reporte_final(options, resultado_generacion)
            
        except Exception as e:
            logger.exception("Error durante la generación")
            raise CommandError(f'Error durante la generación: {str(e)}')

    def _validar_precondiciones(self, options) -> bool:
        """Valida precondiciones antes de generar"""
        self.stdout.write('📋 Validando precondiciones...')
        
        validador = ValidadorPrecondiciones()
        resultado = validador.validar_factibilidad_completa()
        
        if resultado.es_factible:
            self.stdout.write(self.style.SUCCESS('✅ Precondiciones cumplidas'))
            if options['verbose']:
                self.stdout.write(f'   • {resultado.estadisticas["total_problemas"]} advertencias detectadas')
        else:
            self.stdout.write(self.style.ERROR('❌ Precondiciones NO cumplidas'))
            self.stdout.write(f'   • {resultado.estadisticas["problemas_criticos"]} problemas críticos')
            
            # Mostrar problemas principales
            for problema in resultado.problemas[:5]:
                if problema.tipo in ['deficit_semanal', 'sin_profesores_relleno']:
                    self.stdout.write(f'   🚨 {problema.descripcion}')
                    if problema.solucion_sugerida:
                        self.stdout.write(f'      💡 {problema.solucion_sugerida}')
            
            if len(resultado.problemas) > 5:
                self.stdout.write(f'   ... y {len(resultado.problemas) - 5} problemas más')
            
            self.stdout.write('\n' + resultado.reporte_detallado)
        
        return resultado.es_factible

    def _generar_reporte_solo(self, options):
        """Genera solo reporte del estado actual"""
        self.stdout.write('📊 Generando reporte del estado actual...')
        
        sistema_reportes = SistemaReportes()
        reporte = sistema_reportes.generar_reporte_completo()
        
        # Mostrar resumen
        calidad = reporte['calidad_global']
        self.stdout.write(f'\n🎯 CALIDAD GLOBAL: {calidad["nivel"]} ({calidad["puntuacion"]}/100)')
        self.stdout.write(f'   {calidad["descripcion"]}')
        
        estadisticas = reporte['estadisticas_generales']
        ocupacion = estadisticas['ocupacion_global']
        self.stdout.write(f'\n📈 OCUPACIÓN: {ocupacion["slots_ocupados"]}/{ocupacion["slots_posibles"]} slots ({ocupacion["porcentaje"]:.1f}%)')
        
        # Mostrar alertas críticas
        alertas_criticas = [a for a in reporte['alertas_previas'] if a.severidad == 'critica']
        if alertas_criticas:
            self.stdout.write(f'\n🚨 ALERTAS CRÍTICAS ({len(alertas_criticas)}):')
            for alerta in alertas_criticas[:3]:
                self.stdout.write(f'   • {alerta.descripcion}')
        
        # Guardar reporte completo si se solicita
        if options['guardar_reporte']:
            self._guardar_reporte_json(reporte, options['guardar_reporte'])

    def _limpiar_horarios_existentes(self):
        """Limpia horarios existentes"""
        self.stdout.write('🧹 Limpiando horarios existentes...')
        
        count = Horario.objects.count()
        Horario.objects.all().delete()
        
        self.stdout.write(self.style.WARNING(f'   Eliminados {count} horarios'))

    def _generar_horarios(self, options) -> dict:
        """Genera horarios usando el sistema demand-first"""
        self.stdout.write('⚙️ Generando horarios con lógica demand-first...')
        
        generador = GeneradorDemandFirst()
        
        # Parámetros de generación
        parametros = {
            'max_iteraciones': options['max_iteraciones'],
            'paciencia': options['paciencia']
        }
        
        inicio_tiempo = time.time()
        resultado = generador.generar_horarios(
            semilla=options['semilla'],
            **parametros
        )
        tiempo_total = time.time() - inicio_tiempo
        
        resultado['tiempo_comando'] = tiempo_total
        
        return resultado

    def _guardar_horarios(self, horarios_lista: list):
        """Guarda horarios en la base de datos"""
        self.stdout.write('💾 Guardando horarios en base de datos...')
        
        with transaction.atomic():
            # Limpiar horarios existentes
            Horario.objects.all().delete()
            
            # Crear nuevos horarios
            horarios_objetos = []
            
            for h in horarios_lista:
                try:
                    from horarios.models import Curso, Materia, Profesor, Aula
                    
                    curso = Curso.objects.get(id=h['curso_id'])
                    materia = Materia.objects.get(id=h['materia_id'])
                    profesor = Profesor.objects.get(id=h['profesor_id'])
                    
                    aula = None
                    if h.get('aula_id'):
                        aula = Aula.objects.get(id=h['aula_id'])
                    
                    horario = Horario(
                        curso=curso,
                        materia=materia,
                        profesor=profesor,
                        dia=h['dia'],
                        bloque=h['bloque'],
                        aula=aula
                    )
                    
                    horarios_objetos.append(horario)
                    
                except Exception as e:
                    logger.warning(f"Error creando horario: {e}")
                    continue
            
            # Guardar en lote
            Horario.objects.bulk_create(horarios_objetos)
            
            self.stdout.write(self.style.SUCCESS(f'   ✅ Guardados {len(horarios_objetos)} horarios'))

    def _mostrar_resultado_exitoso(self, resultado: dict):
        """Muestra resultado exitoso"""
        self.stdout.write(self.style.SUCCESS('\n🎉 ¡Generación exitosa!'))
        
        estadisticas = resultado['estadisticas']
        self.stdout.write(f'   📊 Slots generados: {estadisticas["slots_generados"]}')
        self.stdout.write(f'   📚 Cursos completos: {estadisticas["cursos_completos"]}')
        self.stdout.write(f'   ⏱️  Tiempo total: {estadisticas["tiempo_total"]:.2f}s')
        self.stdout.write(f'   🎯 Calidad: {resultado["calidad"]:.3f}')
        
        # Mostrar validación final
        validacion = resultado['validacion_final']
        if validacion.es_valido:
            self.stdout.write(self.style.SUCCESS('   ✅ Todas las reglas duras cumplidas'))
        else:
            self.stdout.write(self.style.ERROR(f'   ❌ {len(validacion.violaciones)} violaciones detectadas'))

    def _mostrar_resultado_fallido(self, resultado: dict):
        """Muestra resultado fallido"""
        self.stdout.write(self.style.ERROR('\n❌ Generación fallida'))
        self.stdout.write(f'   Razón: {resultado.get("razon", "Desconocida")}')
        
        if 'factibilidad' in resultado:
            factibilidad = resultado['factibilidad']
            self.stdout.write(f'   Problemas críticos: {factibilidad.estadisticas["problemas_criticos"]}')

        if 'validacion_final' in resultado:
            validacion = resultado['validacion_final']
            if hasattr(validacion, 'es_valido') and not validacion.es_valido:
                violaciones = getattr(validacion, 'violaciones', [])
                self.stdout.write(self.style.ERROR(f'   Violaciones detectadas ({len(violaciones)}):'))
                for violacion in violaciones[:10]:
                    self.stdout.write(f'     - {violacion}')
            elif isinstance(validacion, dict) and not validacion.get('es_valido'):
                 errores = validacion.get('errores', [])
                 self.stdout.write(self.style.ERROR(f'   Errores detectados ({len(errores)}):'))
                 for error in errores[:10]:
                     self.stdout.write(f'     - {error}')

    def _generar_reporte_final(self, options, resultado_generacion: dict):
        """Genera reporte final completo"""
        if not options['guardar_reporte']:
            return
        
        self.stdout.write('📋 Generando reporte final...')
        
        sistema_reportes = SistemaReportes()
        reporte = sistema_reportes.generar_reporte_completo()
        
        # Agregar información de la generación
        reporte['generacion'] = {
            'parametros': {
                'semilla': options['semilla'],
                'max_iteraciones': options['max_iteraciones'],
                'paciencia': options['paciencia']
            },
            'resultado': resultado_generacion
        }
        
        self._guardar_reporte_json(reporte, options['guardar_reporte'])

    def _guardar_reporte_json(self, reporte: dict, archivo: str):
        """Guarda reporte en archivo JSON"""
        try:
            # Convertir objetos no serializables
            reporte_serializable = self._hacer_serializable(reporte)
            
            with open(archivo, 'w', encoding='utf-8') as f:
                json.dump(reporte_serializable, f, indent=2, ensure_ascii=False)
            
            self.stdout.write(self.style.SUCCESS(f'   📄 Reporte guardado en: {archivo}'))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'   ❌ Error guardando reporte: {e}'))

    def _hacer_serializable(self, obj):
        """Convierte objeto a formato serializable JSON"""
        if hasattr(obj, '__dict__'):
            return {k: self._hacer_serializable(v) for k, v in obj.__dict__.items()}
        elif isinstance(obj, dict):
            return {k: self._hacer_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return [self._hacer_serializable(item) for item in obj]
        elif isinstance(obj, (str, int, float, bool)) or obj is None:
            return obj
        else:
            return str(obj) 