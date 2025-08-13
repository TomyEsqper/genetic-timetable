#!/usr/bin/env python
"""
Script para cargar datos de ejemplo ORIENTADO A SECUNDARIA (6°–11°).
- Elimina grados 1°–5° si existieran.
- Crea grados 6°–11° con cursos A y B por grado (p.ej., 6A, 6B, …, 11A, 11B).
- Materias y cargas semanales más realistas para secundaria.
- Relaciones Materia↔Grado (Proyecto solo 6–9; Profundización solo 10–11).
- Mapeo Profesor↔Materia realista (cada prof principal en 1 materia; algunos en 2).
- Disponibilidad de profesores en semana tipo (lun–vie, bloques 1–6).
"""

import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'colegio.settings')
django.setup()

from horarios.models import (
    Grado, Curso, Materia, Profesor, Aula, BloqueHorario,
    MateriaGrado, MateriaProfesor, DisponibilidadProfesor
)
from django.db import transaction

# -------------------------------
# Parámetros del dataset ejemplo
# -------------------------------

GRADOS_SECUNDARIA = ['6°', '7°', '8°', '9°', '10°', '11°']
CURSOS_POR_GRADO = ['A', 'B']   # 2 cursos por grado (ajusta si quieres más)

# 6 bloques por día (semana tipo lun–vie)
BLOQUES = [
    (1, '08:00', '09:00'),
    (2, '09:00', '10:00'),
    (3, '10:00', '11:00'),
    (4, '11:00', '12:00'),
    (5, '14:00', '15:00'),
    (6, '15:00', '16:00'),
]
DIAS = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes']

# Materias de secundaria y su carga semanal típica por curso
# (cargas “promedio” para demo; en tu modelo real puedes afinarlas por grado si lo soporta)
MATERIAS_CARGA = [
    ('Matemáticas', 5),
    ('Lengua Castellana', 4),
    ('Inglés', 3),
    ('Ciencias Sociales', 3),
    ('Física', 2),
    ('Química', 2),
    ('Biología', 2),
    ('Tecnología e informática', 2),
    ('Educación Física', 2),
    ('Arte', 1),
    ('Religión', 1),
    ('Ética', 1),
    ('Proyecto', 1),         # SOLO 6°–9°
    ('Profundización', 2),   # SOLO 10°–11°
]

# Qué materias dicta cada grado (semana tipo)
MATERIAS_POR_GRADO = {
    '6°': {'include': ['Matemáticas', 'Lengua Castellana', 'Inglés', 'Ciencias Sociales',
                       'Física', 'Química', 'Biología', 'Tecnología e informática',
                       'Educación Física', 'Arte', 'Religión', 'Ética', 'Proyecto']},
    '7°': {'include': ['Matemáticas', 'Lengua Castellana', 'Inglés', 'Ciencias Sociales',
                       'Física', 'Química', 'Biología', 'Tecnología e informática',
                       'Educación Física', 'Arte', 'Religión', 'Ética', 'Proyecto']},
    '8°': {'include': ['Matemáticas', 'Lengua Castellana', 'Inglés', 'Ciencias Sociales',
                       'Física', 'Química', 'Biología', 'Tecnología e informática',
                       'Educación Física', 'Arte', 'Religión', 'Ética', 'Proyecto']},
    '9°': {'include': ['Matemáticas', 'Lengua Castellana', 'Inglés', 'Ciencias Sociales',
                       'Física', 'Química', 'Biología', 'Tecnología e informática',
                       'Educación Física', 'Arte', 'Religión', 'Ética', 'Proyecto']},
    '10°': {'include': ['Matemáticas', 'Lengua Castellana', 'Inglés', 'Ciencias Sociales',
                        'Física', 'Química', 'Biología', 'Tecnología e informática',
                        'Educación Física', 'Arte', 'Religión', 'Ética', 'Profundización']},
    '11°': {'include': ['Matemáticas', 'Lengua Castellana', 'Inglés', 'Ciencias Sociales',
                        'Física', 'Química', 'Biología', 'Tecnología e informática',
                        'Educación Física', 'Arte', 'Religión', 'Ética', 'Profundización']},
}

# Lista de profesores (según nombres que compartiste)
PROFESORES_NOMBRES = [
    "Daniela Cortés","Diego García","Julián Valencia","Pedro Gómez","Felipe Sánchez","Álvaro Castro",
    "Óscar García","Gloria Reyes","Esteban Gutiérrez","Adriana Reyes","Carolina Torres","Sara Vargas",
    "Andrés Suárez","Natalia Vargas","Jorge López","Adriana Vargas","Julián Gutiérrez","Andrés Valencia",
    "Pedro Rodríguez","Diana Reyes","Valeria Reyes","Luisa Cortés","Julián López","Valeria Vargas",
    "Luisa Moreno","Carolina Vargas","Natalia Rojas","Paula Castro","Hernán Suárez","Adriana Ramírez",
    "Esteban Torres",
]

