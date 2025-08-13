from django.core.management.base import BaseCommand
from typing import Dict, List, Tuple
import csv
from collections import defaultdict

from horarios.models import (
    ConfiguracionColegio, BloqueHorario, Curso,
    Profesor, Materia, MateriaGrado, MateriaProfesor,
    DisponibilidadProfesor, Aula
)

class Command(BaseCommand):
    help = "🔍 Diagnóstico completo del sistema de horarios"

    def add_arguments(self, parser):
        parser.add_argument("--csv", action="store_true", help="Exportar resultados a CSV")
        parser.add_argument("--fix", action="store_true", help="Intentar corregir problemas automáticamente")

    def handle(self, *args, **options):
        self.stdout.write("🔍 Iniciando diagnóstico completo del sistema...")
        
        # 1. Análisis de configuración básica
        self.analizar_configuracion()
        
        # 2. Análisis de bloques horarios
        self.analizar_bloques_horarios()
        
        # 3. Análisis de disponibilidad de profesores
        self.analizar_disponibilidad_profesores()
        
        # 4. Análisis de materias y cursos
        self.analizar_materias_cursos()
        
        # 5. Análisis de factibilidad global
        self.analizar_factibilidad_global()
        
        # 6. Sugerencias de mejora
        self.sugerir_mejoras()
        
        if options["csv"]:
            self.exportar_csv()
        
        if options["fix"]:
            self.intentar_corregir_problemas()

    def analizar_configuracion(self):
        """Analiza la configuración básica del colegio."""
        self.stdout.write("\n📋 ANÁLISIS DE CONFIGURACIÓN:")
        
        try:
            config = ConfiguracionColegio.objects.first()
            if config:
                self.stdout.write(f"   ✅ Configuración encontrada")
                self.stdout.write(f"   - Días de clase: {config.dias_clase or 'No configurado'}")
                self.stdout.write(f"   - Bloques por día: {config.bloques_por_dia or 'No configurado'}")
            else:
                self.stdout.write("   ❌ No hay configuración del colegio")
                self.stdout.write("   💡 Ejecutar: python manage.py seed_realista --purge")
        except Exception as e:
            self.stdout.write(f"   ❌ Error al leer configuración: {e}")

    def analizar_bloques_horarios(self):
        """Analiza los bloques horarios disponibles."""
        self.stdout.write("\n⏰ ANÁLISIS DE BLOQUES HORARIOS:")
        
        try:
            bloques = BloqueHorario.objects.all().order_by('numero')
            if bloques:
                self.stdout.write(f"   ✅ {bloques.count()} bloques encontrados")
                
                tipos = defaultdict(int)
                for bloque in bloques:
                    tipos[bloque.tipo] += 1
                    self.stdout.write(f"   - Bloque {bloque.numero}: {bloque.tipo}")
                
                self.stdout.write(f"\n   📊 Resumen por tipo:")
                for tipo, count in tipos.items():
                    self.stdout.write(f"   - {tipo}: {count} bloques")
                
                # Verificar si hay suficientes bloques de clase
                bloques_clase = bloques.filter(tipo='clase')
                if bloques_clase.count() < 5:
                    self.stdout.write("   ⚠️  Pocos bloques de clase disponibles")
                else:
                    self.stdout.write("   ✅ Suficientes bloques de clase")
            else:
                self.stdout.write("   ❌ No hay bloques horarios definidos")
        except Exception as e:
            self.stdout.write(f"   ❌ Error al leer bloques: {e}")

    def analizar_disponibilidad_profesores(self):
        """Analiza la disponibilidad de los profesores."""
        self.stdout.write("\n👨‍🏫 ANÁLISIS DE DISPONIBILIDAD DE PROFESORES:")
        
        try:
            profesores = Profesor.objects.all()
            self.stdout.write(f"   ✅ {profesores.count()} profesores encontrados")
            
            # Analizar disponibilidad por profesor
            sin_disponibilidad = 0
            disponibilidad_insuficiente = 0
            
            for profesor in profesores:
                disponibilidades = DisponibilidadProfesor.objects.filter(profesor=profesor)
                if not disponibilidades.exists():
                    sin_disponibilidad += 1
                    continue
                
                # Verificar si la disponibilidad cubre todos los bloques
                bloques_disponibles = set()
                for disp in disponibilidades:
                    for bloque in range(disp.bloque_inicio, disp.bloque_fin + 1):
                        bloques_disponibles.add((disp.dia, bloque))
                
                # Verificar si hay suficientes bloques disponibles
                dias_config = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes']
                bloques_config = list(BloqueHorario.objects.filter(tipo='clase').values_list('numero', flat=True))
                
                slots_esperados = len(dias_config) * len(bloques_config)
                if len(bloques_disponibles) < slots_esperados * 0.8:  # 80% de cobertura mínima
                    disponibilidad_insuficiente += 1
            
            self.stdout.write(f"   - Sin disponibilidad: {sin_disponibilidad}")
            self.stdout.write(f"   - Disponibilidad insuficiente: {disponibilidad_insuficiente}")
            
            if sin_disponibilidad > 0:
                self.stdout.write("   ⚠️  Algunos profesores no tienen disponibilidad definida")
            if disponibilidad_insuficiente > 0:
                self.stdout.write("   ⚠️  Algunos profesores tienen disponibilidad limitada")
                
        except Exception as e:
            self.stdout.write(f"   ❌ Error al analizar disponibilidad: {e}")

    def analizar_materias_cursos(self):
        """Analiza la relación entre materias y cursos."""
        self.stdout.write("\n📚 ANÁLISIS DE MATERIAS Y CURSOS:")
        
        try:
            cursos = Curso.objects.all()
            materias = Materia.objects.all()
            
            self.stdout.write(f"   ✅ {cursos.count()} cursos, {materias.count()} materias")
            
            # Verificar que cada curso tenga materias asignadas
            cursos_sin_materias = 0
            for curso in cursos:
                materias_curso = MateriaGrado.objects.filter(grado=curso.grado)
                if not materias_curso.exists():
                    cursos_sin_materias += 1
            
            if cursos_sin_materias > 0:
                self.stdout.write(f"   ⚠️  {cursos_sin_materias} cursos sin materias asignadas")
            
            # Verificar que cada materia tenga profesores
            materias_sin_profesores = 0
            for materia in materias:
                profesores_materia = MateriaProfesor.objects.filter(materia=materia)
                if not profesores_materia.exists():
                    materias_sin_profesores += 1
            
            if materias_sin_profesores > 0:
                self.stdout.write(f"   ⚠️  {materias_sin_profesores} materias sin profesores asignados")
                
        except Exception as e:
            self.stdout.write(f"   ❌ Error al analizar materias y cursos: {e}")

    def analizar_factibilidad_global(self):
        """Analiza la factibilidad global del sistema."""
        self.stdout.write("\n🌐 ANÁLISIS DE FACTIBILIDAD GLOBAL:")
        
        try:
            # Calcular capacidad total del sistema
            dias_config = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes']
            bloques_clase = list(BloqueHorario.objects.filter(tipo='clase').values_list('numero', flat=True))
            cursos = Curso.objects.all()
            
            capacidad_total = len(dias_config) * len(bloques_clase) * cursos.count()
            self.stdout.write(f"   - Capacidad total del sistema: {capacidad_total} slots")
            
            # Calcular demanda total
            demanda_total = 0
            for curso in cursos:
                materias_curso = MateriaGrado.objects.filter(grado=curso.grado)
                for materia_grado in materias_curso:
                    if materia_grado.materia:
                        demanda_total += materia_grado.materia.bloques_por_semana
            
            self.stdout.write(f"   - Demanda total del sistema: {demanda_total} bloques")
            
            # Verificar factibilidad
            if demanda_total > capacidad_total:
                self.stdout.write("   ❌ DEMANDA EXCEDE CAPACIDAD - Sistema no factible")
                self.stdout.write("   💡 Soluciones:")
                self.stdout.write("      - Reducir bloques por materia")
                self.stdout.write("      - Aumentar bloques por día")
                self.stdout.write("      - Reducir número de cursos")
            elif demanda_total < capacidad_total * 0.8:
                self.stdout.write("   ⚠️  Capacidad subutilizada - Demanda muy baja")
            else:
                self.stdout.write("   ✅ Sistema factible - Demanda y capacidad balanceadas")
                
        except Exception as e:
            self.stdout.write(f"   ❌ Error al analizar factibilidad: {e}")

    def sugerir_mejoras(self):
        """Sugiere mejoras para el sistema."""
        self.stdout.write("\n💡 SUGERENCIAS DE MEJORA:")
        
        try:
            # Verificar si hay profesores sin disponibilidad
            profesores_sin_disp = Profesor.objects.filter(
                disponibilidadprofesor__isnull=True
            ).count()
            
            if profesores_sin_disp > 0:
                self.stdout.write(f"   🔧 {profesores_sin_disp} profesores sin disponibilidad")
                self.stdout.write("      - Ejecutar: python manage.py seed_realista --purge")
            
            # Verificar configuración
            config = ConfiguracionColegio.objects.first()
            if not config or not config.dias_clase or not config.bloques_por_dia:
                self.stdout.write("   🔧 Configuración incompleta")
                self.stdout.write("      - Ejecutar: python manage.py seed_realista --purge")
            
            # Verificar bloques de clase
            bloques_clase = BloqueHorario.objects.filter(tipo='clase').count()
            if bloques_clase < 5:
                self.stdout.write("   🔧 Pocos bloques de clase")
                self.stdout.write("      - Crear más bloques tipo 'clase'")
            
            self.stdout.write("\n   🚀 Para probar el sistema:")
            self.stdout.write("      - python manage.py test_generacion --iteraciones 2")
            self.stdout.write("      - python manage.py diagnostico_horarios")
            
        except Exception as e:
            self.stdout.write(f"   ❌ Error al generar sugerencias: {e}")

    def intentar_corregir_problemas(self):
        """Intenta corregir problemas automáticamente."""
        self.stdout.write("\n🔧 INTENTANDO CORREGIR PROBLEMAS:")
        
        try:
            # Verificar si hay profesores sin disponibilidad
            profesores_sin_disp = Profesor.objects.filter(
                disponibilidadprofesor__isnull=True
            )
            
            if profesores_sin_disp.exists():
                self.stdout.write("   🔧 Creando disponibilidad para profesores...")
                
                # Obtener configuración
                config = ConfiguracionColegio.objects.first()
                bloques_por_dia = config.bloques_por_dia if config else 6
                dias = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes']
                
                for profesor in profesores_sin_disp:
                    for dia in dias:
                        DisponibilidadProfesor.objects.get_or_create(
                            profesor=profesor,
                            dia=dia,
                            defaults={
                                'bloque_inicio': 1,
                                'bloque_fin': bloques_por_dia
                            }
                        )
                
                self.stdout.write("   ✅ Disponibilidad creada para todos los profesores")
            
            # Verificar configuración
            if not ConfiguracionColegio.objects.exists():
                self.stdout.write("   🔧 Creando configuración del colegio...")
                ConfiguracionColegio.objects.create(
                    dias_clase='lunes,martes,miércoles,jueves,viernes',
                    bloques_por_dia=6
                )
                self.stdout.write("   ✅ Configuración creada")
                
        except Exception as e:
            self.stdout.write(f"   ❌ Error al corregir problemas: {e}")

    def exportar_csv(self):
        """Exporta los resultados del diagnóstico a CSV."""
        self.stdout.write("\n📊 Exportando resultados a CSV...")
        
        try:
            filename = "diagnostico_horarios.csv"
            with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(['Aspecto', 'Estado', 'Detalles'])
                
                # Aquí podrías agregar más datos específicos para el CSV
                writer.writerow(['Profesores', 'Total', Profesor.objects.count()])
                writer.writerow(['Cursos', 'Total', Curso.objects.count()])
                writer.writerow(['Materias', 'Total', Materia.objects.count()])
                writer.writerow(['Bloques', 'Total', BloqueHorario.objects.count()])
            
            self.stdout.write(f"   ✅ Resultados exportados a {filename}")
            
        except Exception as e:
            self.stdout.write(f"   ❌ Error al exportar CSV: {e}") 