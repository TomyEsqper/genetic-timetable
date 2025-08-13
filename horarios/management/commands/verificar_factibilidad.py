from django.core.management.base import BaseCommand
from collections import defaultdict

from horarios.models import (
    Curso, Materia, MateriaGrado, MateriaProfesor, DisponibilidadProfesor, BloqueHorario
)

class Command(BaseCommand):
    help = "🔎 Verifica factibilidad previa: demanda de bloques por materia vs. capacidad disponible."

    def handle(self, *args, **opts):
        bloques_clase = list(BloqueHorario.objects.filter(tipo="clase").values_list("numero", flat=True))
        cursos = list(Curso.objects.select_related("grado"))
        materias = list(Materia.objects.all())

        # DEMANDA: por materia = sum_{cursos que la dictan} materia.bloques_por_semana
        cursos_por_materia = defaultdict(list)
        for mg in MateriaGrado.objects.select_related("grado","materia"):
            for c in cursos:
                if c.grado_id == mg.grado_id:
                    cursos_por_materia[mg.materia_id].append(c)

        demanda = {}
        for m in materias:
            demanda[m.id] = len(cursos_por_materia[m.id]) * m.bloques_por_semana

        # CAPACIDAD: por materia = sum_{profes que dictan m} slots disponibles (L–V)
        capacidad = defaultdict(int)
        profs_por_materia = defaultdict(set)
        for mp in MateriaProfesor.objects.select_related("materia","profesor"):
            profs_por_materia[mp.materia_id].add(mp.profesor_id)

        disp_por_prof = defaultdict(int)
        for d in DisponibilidadProfesor.objects.all():
            disp_por_prof[d.profesor_id] += (d.bloque_fin - d.bloque_inicio + 1)

        for m in materias:
            for pid in profs_por_materia[m.id]:
                capacidad[m.id] += disp_por_prof.get(pid, 0)

        # Reporte
        self.stdout.write("📊 Resumen por materia (demanda vs capacidad):")
        ok = True
        for m in materias:
            d = demanda.get(m.id, 0)
            c = capacidad.get(m.id, 0)
            estado = "✅ OK" if c >= d else "❌ INSUFICIENTE"
            if c < d: ok = False
            self.stdout.write(f" - {m.nombre:25s} demanda={d:4d}  capacidad≈{c:4d}  {estado}")

        if ok:
            self.stdout.write(self.style.SUCCESS("\n✅ Factibilidad básica superada."))
        else:
            self.stdout.write(self.style.ERROR("\n❌ Falta capacidad en al menos una materia. Ajusta PROFES o disponibilidad."))
