#!/usr/bin/env python3
"""
Management command para poblar la tabla CursoMateriaRequerida con datos de MateriaGrado.
Este comando es necesario porque el sistema de máscaras busca primero en CursoMateriaRequerida.
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from horarios.models import Curso, Materia, MateriaGrado, CursoMateriaRequerida

class Command(BaseCommand):
    help = 'Pobla la tabla CursoMateriaRequerida con datos de MateriaGrado'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Forzar sobrescritura de datos existentes',
        )

    def handle(self, *args, **options):
        self.stdout.write("🔄 Poblando tabla CursoMateriaRequerida...")
        
        # Verificar si ya hay datos
        if CursoMateriaRequerida.objects.exists() and not options['force']:
            self.stdout.write(
                self.style.WARNING("⚠️  La tabla CursoMateriaRequerida ya tiene datos.")
            )
            respuesta = input("¿Desea continuar y sobrescribir? (s/N): ")
            if respuesta.lower() != 's':
                self.stdout.write(self.style.ERROR("❌ Operación cancelada."))
                return
        
        # Limpiar tabla existente
        CursoMateriaRequerida.objects.all().delete()
        self.stdout.write("🧹 Tabla limpiada.")
        
        # Contadores
        creados = 0
        omitidos = 0
        
        with transaction.atomic():
            # Obtener todos los cursos
            cursos = Curso.objects.select_related('grado').all()
            
            for curso in cursos:
                self.stdout.write(f"📚 Procesando curso: {curso.nombre} (Grado: {curso.grado.nombre})")
                
                # Obtener materias del grado del curso
                materias_grado = MateriaGrado.objects.filter(grado=curso.grado)
                
                for mg in materias_grado:
                    try:
                        # Crear registro en CursoMateriaRequerida
                        CursoMateriaRequerida.objects.create(
                            curso=curso,
                            materia=mg.materia,
                            bloques_requeridos=mg.materia.bloques_por_semana
                        )
                        creados += 1
                        self.stdout.write(f"  ✅ {mg.materia.nombre}: {mg.materia.bloques_por_semana} bloques")
                        
                    except Exception as e:
                        omitidos += 1
                        self.stdout.write(f"  ❌ {mg.materia.nombre}: Error - {e}")
        
        self.stdout.write(f"\n🎉 Proceso completado:")
        self.stdout.write(f"  ✅ Registros creados: {creados}")
        self.stdout.write(f"  ❌ Registros omitidos: {omitidos}")
        
        # Verificar resultado
        total_final = CursoMateriaRequerida.objects.count()
        self.stdout.write(f"  📊 Total en tabla: {total_final}")
        
        if total_final > 0:
            self.stdout.write(
                self.style.SUCCESS("\n✅ La tabla CursoMateriaRequerida ha sido poblada exitosamente.")
            )
            self.stdout.write("🔄 Ahora el sistema de generación de horarios debería funcionar correctamente.")
        else:
            self.stdout.write(
                self.style.ERROR("\n❌ Error: La tabla sigue vacía.")
            ) 