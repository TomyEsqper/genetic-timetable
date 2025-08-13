from django.core.management.base import BaseCommand
from django.db import transaction
from datetime import time
import random

from horarios.models import (
    ConfiguracionColegio, Grado, Curso, Aula, BloqueHorario,
    Materia, Profesor, MateriaGrado, MateriaProfesor, DisponibilidadProfesor,
    Horario
)

NOMBRES = [
    "Carlos", "María", "Luisa", "Andrés", "Paula", "Julián", "Camila", "Sergio",
    "Daniela", "Felipe", "Laura", "Santiago", "Carolina", "Valeria", "Natalia",
    "Jorge", "Liliana", "Hernán", "Diego", "Mónica", "Pedro", "Sofía", "Adriana",
    "Juan", "Sara", "Esteban", "Diana", "Ricardo", "Gloria", "Óscar", "Álvaro",
]
APELLIDOS = [
    "Gómez", "Pérez", "Rodríguez", "Martínez", "García", "López", "Hernández",
    "Sánchez", "Ramírez", "Torres", "Vargas", "Gutiérrez", "Castro", "Suárez",
    "Cortés", "Rojas", "Moreno", "Ortega", "Reyes", "Valencia", "Cárdenas",
]

MATERIAS_DEF = {
    # Comunes
    "Matemáticas": 5,
    "Lengua Castellana": 4,
    "Inglés": 3,
    "Ciencias Sociales": 3,
    "Tecnología e informática": 2,
    "Educación Física": 2,
    "Arte": 1,
    "Ética": 1,
    "Religión": 1,
    # Ciencias por áreas (usadas en secundaria)
    "Biología": 2,
    "Química": 2,
    "Física": 2,
    # Refuerzos/Proyecto para cuadrar 30
    "Proyecto": 2,
    "Profundización": 3,
    # Para primaria
    "Ciencias Naturales": 4,
}

# Malla por grado: suma EXACTA = 30 bloques/semana (6x5)
MALLA_POR_GRADO = {
    # Primaria (en este proyecto: 1° y 2°)
    "1°": [
        ("Matemáticas", 6), ("Lengua Castellana", 7), ("Ciencias Naturales", 4),
        ("Ciencias Sociales", 3), ("Inglés", 3), ("Educación Física", 2),
        ("Arte", 2), ("Tecnología e informática", 1), ("Ética", 1), ("Religión", 1),
    ],
    "2°": [
        ("Matemáticas", 6), ("Lengua Castellana", 6), ("Ciencias Naturales", 4),
        ("Ciencias Sociales", 3), ("Inglés", 3), ("Educación Física", 2),
        ("Arte", 2), ("Tecnología e informática", 2), ("Ética", 1), ("Religión", 1),
    ],
    # Secundaria baja (6°–9°)
    "6°": [
        ("Matemáticas", 5), ("Lengua Castellana", 4), ("Inglés", 3),
        ("Biología", 2), ("Química", 2), ("Física", 2),
        ("Ciencias Sociales", 3), ("Tecnología e informática", 2),
        ("Educación Física", 2), ("Arte", 1), ("Ética", 1), ("Religión", 1),
        ("Proyecto", 2),
    ],
    "7°": [
        ("Matemáticas", 5), ("Lengua Castellana", 4), ("Inglés", 3),
        ("Biología", 2), ("Química", 2), ("Física", 2),
        ("Ciencias Sociales", 3), ("Tecnología e informática", 2),
        ("Educación Física", 2), ("Arte", 1), ("Ética", 1), ("Religión", 1),
        ("Proyecto", 2),
    ],
    "8°": [
        ("Matemáticas", 5), ("Lengua Castellana", 4), ("Inglés", 3),
        ("Biología", 2), ("Química", 2), ("Física", 2),
        ("Ciencias Sociales", 3), ("Tecnología e informática", 2),
        ("Educación Física", 2), ("Arte", 1), ("Ética", 1), ("Religión", 1),
        ("Proyecto", 2),
    ],
    "9°": [
        ("Matemáticas", 5), ("Lengua Castellana", 4), ("Inglés", 3),
        ("Biología", 2), ("Química", 2), ("Física", 2),
        ("Ciencias Sociales", 3), ("Tecnología e informática", 2),
        ("Educación Física", 2), ("Arte", 1), ("Ética", 1), ("Religión", 1),
        ("Proyecto", 2),
    ],
    # Media (10°–11°)
    "10°": [
        ("Matemáticas", 5), ("Lengua Castellana", 4), ("Inglés", 3),
        ("Física", 2), ("Química", 2), ("Ciencias Sociales", 3),
        ("Tecnología e informática", 2), ("Educación Física", 2),
        ("Arte", 1), ("Ética", 1), ("Religión", 1), ("Profundización", 4),
    ],
    "11°": [
        ("Matemáticas", 5), ("Lengua Castellana", 4), ("Inglés", 3),
        ("Física", 2), ("Química", 2), ("Ciencias Sociales", 3),
        ("Tecnología e informática", 2), ("Educación Física", 2),
        ("Arte", 1), ("Ética", 1), ("Religión", 1), ("Profundización", 4),
    ],
}