# Mapeo Profesor → Materia(s) (realista: 1 principal; unos pocos con 2)
# Nota: no “fijamos” nada en el solver; esto solo es el fixture de ejemplo.
PROFESOR_MATERIAS = {
    "Jorge López": ["Matemáticas"],
    "Julián Gutiérrez": ["Matemáticas"],
    "Paula Castro": ["Matemáticas"],
    "Adriana Ramírez": ["Matemáticas"],
    "Esteban Torres": ["Matemáticas"],

    "Daniela Cortés": ["Lengua Castellana"],
    "Adriana Reyes": ["Lengua Castellana"],
    "Natalia Vargas": ["Lengua Castellana"],
    "Luisa Cortés": ["Lengua Castellana"],

    "Sara Vargas": ["Inglés"],
    "Julián López": ["Inglés"],
    "Luisa Moreno": ["Inglés"],

    "Diego García": ["Ciencias Sociales", "Profundización"],  # transversal
    "Gloria Reyes": ["Ciencias Sociales"],
    "Valeria Reyes": ["Ciencias Sociales"],

    "Andrés Valencia": ["Física"],
    "Diana Reyes": ["Física"],

    "Adriana Vargas": ["Química"],
    "Pedro Rodríguez": ["Química"],

    "Esteban Gutiérrez": ["Biología"],
    "Natalia Rojas": ["Biología"],

    "Carolina Torres": ["Tecnología e informática"],
    "Esteban Gutiérrez": ["Biología"],  # ya incluido arriba (se mantiene)

    "Óscar García": ["Educación Física"],
    "Andrés Suárez": ["Educación Física"],

    "Felipe Sánchez": ["Arte"],
    "Álvaro Castro": ["Arte"],

    "Julián Valencia": ["Religión"],
    "Pedro Gómez": ["Ética"],

    "Carolina Vargas": ["Proyecto"],
    "Valeria Vargas": ["Proyecto"],
    # Profes no listados explícitamente arriba no se asignan en este ejemplo.
}

# --------------------------------------------------
# Helpers
# --------------------------------------------------

def ensure_bloques_horario():
    for numero, inicio, fin in BLOQUES:
        BloqueHorario.objects.get_or_create(
            numero=numero,
            defaults={'hora_inicio': inicio, 'hora_fin': fin, 'tipo': 'clase'}
        )

def create_or_get_materias():
    materias = {}
    for nombre, bloques in MATERIAS_CARGA:
        mat, _ = Materia.objects.get_or_create(
            nombre=nombre,
            defaults={'bloques_por_semana': bloques}
        )
        # Si ya existía, actualiza la carga si no estaba definida
        if getattr(mat, 'bloques_por_semana', None) in (None, 0):
            mat.bloques_por_semana = bloques
            mat.save(update_fields=['bloques_por_semana'])
        materias[nombre] = mat
    return materias

def create_or_get_profesores():
    profesores = {}
    for nombre in PROFESORES_NOMBRES:
        p, _ = Profesor.objects.get_or_create(nombre=nombre)
        profesores[nombre] = p
    return profesores

def create_or_get_aulas(total):
    aulas = []
    for i in range(1, total + 1):
        aula, _ = Aula.objects.get_or_create(
            nombre=f'Aula {i:02d}',
            defaults={'tipo': 'comun', 'capacidad': 40}
        )
        aulas.append(aula)
    return aulas

def limpiar_grados_primaria():
    # Elimina grados 1°–5° si existieran (y también etiquetas textuales comunes)
    nombres_borrar = ['1°','2°','3°','4°','5°','Primero','Segundo','Tercero','Cuarto','Quinto']
    Grado.objects.filter(nombre__in=nombres_borrar).delete()

def crear_grados_y_cursos(aulas):
    cursos = []
    idx_aula = 0
    for g in GRADOS_SECUNDARIA:
        grado, _ = Grado.objects.get_or_create(nombre=g)
        for secc in CURSOS_POR_GRADO:
            if idx_aula >= len(aulas):
                idx_aula = 0
            aula = aulas[idx_aula]
            idx_aula += 1
            curso, _ = Curso.objects.get_or_create(
                nombre=f"{g.replace('°','')}{secc}",  # 6A, 6B, ...
                defaults={'grado': grado, 'aula_fija': aula}
            )
            # Si el curso existía pero sin grado/aula, asegura consistencia
            if curso.grado_id != grado.id or curso.aula_fija_id != aula.id:
                curso.grado = grado
                curso.aula_fija = aula
                curso.save(update_fields=['grado', 'aula_fija'])
            cursos.append(curso)
    return cursos

