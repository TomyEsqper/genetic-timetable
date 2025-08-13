# horarios/management/commands/diagnostico_horarios.py
from django.core.management.base import BaseCommand
from typing import Dict, List
import csv

from horarios.models import (
    ConfiguracionColegio, BloqueHorario, Curso,
    Profesor, Materia, MateriaGrado, MateriaProfesor,
    DisponibilidadProfesor
)

def get_dias_clase() -> List[str]:
    cfg = ConfiguracionColegio.objects.first()
    if not cfg or not cfg.dias_clase:
        return ['lunes', 'martes', 'miércoles', 'jueves', 'viernes']
    return [d.strip().lower() for d in cfg.dias_clase.split(',') if d.strip()]

def get_bloques_clase() -> List[int]:
    return list(BloqueHorario.objects.filter(tipo='clase').order_by('numero').values_list('numero', flat=True))

def capacidad_curso_semanal() -> int:
    dias = get_dias_clase()
    bloques = get_bloques_clase()
    return len(dias) * len(bloques)

def demanda_por_curso() -> Dict[int, int]:
    """Suma de bloques_por_semana de TODAS las materias del grado del curso."""
    demanda: Dict[int, int] = {}
    for curso in Curso.objects.select_related('grado').all():
        total = 0
        for mg in MateriaGrado.objects.filter(grado=curso.grado).select_related('materia'):
            total += mg.materia.bloques_por_semana
        demanda[curso.id] = total
    return demanda

def materias_de_grado_por_curso() -> Dict[int, List[Materia]]:
    out: Dict[int, List[Materia]] = {}
    for curso in Curso.objects.select_related('grado').all():
        mats = list(Materia.objects.filter(materiagrado__grado=curso.grado).distinct())
        out[curso.id] = mats
    return out

def oferta_slots_profesor(profesor_id: int) -> int:
    """
    Cuenta (día,bloque) disponibles del profesor en bloques tipo 'clase' y días reales.
    Es una cota superior de lo que puede dictar semanalmente.
    """
    dias = set(get_dias_clase())
    bloques = set(get_bloques_clase())
    total = 0
    for disp in DisponibilidadProfesor.objects.filter(profesor_id=profesor_id):
        if disp.dia.lower() not in dias:
            continue
        for b in range(disp.bloque_inicio, disp.bloque_fin + 1):
            if b in bloques:
                total += 1
    return total

def oferta_por_materia() -> Dict[int, int]:
    """Suma slots potenciales de todos los profesores que pueden dictar cada materia."""
    oferta: Dict[int, int] = {}
    for m in Materia.objects.all():
        total = 0
        for mp in MateriaProfesor.objects.filter(materia=m).select_related('profesor'):
            total += oferta_slots_profesor(mp.profesor_id)
        oferta[m.id] = total
    return oferta

def demanda_por_materia_global() -> Dict[int, int]:
    """Suma global de bloques_por_semana en todos los grados donde aparece cada materia."""
    dem: Dict[int, int] = {}
    for mg in MateriaGrado.objects.select_related('materia', 'grado'):
        m = mg.materia
        dem[m.id] = dem.get(m.id, 0) + m.bloques_por_semana
    return dem

