"""
Management command para cargar datasets de prueba de diferentes tamaños.
Uso: python manage.py cargar_dataset --size {S|M|L|XL} --seed 42 --force
"""

import random
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from horarios.models import (
    Profesor, Materia, Curso, Aula, Grado, MateriaGrado, 
    MateriaProfesor, DisponibilidadProfesor, BloqueHorario
)


class Command(BaseCommand):
    help = 'Carga un dataset de prueba de tamaño especificado (S, M, L, XL)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--size',
            type=str,
            choices=['S', 'M', 'L', 'XL'],
            default='M',
            help='Tamaño del dataset (S, M, L, XL)'
        )
        parser.add_argument(
            '--seed',
            type=int,
            default=42,
            help='Semilla para reproducibilidad'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Forzar recreación de datos existentes'
        )

    def handle(self, *args, **options):
        size = options['size']
        seed = options['seed']
        force = options['force']
        
        # Configurar semilla
        random.seed(seed)
        
        # Configuraciones por tamaño
        configs = {
            'S': {
                'cursos': 10,
                'profesores': 15,
                'materias': 12,
                'bloques_por_dia': 6,
                'aulas': 12
            },
            'M': {
                'cursos': 30,
                'profesores': 40,
                'materias': 18,
                'bloques_por_dia': 7,
                'aulas': 35
            },
            'L': {
                'cursos': 60,
                'profesores': 80,
                'materias': 22,
                'bloques_por_dia': 8,
                'aulas': 65
            },
            'XL': {
                'cursos': 100,
                'profesores': 150,
                'materias': 26,
                'bloques_por_dia': 8,
                'aulas': 105
            }
        }
        
        config = configs[size]
        
        self.stdout.write(f"Cargando dataset {size} con configuración: {config}")
        
        try:
            with transaction.atomic():
                if force:
                    self._limpiar_datos()
                
                self._crear_datos(config, seed)
                
            self.stdout.write(
                self.style.SUCCESS(f'✅ Dataset {size} cargado exitosamente')
            )
            
        except Exception as e:
            raise CommandError(f"Error al cargar dataset: {e}")

    def _limpiar_datos(self):
        """Limpia todos los datos existentes."""
        self.stdout.write("Limpiando datos existentes...")
        
        # Eliminar en orden para evitar problemas de FK
        Horario.objects.all().delete()
        DisponibilidadProfesor.objects.all().delete()
        MateriaProfesor.objects.all().delete()
        MateriaGrado.objects.all().delete()
        Curso.objects.all().delete()
        Profesor.objects.all().delete()
        Materia.objects.all().delete()
        Aula.objects.all().delete()
        Grado.objects.all().delete()
        BloqueHorario.objects.all().delete()

    def _crear_datos(self, config, seed):
        """Crea los datos según la configuración especificada."""
        
        # Crear grados
        grados = self._crear_grados()
        
        # Crear aulas
        aulas = self._crear_aulas(config['aulas'])
        
        # Crear bloques horarios
        self._crear_bloques_horarios(config['bloques_por_dia'])
        
        # Crear materias
        materias = self._crear_materias(config['materias'])
        
        # Crear profesores
        profesores = self._crear_profesores(config['profesores'])
        
        # Crear cursos
        cursos = self._crear_cursos(config['cursos'], grados, aulas)
        
        # Crear relaciones materia-grado
        self._crear_materia_grado(materias, grados)
        
        # Crear relaciones materia-profesor
        self._crear_materia_profesor(materias, profesores)
        
        # Crear disponibilidad de profesores
        self._crear_disponibilidad_profesores(profesores, config['bloques_por_dia'])

    def _crear_grados(self):
        """Crea grados escolares."""
        grados = []
        nombres_grados = ['Primero', 'Segundo', 'Tercero', 'Cuarto', 'Quinto', 'Sexto', 'Séptimo', 'Octavo', 'Noveno', 'Décimo', 'Undécimo']
        
        for nombre in nombres_grados:
            grado, created = Grado.objects.get_or_create(nombre=nombre)
            grados.append(grado)
            if created:
                self.stdout.write(f"  Creado grado: {nombre}")
        
        return grados

    def _crear_aulas(self, num_aulas):
        """Crea aulas de diferentes tipos."""
        aulas = []
        tipos = ['comun', 'laboratorio', 'arte', 'educacion_fisica', 'tecnologia']
        
        for i in range(num_aulas):
            tipo = tipos[i % len(tipos)]
            nombre = f"Aula {i+1:03d}"
            capacidad = random.randint(25, 45)
            
            aula, created = Aula.objects.get_or_create(
                nombre=nombre,
                defaults={'tipo': tipo, 'capacidad': capacidad}
            )
            aulas.append(aula)
            if created:
                self.stdout.write(f"  Creada aula: {nombre} ({tipo})")
        
        return aulas

    def _crear_bloques_horarios(self, bloques_por_dia):
        """Crea bloques horarios de tipo 'clase'."""
        for i in range(1, bloques_por_dia + 1):
            hora_inicio = f"{7 + i:02d}:00"
            hora_fin = f"{8 + i:02d}:00"
            
            bloque, created = BloqueHorario.objects.get_or_create(
                numero=i,
                defaults={
                    'hora_inicio': hora_inicio,
                    'hora_fin': hora_fin,
                    'tipo': 'clase'
                }
            )
            if created:
                self.stdout.write(f"  Creado bloque: {i} ({hora_inicio}-{hora_fin})")

    def _crear_materias(self, num_materias):
        """Crea materias escolares."""
        materias = []
        nombres_materias = [
            'Matemáticas', 'Lenguaje', 'Ciencias', 'Historia', 'Geografía',
            'Inglés', 'Arte', 'Música', 'Educación Física', 'Tecnología',
            'Filosofía', 'Química', 'Física', 'Biología', 'Literatura',
            'Gramática', 'Álgebra', 'Geometría', 'Trigonometría', 'Cálculo',
            'Estadística', 'Programación', 'Dibujo', 'Teatro', 'Danza',
            'Deportes', 'Cocina', 'Jardinería', 'Carpintería', 'Electricidad'
        ]
        
        for i in range(num_materias):
            nombre = nombres_materias[i % len(nombres_materias)]
            bloques_por_semana = random.randint(2, 6)
            jornada_preferida = random.choice(['mañana', 'tarde', 'cualquiera'])
            requiere_bloques_consecutivos = random.choice([True, False])
            requiere_aula_especial = random.choice([True, False])
            
            materia, created = Materia.objects.get_or_create(
                nombre=nombre,
                defaults={
                    'bloques_por_semana': bloques_por_semana,
                    'jornada_preferida': jornada_preferida,
                    'requiere_bloques_consecutivos': requiere_bloques_consecutivos,
                    'requiere_aula_especial': requiere_aula_especial
                }
            )
            materias.append(materia)
            if created:
                self.stdout.write(f"  Creada materia: {nombre} ({bloques_por_semana} bloques/semana)")
        
        return materias

    def _crear_profesores(self, num_profesores):
        """Crea profesores."""
        profesores = []
        nombres = [
            'Ana', 'Carlos', 'María', 'Juan', 'Laura', 'Pedro', 'Sofia', 'Luis',
            'Carmen', 'Roberto', 'Elena', 'Miguel', 'Isabel', 'Francisco', 'Patricia',
            'Jorge', 'Lucía', 'Diego', 'Valentina', 'Andrés', 'Camila', 'Ricardo',
            'Daniela', 'Fernando', 'Natalia', 'Alejandro', 'Gabriela', 'Héctor',
            'Monica', 'Eduardo', 'Claudia', 'Rafael', 'Verónica', 'Manuel',
            'Adriana', 'Javier', 'Silvia', 'Alberto', 'Rosa', 'Guillermo'
        ]
        apellidos = [
            'García', 'Rodríguez', 'López', 'Martínez', 'González', 'Pérez',
            'Sánchez', 'Ramírez', 'Torres', 'Flores', 'Rivera', 'Morales',
            'Cruz', 'Ortiz', 'Silva', 'Reyes', 'Moreno', 'Jiménez', 'Díaz',
            'Romero', 'Herrera', 'Ruiz', 'Vargas', 'Mendoza', 'Castro'
        ]
        
        for i in range(num_profesores):
            nombre = f"{random.choice(nombres)} {random.choice(apellidos)}"
            
            profesor, created = Profesor.objects.get_or_create(nombre=nombre)
            profesores.append(profesor)
            if created:
                self.stdout.write(f"  Creado profesor: {nombre}")
        
        return profesores

    def _crear_cursos(self, num_cursos, grados, aulas):
        """Crea cursos y les asigna aulas fijas."""
        cursos = []
        
        for i in range(num_cursos):
            grado = random.choice(grados)
            nombre = f"{grado.nombre} {chr(65 + (i % 3))}"  # A, B, C
            aula = aulas[i % len(aulas)]
            
            curso, created = Curso.objects.get_or_create(
                nombre=nombre,
                grado=grado,
                defaults={'aula_fija': aula}
            )
            cursos.append(curso)
            if created:
                self.stdout.write(f"  Creado curso: {nombre} en {aula.nombre}")
        
        return cursos

    def _crear_materia_grado(self, materias, grados):
        """Crea relaciones materia-grado."""
        for materia in materias:
            # Cada materia se asigna a 2-4 grados aleatorios
            num_grados = random.randint(2, min(4, len(grados)))
            grados_seleccionados = random.sample(grados, num_grados)
            
            for grado in grados_seleccionados:
                mg, created = MateriaGrado.objects.get_or_create(
                    materia=materia,
                    grado=grado
                )
                if created:
                    self.stdout.write(f"  Asignada materia {materia.nombre} a grado {grado.nombre}")

    def _crear_materia_profesor(self, materias, profesores):
        """Crea relaciones materia-profesor."""
        for materia in materias:
            # Cada materia tiene 1-3 profesores
            num_profesores = random.randint(1, min(3, len(profesores)))
            profesores_seleccionados = random.sample(profesores, num_profesores)
            
            for profesor in profesores_seleccionados:
                mp, created = MateriaProfesor.objects.get_or_create(
                    materia=materia,
                    profesor=profesor
                )
                if created:
                    self.stdout.write(f"  Asignado profesor {profesor.nombre} a materia {materia.nombre}")

    def _crear_disponibilidad_profesores(self, profesores, bloques_por_dia):
        """Crea disponibilidad de profesores."""
        dias = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes']
        
        for profesor in profesores:
            # Cada profesor tiene disponibilidad en 3-5 días
            num_dias = random.randint(3, 5)
            dias_disponibles = random.sample(dias, num_dias)
            
            for dia in dias_disponibles:
                # Disponibilidad en 3-6 bloques consecutivos
                bloque_inicio = random.randint(1, bloques_por_dia - 2)
                bloque_fin = min(bloque_inicio + random.randint(2, 4), bloques_por_dia)
                
                disp, created = DisponibilidadProfesor.objects.get_or_create(
                    profesor=profesor,
                    dia=dia,
                    defaults={
                        'bloque_inicio': bloque_inicio,
                        'bloque_fin': bloque_fin
                    }
                )
                if created:
                    self.stdout.write(f"  Disponibilidad {profesor.nombre}: {dia} bloques {bloque_inicio}-{bloque_fin}") 