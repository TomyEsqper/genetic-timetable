import time
from django.db import connections
from django.db.utils import OperationalError
from django.core.management.base import BaseCommand
import redis
from django.conf import settings

class Command(BaseCommand):
    help = 'Espera a que la base de datos y Redis estén disponibles'

    def handle(self, *args, **options):
        self.stdout.write('Esperando servicios...')

        # 1. Esperar DB
        db_conn = None
        while not db_conn:
            try:
                db_conn = connections['default']
                db_conn.cursor() # Intenta conectar
                self.stdout.write(self.style.SUCCESS('Base de datos disponible!'))
            except OperationalError:
                self.stdout.write('Base de datos no disponible, esperando 1 segundo...')
                time.sleep(1)

        # 2. Esperar Redis (si está configurado)
        if hasattr(settings, 'CELERY_BROKER_URL'):
            redis_url = settings.CELERY_BROKER_URL
            redis_up = False
            while not redis_up:
                try:
                    r = redis.from_url(redis_url)
                    r.ping()
                    self.stdout.write(self.style.SUCCESS('Redis disponible!'))
                    redis_up = True
                except redis.ConnectionError:
                    self.stdout.write('Redis no disponible, esperando 1 segundo...')
                    time.sleep(1)

        self.stdout.write(self.style.SUCCESS('Todos los servicios están listos!'))