class Command(BaseCommand):
    help = "Diagnóstico de factibilidad: capacidad vs demanda, oferta por materia, datos faltantes y alertas de aulas."

    def add_arguments(self, parser):
        parser.add_argument("--csv", type=str, default=None, help="Ruta para exportar CSV de cuellos de botella por materia.")
        parser.add_argument("--detallado", action="store_true", help="Imprime listados detallados por curso/materia/profesor.")

    def handle(self, *args, **options):
        dias = get_dias_clase()
        bloques = get_bloques_clase()
        cap_semanal = capacidad_curso_semanal()

        self.stdout.write(self.style.SUCCESS("== DIAGNÓSTICO DE FACTIBILIDAD =="))
        self.stdout.write(f"Días de clase: {dias}")
        self.stdout.write(f"Bloques 'clase' por día: {len(bloques)} ({list(bloques)})")
        self.stdout.write(f"Capacidad semanal por curso: {cap_semanal}\n")

        # 1) Cursos: capacidad vs demanda
        dem_curso = demanda_por_curso()
        cursos_inviables = []
        for curso in Curso.objects.all():
            demanda = dem_curso.get(curso.id, 0)
            if demanda > cap_semanal:
                cursos_inviables.append((curso, demanda))
        if cursos_inviables:
            self.stdout.write(self.style.ERROR("Cursos con demanda > capacidad (ajustar bloques_por_semana o la malla):"))
            for curso, demanda in cursos_inviables:
                self.stdout.write(f" - {curso.nombre}: demanda={demanda}, capacidad={cap_semanal}")
        else:
            self.stdout.write(self.style.SUCCESS("OK: Ningún curso supera su capacidad semanal."))

        # 2) Materias: demanda global vs oferta de profesores
        dem_mat = demanda_por_materia_global()
        of_mat = oferta_por_materia()
        cuellos = []  # (ratio, materia, demanda, oferta)
        for m in Materia.objects.all():
            demanda = dem_mat.get(m.id, 0)
            oferta = of_mat.get(m.id, 0)
            ratio = (demanda / oferta) if oferta > 0 else float('inf')
            cuellos.append((ratio, m, demanda, oferta))
        cuellos.sort(key=lambda x: x[0], reverse=True)

        self.stdout.write("\nPosibles CUELLOS DE BOTELLA (demanda vs oferta teórica):")
        for ratio, m, dem, ofr in cuellos[:10]:
            flag = self.style.ERROR if ratio > 1.0 else self.style.SUCCESS
            ratio_txt = "∞" if ofr == 0 and dem > 0 else f"{ratio:0.2f}"
            self.stdout.write(flag(f" - {m.nombre}: demanda={dem}, oferta={ofr}, ratio={ratio_txt}"))

        # 3) Datos faltantes
        sin_prof = (Materia.objects
                    .filter(materiagrado__isnull=False)
                    .exclude(id__in=MateriaProfesor.objects.values('materia_id'))
                    .distinct())
        if sin_prof.exists():
            self.stdout.write(self.style.ERROR("\nMaterias con grado pero SIN profesor asignado (MateriaProfesor):"))
            for m in sin_prof:
                self.stdout.write(f" - {m.nombre}")
        else:
            self.stdout.write(self.style.SUCCESS("\nOK: Todas las materias con grado tienen al menos un profesor."))

        prof_sin_disp = Profesor.objects.exclude(
            id__in=DisponibilidadProfesor.objects.values('profesor_id')
        )
        if prof_sin_disp.exists():
            self.stdout.write(self.style.WARNING("\nProfesores SIN disponibilidad registrada:"))
            for p in prof_sin_disp:
                self.stdout.write(f" - {p.nombre}")
        else:
            self.stdout.write(self.style.SUCCESS("\nOK: Todos los profesores tienen alguna disponibilidad."))

        mats_esp = Materia.objects.filter(requiere_aula_especial=True)
        if mats_esp.exists():
            self.stdout.write(self.style.WARNING("\nMaterias que requieren aula especial (revisar aulas fijas de cursos):"))
            for m in mats_esp:
                self.stdout.write(f" - {m.nombre}")
            cursos_alerta = []
            for curso in Curso.objects.select_related('aula_fija', 'grado'):
                if not curso.aula_fija:
                    continue
                if curso.aula_fija.tipo == 'comun':
                    if MateriaGrado.objects.filter(grado=curso.grado, materia__requiere_aula_especial=True).exists():
                        cursos_alerta.append(curso.nombre)
            if cursos_alerta:
                self.stdout.write(self.style.ERROR("Cursos con aula 'comun' y materias especiales en su grado (revisar asignación de aulas):"))
                for c in sorted(set(cursos_alerta)):
                    self.stdout.write(f" - {c}")
        else:
            self.stdout.write(self.style.SUCCESS("\nOK: No hay materias marcadas como 'requiere_aula_especial'."))

        # 4) Export CSV opcional
        csv_path = options.get("csv")
        if csv_path:
            with open(csv_path, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["materia_id", "materia_nombre", "demanda_total", "oferta_total", "ratio"])
                for ratio, m, dem, ofr in cuellos:
                    ratio_val = "" if (ofr == 0 and dem > 0) else f"{ratio:0.4f}"
                    w.writerow([m.id, m.nombre, dem, ofr, ratio_val])
            self.stdout.write(self.style.SUCCESS(f"\nCSV exportado: {csv_path}"))

        # 5) Resumen y recomendaciones
        self.stdout.write(self.style.SUCCESS("\n== RESUMEN =="))
        cuello_malo = [c for c in cuellos if (c[0] > 1.0 or (c[3] == 0 and c[2] > 0))]
        self.stdout.write(f"- Cursos inviables: {len(cursos_inviables)}")
        self.stdout.write(f"- Materias con oferta < demanda: {len(cuello_malo)}")
        self.stdout.write("\nSugerencias:")
        self.stdout.write("• Bajar bloques_por_semana o aumentar capacidad (días/bloques) en cursos que superan su tope.")
        self.stdout.write("• Añadir profesores a materias cuello de botella y/o ampliar su DisponibilidadProfesor.")
        self.stdout.write("• Validar materias especiales y aulas fijas (no usar 'comun' si requieren laboratorio/arte/etc.).")
        self.stdout.write("• Reintentar generación en modo rápido tras los ajustes.") 