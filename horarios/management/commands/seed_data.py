from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.utils import timezone
from datetime import time
import random
from horarios.models import (
    ConfiguracionColegio, BloqueHorario, Slot, Grado, Curso, Aula,
    Materia, Profesor, DisponibilidadProfesor, MateriaGrado, MateriaProfesor,
    CursoMateriaRequerida, MateriaRelleno
)

class Command(BaseCommand):
    """
    Comando para poblar la base de datos con un escenario de prueba REALISTA.
    Crea configuración, bloques, cursos, profesores, materias y sus relaciones.
    
    WARNING: Borra todos los datos existentes antes de crear los nuevos.
    """
    help = 'Pobla la base de datos con un escenario de colegio REALISTA (seed)'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.WARNING('Iniciando proceso de seed REALISTA...'))

        # 1. Limpiar datos existentes
        self.stdout.write('Limpiando datos existentes...')
        MateriaRelleno.objects.all().delete()
        CursoMateriaRequerida.objects.all().delete()
        MateriaProfesor.objects.all().delete()
        MateriaGrado.objects.all().delete()
        DisponibilidadProfesor.objects.all().delete()
        Profesor.objects.all().delete()
        Materia.objects.all().delete()
        Curso.objects.all().delete()
        Aula.objects.all().delete()
        Grado.objects.all().delete()
        Slot.objects.all().delete()
        BloqueHorario.objects.all().delete()
        ConfiguracionColegio.objects.all().delete()

        # 2. Configuración del Colegio (Jornada Mañana, 6 horas académicas)
        self.stdout.write('Creando configuración del colegio...')
        ConfiguracionColegio.objects.create(
            jornada='mañana',
            bloques_por_dia=6,
            duracion_bloque=55, # 55 min clases
            dias_clase='lunes,martes,miércoles,jueves,viernes'
        )

        # 3. Bloques Horarios (7:00 AM - 1:30 PM aprox)
        self.stdout.write('Creando bloques horarios...')
        horas = [
            (time(7, 0), time(7, 55)),   # Bloque 1
            (time(7, 55), time(8, 50)),  # Bloque 2
            (time(8, 50), time(9, 20)),  # Descanso 1
            (time(9, 20), time(10, 15)), # Bloque 3
            (time(10, 15), time(11, 10)),# Bloque 4
            (time(11, 10), time(11, 40)),# Descanso 2
            (time(11, 40), time(12, 35)),# Bloque 5
            (time(12, 35), time(13, 30)),# Bloque 6
        ]
        
        # Bloques de clase (excluyendo descansos para el contador oficial)
        bloques_clase_indices = [0, 1, 3, 4, 6, 7] 
        numero_bloque = 1
        
        for i, (inicio, fin) in enumerate(horas):
            if i in bloques_clase_indices:
                BloqueHorario.objects.create(numero=numero_bloque, hora_inicio=inicio, hora_fin=fin, tipo='clase')
                numero_bloque += 1
            else:
                # Los descansos no llevan número secuencial de bloque de clase en este modelo simple, 
                # pero los creamos para referencia visual si fuera necesario, o los omitimos de BloqueHorario
                # si solo nos importan los de clase. Para Slots sí los necesitamos si queremos mostrar huecos.
                pass

        # 4. Slots (Lunes a Viernes)
        self.stdout.write('Creando slots...')
        dias = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes']
        # Recuperamos los bloques creados
        bloques_db = list(BloqueHorario.objects.filter(tipo='clase').order_by('numero'))
        
        for dia in dias:
            for b_obj in bloques_db:
                Slot.objects.create(
                    dia=dia,
                    bloque=b_obj.numero,
                    hora_inicio=b_obj.hora_inicio,
                    hora_fin=b_obj.hora_fin,
                    tipo='clase'
                )

        # 5. Grados y Cursos (6º a 11º, dos grupos A y B) -> 12 Cursos
        self.stdout.write('Creando grados y cursos...')
        grados_config = ['SEXTO', 'SEPTIMO', 'OCTAVO', 'NOVENO', 'DECIMO', 'ONCE']
        cursos_objs = []
        grados_objs = {} # Mapa nombre -> objeto
        
        for nombre_grado in grados_config:
            grado = Grado.objects.create(nombre=nombre_grado)
            grados_objs[nombre_grado] = grado
            
            for grupo in ['A', 'B']:
                nombre_curso = f"{nombre_grado} {grupo}"
                # Aula normal
                aula = Aula.objects.create(
                    nombre=f"Salón {nombre_curso}",
                    tipo='comun',
                    capacidad=40
                )
                curso = Curso.objects.create(
                    nombre=nombre_curso,
                    grado=grado,
                    aula_fija=aula
                )
                cursos_objs.append(curso)

        # 6. Aulas Especiales
        self.stdout.write('Creando aulas especiales...')
        aulas_especiales = [
            Aula.objects.create(nombre="Laboratorio Química", tipo='laboratorio', capacidad=30),
            Aula.objects.create(nombre="Laboratorio Física", tipo='laboratorio', capacidad=30),
            Aula.objects.create(nombre="Sala de Sistemas 1", tipo='tecnologia', capacidad=40),
            Aula.objects.create(nombre="Sala de Sistemas 2", tipo='tecnologia', capacidad=40),
            Aula.objects.create(nombre="Sala de Arte", tipo='arte', capacidad=35),
            Aula.objects.create(nombre="Cancha Múltiple", tipo='educacion_fisica', capacidad=100),
            Aula.objects.create(nombre="Patio Central", tipo='educacion_fisica', capacidad=100),
        ]

        # 7. Definición de Materias (Plan de Estudios)
        self.stdout.write('Definiendo materias...')
        
        # Materia de Relleno (Vital para completar horarios)
        materia_relleno = Materia.objects.create(
            nombre="Actividad Complementaria",
            bloques_por_semana=1, 
            es_relleno=True,
            prioridad=10,
            tipo_materia='relleno'
        )
        
        # Configurar MateriaRelleno (Necesario para GeneradorDemandFirst)
        MateriaRelleno.objects.create(
            materia=materia_relleno,
            flexible_bloques=True,
            min_bloques=1,
            max_bloques=10,
            activa=True
        )
        
        # No la agregamos a materias_db por nombre para evitar conflictos con lógica de abajo,
        # pero la usaremos para asignarla a todos los grados al final.
        
        # Materias Comunes (Básica: 6-9) - Total 29 horas (dejamos 1 para relleno/flexible)
        plan_basica = [
            {'nombre': 'Matemáticas', 'bloques': 5},
            {'nombre': 'Español', 'bloques': 4}, # Reducido de 5 a 4
            {'nombre': 'Inglés', 'bloques': 4},
            {'nombre': 'Ciencias Naturales', 'bloques': 4, 'aula_tipo': 'laboratorio'},
            {'nombre': 'Ciencias Sociales', 'bloques': 4},
            {'nombre': 'Educación Física', 'bloques': 2, 'aula_tipo': 'educacion_fisica'},
            {'nombre': 'Tecnología', 'bloques': 2, 'aula_tipo': 'tecnologia'},
            {'nombre': 'Artes', 'bloques': 2, 'aula_tipo': 'arte'},
            {'nombre': 'Ética', 'bloques': 1},
            {'nombre': 'Religión', 'bloques': 1},
        ]
        
        # Materias Media (10-11) - Total 29 horas (dejamos 1 para relleno/flexible)
        plan_media = [
            {'nombre': 'Cálculo', 'bloques': 4},     # Matemáticas avanzada
            {'nombre': 'Física', 'bloques': 3, 'aula_tipo': 'laboratorio'},
            {'nombre': 'Química', 'bloques': 3, 'aula_tipo': 'laboratorio'},
            {'nombre': 'Español y Literatura', 'bloques': 3},
            {'nombre': 'Inglés Intensivo', 'bloques': 3}, # Reducido de 4 a 3
            {'nombre': 'Filosofía', 'bloques': 3},
            {'nombre': 'Ciencias Políticas', 'bloques': 2},
            {'nombre': 'Educación Física', 'bloques': 2, 'aula_tipo': 'educacion_fisica'},
            {'nombre': 'Tecnología Aplicada', 'bloques': 2, 'aula_tipo': 'tecnologia'},
            {'nombre': 'Investigación', 'bloques': 2},
            {'nombre': 'Ética', 'bloques': 1},
            {'nombre': 'Religión', 'bloques': 1},
        ]

        # Crear objetos Materia (unificando nombres para evitar duplicados si coinciden)
        # Usaremos un diccionario para no repetir materias si tienen el mismo nombre
        materias_db = {} 
        
        def get_or_create_materia(data):
            nombre = data['nombre']
            if nombre in materias_db:
                return materias_db[nombre]
            
            req_aula = 'aula_tipo' in data
            m_obj = Materia.objects.create(
                nombre=nombre,
                bloques_por_semana=data['bloques'], # Default, se sobreescribe en CursoMateriaRequerida
                requiere_aula_especial=req_aula,
                # Si requiere aula especial, mapeamos el tipo en la lógica de asignación, 
                # pero el modelo Materia solo tiene booleano 'requiere_aula_especial'.
                # La lógica de 'tipo' de aula se maneja en el validador o asignación.
                # Para simplificar, asumiremos que si requiere aula especial, cualquiera de ese "tipo" sirve,
                # pero el modelo actual solo pide "aula especial" vs "comun".
                # (Mejoraremos esto asumiendo que el algoritmo busca un aula del tipo correcto si implementamos esa lógica,
                # por ahora lo marcamos como especial).
            )
            # Guardamos el tipo de aula preferido en un atributo temporal para usarlo al asignar profes o reglas
            m_obj.tipo_aula_preferido = data.get('aula_tipo', 'comun')
            materias_db[nombre] = m_obj
            return m_obj

        # Crear todas las materias
        for m in plan_basica: get_or_create_materia(m)
        for m in plan_media: get_or_create_materia(m)

        # 8. Asignar Materias a Grados
        self.stdout.write('Asignando materias a grados...')
        
        # Asignar materia de relleno a todos los grados
        materia_relleno = Materia.objects.get(nombre="Actividad Complementaria")
        for grado_obj in grados_objs.values():
             MateriaGrado.objects.get_or_create(grado=grado_obj, materia=materia_relleno)

        # 6º a 9º
        grados_basica = ['SEXTO', 'SEPTIMO', 'OCTAVO', 'NOVENO']
        for g_nom in grados_basica:
            grado = grados_objs[g_nom]
            for m_data in plan_basica:
                m_obj = materias_db[m_data['nombre']]
                MateriaGrado.objects.get_or_create(grado=grado, materia=m_obj)

        # 10º a 11º
        grados_media = ['DECIMO', 'ONCE']
        for g_nom in grados_media:
            grado = grados_objs[g_nom]
            for m_data in plan_media:
                m_obj = materias_db[m_data['nombre']]
                MateriaGrado.objects.get_or_create(grado=grado, materia=m_obj)

        # 9. Profesores (Staff Grande)
        self.stdout.write('Contratando profesores...')
        
        # Estructura: (Nombre, [Lista de Materias que puede dictar])
        staff = [
            # Matemáticas y Física
            ('Prof. Newton', ['Matemáticas', 'Cálculo', 'Física']),
            ('Prof. Euler', ['Matemáticas', 'Cálculo']),
            ('Prof. Hipatia', ['Matemáticas']),
            
            # Ciencias
            ('Prof. Curie', ['Química', 'Ciencias Naturales', 'Investigación']),
            ('Prof. Darwin', ['Ciencias Naturales', 'Investigación']),
            ('Prof. Einstein', ['Física', 'Ciencias Naturales', 'Investigación']),
            
            # Humanidades
            ('Prof. Cervantes', ['Español', 'Español y Literatura']),
            ('Prof. Gabo', ['Español', 'Español y Literatura']),
            ('Prof. Shakespeare', ['Inglés', 'Inglés Intensivo']),
            ('Prof. Wilde', ['Inglés', 'Inglés Intensivo']),
            
            # Sociales
            ('Prof. Herodoto', ['Historia', 'Ciencias Sociales', 'Ciencias Políticas']),
            ('Prof. Platón', ['Filosofía', 'Ética', 'Religión', 'Ciencias Políticas']),
            ('Prof. Marx', ['Ciencias Sociales', 'Filosofía', 'Ciencias Políticas']),
            
            # Técnicas y Arte
            ('Prof. Da Vinci', ['Artes', 'Tecnología', 'Tecnología Aplicada']),
            ('Prof. Picasso', ['Artes']),
            ('Prof. Jobs', ['Tecnología', 'Tecnología Aplicada']),
            
            # Deportes
            ('Prof. Messi', ['Educación Física']),
            ('Prof. Jordan', ['Educación Física']),
            
            # Ética y Religión (Relleno/Transversales)
            ('Prof. Francisco', ['Religión', 'Ética']),
        ]

        profesores_objs = []
        for nombre, especialidades in staff:
            prof = Profesor.objects.create(nombre=nombre)
            profesores_objs.append(prof)
            
            # Disponibilidad (todos tiempo completo 7-1:30 para simplificar, algunos con huecos)
            # Para hacerlo realista, vamos a darles un día libre aleatorio o tardes libres (que no aplican aquí pq es jornada mañana)
            # Daremos disponibilidad completa para maximizar factibilidad inicial
            for dia in dias:
                DisponibilidadProfesor.objects.create(
                    profesor=prof, dia=dia, bloque_inicio=1, bloque_fin=6
                )
            
            # Asignar especialidades (MateriaProfesor)
            for esp in especialidades:
                if esp in materias_db:
                    MateriaProfesor.objects.create(profesor=prof, materia=materias_db[esp])

        # 10. Poblar CursoMateriaRequerida
        self.stdout.write('Generando requerimientos de cursos...')
        call_command('poblar_curso_materia_requerida', force=True)
        
        # 11. Configurar Materia de Relleno (Asignar a todos los grados y un profesor comodín)
        self.stdout.write('Configurando materia de relleno...')
        materia_relleno = Materia.objects.get(nombre="Actividad Complementaria")
        
        # Asignar a todos los grados
        for grado in Grado.objects.all():
            MateriaGrado.objects.get_or_create(grado=grado, materia=materia_relleno)
            
        # Asignar a un profesor (o varios)
        prof_comodin, _ = Profesor.objects.get_or_create(
            nombre="Prof. Monitor",
            defaults={'max_bloques_por_semana': 50, 'puede_dictar_relleno': True}
        )
        # Dar disponibilidad completa al comodín
        for dia in dias:
            DisponibilidadProfesor.objects.get_or_create(
                profesor=prof_comodin, dia=dia, bloque_inicio=1, bloque_fin=6
            )
            
        MateriaProfesor.objects.get_or_create(profesor=prof_comodin, materia=materia_relleno)
        # También asignamos a Francisco (Ética/Religión) como apoyo
        prof_francisco = Profesor.objects.get(nombre="Prof. Francisco")
        MateriaProfesor.objects.get_or_create(profesor=prof_francisco, materia=materia_relleno)

        # Ajustar bloques requeridos específicos por grado (ya que Materia tiene un default, 
        # pero CursoMateriaRequerida se creó con ese default. Si queremos variar bloques por grado
        # tendríamos que editar CursoMateriaRequerida aquí. 
        # En este seed, los defaults del plan coinciden con lo creado en Materia, así que está bien).

        self.stdout.write(self.style.SUCCESS(f'¡Seed REALISTA completado!'))
        self.stdout.write(f"- Cursos: {Curso.objects.count()} (12 grupos)")
        self.stdout.write(f"- Materias: {Materia.objects.count()}")
        self.stdout.write(f"- Profesores: {Profesor.objects.count()}")
        self.stdout.write(f"- Bloques Totales a Programar: {CursoMateriaRequerida.objects.count() * 5} aprox (depende de horas/materia)")