AREAS = {
    "Matemáticas": "Matemáticas",
    "Lengua Castellana": "Lengua",
    "Inglés": "Inglés",
    "Ciencias Naturales": "Ciencias",
    "Biología": "Ciencias",
    "Química": "Ciencias",
    "Física": "Ciencias",
    "Ciencias Sociales": "Sociales",
    "Tecnología e informática": "Tecnología",
    "Educación Física": "Ed. Física",
    "Arte": "Arte",
    "Ética": "Humanidades",
    "Religión": "Humanidades",
    "Proyecto": "Proyecto",
    "Profundización": "Proyecto",
}

PROFES_POR_AREA = {
    "Matemáticas": 4,
    "Lengua": 4,
    "Inglés": 3,
    "Ciencias": 6,
    "Sociales": 3,
    "Tecnología": 3,
    "Ed. Física": 3,
    "Arte": 2,
    "Humanidades": 2,
    "Proyecto": 2,
}

SECCIONES_DEF = {
    "1°": ["A", "B", "C"],
    "2°": ["A", "B", "C"],
    "6°": ["A", "B", "C"],
    "7°": ["A", "B", "C"],
    "8°": ["A", "B", "C"],
    "9°": ["A", "B", "C"],
    "10°": ["A", "B"],
    "11°": ["A", "B"],
}

def _crear_nombre_profesor():
    return f"{random.choice(NOMBRES)} {random.choice(APELLIDOS)}"

