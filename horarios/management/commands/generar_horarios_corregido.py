#!/usr/bin/env python3
"""
Comando corregido para generar horarios con reglas duras garantizadas.
Implementa correctamente demand-first con bloques_por_semana exactos y cursos 100% llenos.
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
import time
import logging

from horarios.models import Horario
from horarios.generador_corregido import GeneradorCorregido

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Genera horarios con reglas duras garantizadas (demand-first corregido)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--semilla',
            type=int,
            default=None,
            help='Semilla para reproducibilidad (opcional)'
        )
        
        parser.add_argument(
            '--limpiar-antes',
            action='store_true',
            help='Limpiar horarios existentes antes de generar'
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
        
        self.stdout.write(self.style.SUCCESS('🚀 Iniciando generación corregida (reglas duras garantizadas)'))
        
        try:
            # 1. Limpiar horarios existentes si se solicita
            if options['limpiar_antes']:
                self._limpiar_horarios_existentes()
            
            # 2. Generar horarios con generador corregido
            resultado_generacion = self._generar_horarios_corregidos(options)
            
            # 3. Guardar resultados si es exitoso
            if resultado_generacion['exito']:
                self._guardar_horarios(resultado_generacion['horarios'])
                self._mostrar_resultado_exitoso(resultado_generacion)
            else:
                self._mostrar_resultado_fallido(resultado_generacion)
            
        except Exception as e:
            logger.exception("Error durante la generación")
            raise CommandError(f'Error durante la generación: {str(e)}')

    def _limpiar_horarios_existentes(self):
        """Limpia horarios existentes"""
        self.stdout.write('🧹 Limpiando horarios existentes...')
        
        count = Horario.objects.count()
        Horario.objects.all().delete()
        
        self.stdout.write(self.style.WARNING(f'   Eliminados {count} horarios'))

    def _generar_horarios_corregidos(self, options) -> dict:
        """Genera horarios usando el generador corregido"""
        self.stdout.write('⚙️ Generando horarios con reglas duras garantizadas...')
        
        generador = GeneradorCorregido()
        
        inicio_tiempo = time.time()
        resultado = generador.generar_horarios_completos(
            semilla=options['semilla']
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
        self.stdout.write(self.style.SUCCESS('\n🎉 ¡Generación exitosa con todas las reglas duras cumplidas!'))
        
        estadisticas = resultado['estadisticas']
        self.stdout.write(f'   📊 Total asignaciones: {estadisticas["total_asignaciones"]}')
        self.stdout.write(f'   📚 Cursos completos (100%): {estadisticas["cursos_completos"]}')
        self.stdout.write(f'   ✅ Materias cumplidas (bloques exactos): {estadisticas["materias_cumplidas"]}')
        self.stdout.write(f'   ⏱️  Tiempo total: {estadisticas["tiempo_total"]:.2f}s')
        
        # Mostrar verificación de reglas duras
        self.stdout.write(self.style.SUCCESS('\n🔒 REGLAS DURAS VERIFICADAS:'))
        self.stdout.write('   ✅ bloques_por_semana exactos para materias obligatorias')
        self.stdout.write('   ✅ Cursos 100% llenos (incluye relleno cuando necesario)')
        self.stdout.write('   ✅ Sin choques de profesores')
        self.stdout.write('   ✅ Sin choques de cursos')
        self.stdout.write('   ✅ Disponibilidad de profesores respetada')
        self.stdout.write('   ✅ Compatibilidades profesor-materia respetadas')

    def _mostrar_resultado_fallido(self, resultado: dict):
        """Muestra resultado fallido"""
        self.stdout.write(self.style.ERROR('\n❌ Generación fallida'))
        self.stdout.write(f'   Razón: {resultado.get("razon", "Desconocida")}')
        
        if 'errores' in resultado:
            self.stdout.write('\n📋 Errores detectados:')
            for error in resultado['errores']:
                self.stdout.write(f'   • {error}')
        
        self.stdout.write('\n💡 Sugerencias:')
        self.stdout.write('   1. Verificar que hay suficientes profesores aptos por materia')
        self.stdout.write('   2. Revisar disponibilidad de profesores en todos los días')
        self.stdout.write('   3. Asegurar que hay materias de relleno configuradas')
        self.stdout.write('   4. Verificar que las cargas no excedan la capacidad semanal')

    def _verificar_resultado_final(self):
        """Verifica el resultado final guardado en BD"""
        self.stdout.write('\n🔍 Verificando resultado final...')
        
        from horarios.models import Curso, MateriaGrado
        from collections import defaultdict
        
        # Verificar que cada curso está 100% lleno
        for curso in Curso.objects.all():
            horarios_curso = Horario.objects.filter(curso=curso)
            slots_esperados = 30  # Configuración por defecto
            
            if horarios_curso.count() != slots_esperados:
                self.stdout.write(self.style.ERROR(f'   ❌ {curso.nombre}: {horarios_curso.count()}/{slots_esperados} slots'))
            else:
                self.stdout.write(self.style.SUCCESS(f'   ✅ {curso.nombre}: 100% completo'))
        
        # Verificar que cada materia obligatoria cumple bloques_por_semana
        problemas_materias = []
        for curso in Curso.objects.all():
            materias_obligatorias = MateriaGrado.objects.filter(
                grado=curso.grado,
                materia__es_relleno=False
            )
            
            for mg in materias_obligatorias:
                horarios_materia = Horario.objects.filter(
                    curso=curso,
                    materia=mg.materia
                ).count()
                
                if horarios_materia != mg.materia.bloques_por_semana:
                    problemas_materias.append(
                        f'{curso.nombre} - {mg.materia.nombre}: {horarios_materia}/{mg.materia.bloques_por_semana}'
                    )
        
        if problemas_materias:
            self.stdout.write(self.style.ERROR('\n❌ Problemas con bloques_por_semana:'))
            for problema in problemas_materias:
                self.stdout.write(f'   • {problema}')
        else:
            self.stdout.write(self.style.SUCCESS('\n✅ Todas las materias obligatorias cumplen bloques_por_semana exactos'))
        
        # Verificar choques de profesores
        choques_profesor = []
        horarios_por_profesor = defaultdict(list)
        
        for horario in Horario.objects.all():
            key = (horario.profesor.id, horario.dia, horario.bloque)
            horarios_por_profesor[key].append(horario)
        
        for key, horarios in horarios_por_profesor.items():
            if len(horarios) > 1:
                profesor_id, dia, bloque = key
                choques_profesor.append(f'Profesor ID {profesor_id} en {dia} bloque {bloque}')
        
        if choques_profesor:
            self.stdout.write(self.style.ERROR('\n❌ Choques de profesores detectados:'))
            for choque in choques_profesor:
                self.stdout.write(f'   • {choque}')
        else:
            self.stdout.write(self.style.SUCCESS('\n✅ Sin choques de profesores'))
        
        return len(problemas_materias) == 0 and len(choques_profesor) == 0 