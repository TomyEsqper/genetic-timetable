# horarios/management/commands/diagnostico_horarios.py
from django.core.management.base import BaseCommand
from django.db import transaction
from horarios.models import Slot, BloqueHorario, DisponibilidadProfesor, ProfesorSlot, Curso, Materia, MateriaGrado, CursoMateriaRequerida

class Command(BaseCommand):
	help = "Materializa ProfesorSlot y sincroniza CursoMateriaRequerida"

	def add_arguments(self, parser):
		parser.add_argument('--sync-slots', action='store_true', help='Reconstruir tabla Slot a partir de BloqueHorario y dias de ConfiguracionColegio')
		parser.add_argument('--materialize-profesorslot', action='store_true', help='Materializar ProfesorSlot desde DisponibilidadProfesor')
		parser.add_argument('--sync-cursomateriarequerida', action='store_true', help='Sincronizar CursoMateriaRequerida desde MateriaGrado/Materia')

	def handle(self, *args, **options):
		if options['sync_slots']:
			self.stdout.write('Sincronizando Slot...')
			self._sync_slots()
			self.stdout.write(self.style.SUCCESS('OK'))
		if options['materialize_profesorslot']:
			self.stdout.write('Materializando ProfesorSlot...')
			self._materialize_profesor_slot()
			self.stdout.write(self.style.SUCCESS('OK'))
		if options['sync_cursomateriarequerida']:
			self.stdout.write('Sincronizando CursoMateriaRequerida...')
			self._sync_curso_materia_requerida()
			self.stdout.write(self.style.SUCCESS('OK'))

	def _sync_slots(self):
		from horarios.models import ConfiguracionColegio
		conf = ConfiguracionColegio.objects.first()
		dias = [d.strip() for d in (conf.dias_clase if conf else 'lunes,martes,miércoles,jueves,viernes').split(',')]
		with transaction.atomic():
			Slot.objects.all().delete()
			bloques = list(BloqueHorario.objects.filter(tipo='clase').order_by('numero').values('numero','hora_inicio','hora_fin','tipo'))
			nuevos = []
			for d in dias:
				for b in bloques:
					nuevos.append(Slot(dia=d, bloque=b['numero'], hora_inicio=b['hora_inicio'], hora_fin=b['hora_fin'], tipo=b['tipo']))
			Slot.objects.bulk_create(nuevos, batch_size=1000)

	def _materialize_profesor_slot(self):
		from django.db.models import Q
		slots = {(s.dia, s.bloque): s.id for s in Slot.objects.all().only('id','dia','bloque')}
		rows = []
		for disp in DisponibilidadProfesor.objects.all().only('profesor_id','dia','bloque_inicio','bloque_fin'):
			for bloque in range(disp.bloque_inicio, disp.bloque_fin + 1):
				slot_id = slots.get((disp.dia, bloque))
				if slot_id:
					rows.append(ProfesorSlot(profesor_id=disp.profesor_id, slot_id=slot_id))
		with transaction.atomic():
			ProfesorSlot.objects.all().delete()
			ProfesorSlot.objects.bulk_create(rows, batch_size=1000, ignore_conflicts=True)

	def _sync_curso_materia_requerida(self):
		# Derivar bloques_requeridos por curso-materia desde MateriaGrado y Materia.bloques_por_semana
		# Asignamos a cada curso de un grado los bloques de cada materia del plan del grado
		curso_por_grado = {}
		for c in Curso.objects.all().only('id','grado_id'):
			curso_por_grado.setdefault(c.grado_id, []).append(c.id)
		rows = []
		for mg in MateriaGrado.objects.select_related('materia').all():
			bloques = mg.materia.bloques_por_semana
			for curso_id in curso_por_grado.get(mg.grado_id, []):
				rows.append(CursoMateriaRequerida(curso_id=curso_id, materia_id=mg.materia_id, bloques_requeridos=bloques))
		with transaction.atomic():
			CursoMateriaRequerida.objects.all().delete()
			CursoMateriaRequerida.objects.bulk_create(rows, batch_size=1000, ignore_conflicts=True) 