class Command(BaseCommand):
    help = "💾 Carga un dataset realista (sin choques y con demanda/capacidad balanceada)."

    def add_arguments(self, parser):
        parser.add_argument("--purge", action="store_true", help="Borra todo antes de sembrar.")
        parser.add_argument("--bloques", type=int, default=6, help="Bloques por día (default 6).")
        parser.add_argument("--duracion", type=int, default=50, help="Duración del bloque en minutos (default 50).")

    @transaction.atomic
    def handle(self, *args, **opts):
        if opts["purge"]:
            self.stdout.write("🧹 Limpiando tablas…")
            Horario.objects.all().delete()
            DisponibilidadProfesor.objects.all().delete()
            MateriaProfesor.objects.all().delete()
            MateriaGrado.objects.all().delete()
            Curso.objects.all().delete()
            Aula.objects.all().delete()
            Profesor.objects.all().delete()
            Materia.objects.all().delete()
            Grado.objects.all().delete()
            BloqueHorario.objects.all().delete()
            ConfiguracionColegio.objects.all().delete()

        self.stdout.write("⚙️  Configurando colegio…")
        ConfiguracionColegio.objects.get_or_create(
            jornada="mañana",
            bloques_por_dia=opts["bloques"],
            duracion_bloque=opts["duracion"],
            dias_clase="lunes,martes,miércoles,jueves,viernes",
        )

        self.stdout.write("🕘 Creando bloques de clase…")
        self._crear_bloques(opts["bloques"], opts["duracion"])

        self.stdout.write("🏫 Creando grados y cursos…")
        grados = self._crear_grados_y_cursos()

        self.stdout.write("📚 Creando materias…")
        materias = self._crear_materias()

        self.stdout.write("🧑‍🏫 Creando profesores y relaciones…")
        profesores = self._crear_profesores_y_relaciones(materias)

        self.stdout.write("🗓️  Creando disponibilidad (L–V, bloques 1–5)…")
        self._crear_disponibilidad(profesores, opts["bloques"])

        self.stdout.write("🔗 Asignando malla por grado…")
        self._asignar_malla(grados, materias)

        self.stdout.write(self.style.SUCCESS("✅ Dataset realista cargado. ¡Listo para generar horarios!"))

    # ---------- helpers ----------
    def _crear_bloques(self, bloques_por_dia: int, duracion: int):
        h = 7  # 7:00 am
        m = 0
        for i in range(1, bloques_por_dia + 1):
            inicio = time(hour=h, minute=m)
            m_fin = m + duracion
            h_fin = h + (m_fin // 60)
            m_fin = m_fin % 60
            fin = time(hour=h_fin, minute=m_fin)
            BloqueHorario.objects.get_or_create(
                numero=i,
                tipo="clase",
                defaults={"hora_inicio": inicio, "hora_fin": fin}
            )
            # Avanzar 10 min entre bloques
            m = m_fin + 10
            h = h_fin + (m // 60)
            m = m % 60

    def _crear_grados_y_cursos(self):
        grados = {}
        aulas_creadas = []
        for nombre in SECCIONES_DEF.keys():
            grado, _ = Grado.objects.get_or_create(nombre=nombre)
            grados[nombre] = grado
            for seccion in SECCIONES_DEF[nombre]:
                aula, _ = Aula.objects.get_or_create(
                    nombre=f"{nombre}{seccion}",
                    defaults={"tipo": "comun", "capacidad": 40}
                )
                aulas_creadas.append(aula)
                Curso.objects.get_or_create(
                    nombre=f"{nombre.replace('°','')}{seccion}",
                    grado=grado,
                    defaults={"aula_fija": aula}
                )
        return grados

    def _crear_materias(self):
        creadas = {}
        for nombre, bps in MATERIAS_DEF.items():
            mat, _ = Materia.objects.get_or_create(
                nombre=nombre,
                defaults={
                    "bloques_por_semana": bps,
                    "jornada_preferida": "cualquiera",
                    "requiere_bloques_consecutivos": False,
                    "requiere_aula_especial": False,
                }
            )
            creadas[nombre] = mat
        # Materia opcional que no esté en MATERIAS_DEF pero aparezca en la malla
        if "Filosofía" in [n for lista in MALLA_POR_GRADO.values() for n,_ in lista]:
            if "Filosofía" not in creadas:
                mat, _ = Materia.objects.get_or_create(
                    nombre="Filosofía",
                    defaults={
                        "bloques_por_semana": 2,
                        "jornada_preferida": "cualquiera",
                        "requiere_bloques_consecutivos": False,
                        "requiere_aula_especial": False,
                    }
                )
                creadas["Filosofía"] = mat
        return creadas

    def _crear_profesores_y_relaciones(self, materias):
        # Crear profesores por área
        area_to_profes = {}
        for area, cantidad in PROFES_POR_AREA.items():
            profs = []
            for _ in range(cantidad):
                nombre = _crear_nombre_profesor()
                p, _ = Profesor.objects.get_or_create(nombre=nombre)
                profs.append(p)
            area_to_profes[area] = profs

        # Relacionar materias con profesores del área
        for materia_nombre, mat in materias.items():
            area = AREAS.get(materia_nombre, "Proyecto")
            profs_area = area_to_profes.get(area, [])
            # cada materia con 2–3 profes
            num = min(len(profs_area), max(2, len(profs_area)//2)) or 1
            asignados = random.sample(profs_area, k=min(num, len(profs_area))) if profs_area else []
            for p in asignados:
                MateriaProfesor.objects.get_or_create(profesor=p, materia=mat)

        # Asegurar que TODAS las materias tengan al menos 1 profesor
        for materia_nombre, mat in materias.items():
            if not MateriaProfesor.objects.filter(materia=mat).exists():
                area = AREAS.get(materia_nombre, "Proyecto")
                profs_area = area_to_profes.get(area, [])
                if profs_area:
                    MateriaProfesor.objects.get_or_create(profesor=profs_area[0], materia=mat)
        return Profesor.objects.all()

    def _crear_disponibilidad(self, profesores, bloques_por_dia):
        dias = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes']
        for p in profesores:
            for d in dias:
                # Usar TODOS los bloques disponibles (1 hasta bloques_por_dia)
                DisponibilidadProfesor.objects.get_or_create(
                    profesor=p, dia=d,
                    defaults={"bloque_inicio": 1, "bloque_fin": bloques_por_dia}
                )

    def _asignar_malla(self, grados, materias):
        # Crear MateriaGrado conforme a la malla y verificar suma=30
        for nombre_grado, lista in MALLA_POR_GRADO.items():
            grado = grados[nombre_grado]
            total = 0
            for nombre_materia, bloques in lista:
                mat = materias[nombre_materia]
                MateriaGrado.objects.get_or_create(grado=grado, materia=mat)
                total += bloques
            if total != 30:
                raise ValueError(f"La malla de {nombre_grado} suma {total}, debe ser 30.")
