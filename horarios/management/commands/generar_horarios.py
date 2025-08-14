from django.core.management.base import BaseCommand
import time, json, sys
from horarios.genetico_funcion import generar_horarios_genetico

class Command(BaseCommand):
	help = "Ejecuta la generación de horarios (GA) con parámetros CLI (reproducible)."

	def add_arguments(self, parser):
		parser.add_argument('--poblacion_size', type=int, default=100)
		parser.add_argument('--generaciones', type=int, default=500)
		parser.add_argument('--prob_cruce', type=float, default=0.85)
		parser.add_argument('--prob_mutacion', type=float, default=0.25)
		parser.add_argument('--elite', type=int, default=4)
		parser.add_argument('--paciencia', type=int, default=25)
		parser.add_argument('--timeout_seg', type=int, default=180)
		parser.add_argument('--semilla', type=int, default=42)
		parser.add_argument('--workers', type=int, default=1)
		parser.add_argument('--output_json', type=str, default=None, help='Ruta para guardar el resultado en JSON')

	def handle(self, *args, **opts):
		inicio = time.time()
		res = generar_horarios_genetico(
			poblacion_size=opts['poblacion_size'],
			generaciones=opts['generaciones'],
			prob_cruce=opts['prob_cruce'],
			prob_mutacion=opts['prob_mutacion'],
			elite=opts['elite'],
			paciencia=opts['paciencia'],
			timeout_seg=opts['timeout_seg'],
			semilla=opts['semilla'],
			workers=opts['workers'],
		)
		if opts['output_json']:
			with open(opts['output_json'], 'w', encoding='utf-8') as f:
				json.dump(res, f, ensure_ascii=False, indent=2)
		self.stdout.write(self.style.SUCCESS(
			f"Listo en {time.time()-inicio:.2f}s - exito={res.get('exito')} timeout={res.get('timeout')} gen={res.get('generaciones_completadas')} fitness={res.get('mejor_fitness')}"
		)) 