def asignar_materias_a_grados(materias):
    # Crea MateriaGrado solo para las materias “include” de cada grado (6°–11°)
    total = 0
    for g, cfg in MATERIAS_POR_GRADO.items():
        grado = Grado.objects.get(nombre=g)
        for nombre_mat in cfg['include']:
            mat = materias[nombre_mat]
            MateriaGrado.objects.get_or_create(grado=grado, materia=mat)
            total += 1
    return total

def asignar_profesores_a_materias(profesores, materias):
    total = 0
    for prof_nombre, mats in PROFESOR_MATERIAS.items():
        if prof_nombre not in profesores:
            continue
        prof = profesores[prof_nombre]
        for m in mats:
            if m not in materias:
                continue
            MateriaProfesor.objects.get_or_create(profesor=prof, materia=materias[m])
            total += 1
    return total

def crear_disponibilidades(profesores):
    # Para el ejemplo, damos disponibilidad lun–vie, bloques 1–6.
    # (Si quieres hacerlo más “real”, reduce a 4 días para algunos profes o acota a bloques 1–5.)
    total = 0
    for prof in profesores.values():
        for dia in DIAS:
            _, creado = DisponibilidadProfesor.objects.get_or_create(
                profesor=prof, dia=dia,
                defaults={'bloque_inicio': 1, 'bloque_fin': 6}
            )
            if creado:
                total += 1
    return total

# --------------------------------------------------
# Carga de datos
# --------------------------------------------------

@transaction.atomic
def cargar_datos_ejemplo_secundaria():
    print("Cargando datos de ejemplo para SECUNDARIA (6°–11°)...\n")

    # 0) Eliminar primaria si existiera
    print("0) Limpiando grados 1°–5° (si existieran)...")
    limpiar_grados_primaria()

    # 1) Bloques
    print("1) Creando bloques (semana tipo)...")
    ensure_bloques_horario()
    print(f"   - Bloques: {BloqueHorario.objects.count()}")

    # 2) Aulas (una por curso)
    total_cursos = len(GRADOS_SECUNDARIA) * len(CURSOS_POR_GRADO)
    print("2) Creando aulas...")
    aulas = create_or_get_aulas(total_cursos)
    print(f"   - Aulas disponibles: {len(aulas)}")

    # 3) Grados y Cursos (6°–11°, A/B)
    print("3) Creando grados y cursos...")
    cursos = crear_grados_y_cursos(aulas)
    print(f"   - Grados: {Grado.objects.filter(nombre__in=GRADOS_SECUNDARIA).count()}")
    print(f"   - Cursos: {len(cursos)}")

    # 4) Materias
    print("4) Creando materias (con bloques/semana típicos)...")
    materias = create_or_get_materias()
    print(f"   - Materias: {len(materias)}")

    # 5) Materia↔Grado
    print("5) Asignando materias a grados...")
    mg_total = asignar_materias_a_grados(materias)
    print(f"   - Relaciones MateriaGrado creadas/aseguradas: {mg_total}")

    # 6) Profesores
    print("6) Creando profesores...")
    profesores = create_or_get_profesores()
    print(f"   - Profesores: {len(profesores)}")

    # 7) Materia↔Profesor
    print("7) Asignando profesores a materias (mapeo realista)...")
    mp_total = asignar_profesores_a_materias(profesores, materias)
    print(f"   - Relaciones MateriaProfesor creadas/aseguradas: {mp_total}")

    # 8) Disponibilidad
    print("8) Creando disponibilidad de profesores (lun–vie, bloques 1–6)...")
    disp_total = crear_disponibilidades(profesores)
    print(f"   - Registros de Disponibilidad creados: {disp_total}")

    # Resumen
    print("\n✅ Datos de ejemplo (SECUNDARIA) cargados exitosamente!")
    print("\nResumen:")
    print(f"   - Grados (6°–11°): {Grado.objects.filter(nombre__in=GRADOS_SECUNDARIA).count()}")
    print(f"   - Cursos: {len(cursos)}")
    print(f"   - Materias: {len(materias)}")
    print(f"   - Profesores: {len(profesores)}")
    print(f"   - Bloques: {BloqueHorario.objects.count()}")
    print(f"   - Materia↔Grado: {MateriaGrado.objects.count()}")
    print(f"   - Materia↔Profesor: {MateriaProfesor.objects.count()}")
    print(f"   - Disponibilidad: {DisponibilidadProfesor.objects.count()}")

    print("\n🎯 Ahora puedes:")
    print("   1) Ejecutar: python manage.py runserver")
    print("   2) Ir a: http://localhost:8000/horarios/")
    print("   3) Generar horarios con el algoritmo genético (semana tipo 6°–11°)")

if __name__ == '__main__':
    cargar_datos_ejemplo_secundaria()
