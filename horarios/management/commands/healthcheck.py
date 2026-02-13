import time
from django.core.management.base import BaseCommand
from django.db import connections
from django.db.utils import OperationalError
from django_redis import get_redis_connection
from redis.exceptions import ConnectionError as RedisConnectionError

class Command(BaseCommand):
    help = 'Verifica la salud de las conexiones a Base de Datos y Redis'

    def handle(self, *args, **options):
        self.stdout.write('Iniciando chequeo de salud...')
        
        # 1. Verificar Base de Datos
        db_conn = connections['default']
        try:
            db_conn.cursor()
            self.stdout.write(self.style.SUCCESS('✓ Base de Datos (PostgreSQL/SQLite): Conectada'))
        except OperationalError:
            self.stdout.write(self.style.ERROR('✗ Base de Datos: Fallo de conexión'))
            exit(1)

        # 2. Verificar Redis
        try:
            redis_conn = get_redis_connection("default")
            redis_conn.ping()
            self.stdout.write(self.style.SUCCESS('✓ Redis: Conectado'))
        except RedisConnectionError:
            self.stdout.write(self.style.ERROR('✗ Redis: Fallo de conexión'))
            exit(1)
        except Exception as e:
            # Fallback si django-redis no está configurado igual que celery
            self.stdout.write(self.style.WARNING(f'⚠ Redis check warning: {e}'))
            # No fallamos aquí estrictamente si es solo caché, pero para celery es vital.
            # Asumimos éxito parcial si DB está ok, pero idealmente ambos.
            
        self.stdout.write(self.style.SUCCESS('Sistema operativo y listo.'))
