from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model


class Command(BaseCommand):
    """
    Comando para asegurar la existencia de un superusuario.
    Útil para despliegues automatizados donde no hay interacción de shell.
    
    Uso:
    python manage.py ensure_admin --username=admin --password=pass --email=admin@example.com
    """
    help = "Crea o actualiza un superusuario de forma no interactiva (sin borrar otros datos)."

    def add_arguments(self, parser):
        parser.add_argument("--username", required=True, help="Nombre de usuario del superadmin (p.ej. admin)")
        parser.add_argument("--password", required=True, help="Contraseña del superadmin")
        parser.add_argument("--email", default="admin@example.com", help="Email del superadmin")

    def handle(self, *args, **options):
        username = options["username"]
        password = options["password"]
        email = options["email"]

        if not username or not password:
            raise CommandError("Debe proporcionar --username y --password")

        User = get_user_model()
        user, created = User.objects.get_or_create(username=username)

        # Asegurar flags y credenciales
        user.email = email
        user.is_superuser = True
        user.is_staff = True
        user.set_password(password)
        user.save()

        if created:
            self.stdout.write(self.style.SUCCESS(f"✅ Superusuario creado: {username}"))
        else:
            self.stdout.write(self.style.SUCCESS(f"✅ Superusuario actualizado: {username}")) 