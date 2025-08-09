# Solución al Error de Conexión a la Base de Datos

## Error detectado

Se ha identificado un error de conexión a la base de datos MySQL:

```
pymysql.err.OperationalError: (1045, "Access denied for user 'root'@'localhost' (using password: YES)")
```

Este error indica que Django no puede conectarse a la base de datos MySQL porque las credenciales configuradas no son válidas o el servidor MySQL no está configurado correctamente.

## Posibles soluciones

### 1. Verificar que MySQL esté instalado y en ejecución

```powershell
# Verificar si el servicio de MySQL está en ejecución
Get-Service -Name "*mysql*"
```

Si MySQL no está en ejecución, inícielo:

```powershell
Start-Service -Name "MySQL80"
# El nombre exacto puede variar según tu instalación (MySQL80, MYSQL, etc.)
```

### 2. Verificar las credenciales de MySQL

Las credenciales configuradas en `settings.py` son:
- Usuario: `root`
- Contraseña: `Tomas2007`

Prueba si puedes conectarte a MySQL con estas credenciales:

```powershell
mysql -u root -p
# Ingresa la contraseña cuando te lo solicite
```

### 3. Restablecer la contraseña de root en MySQL

Si no puedes acceder con las credenciales actuales, puedes restablecer la contraseña de root:

1. Detén el servicio de MySQL:
   ```powershell
   Stop-Service -Name "MySQL80"
   ```

2. Inicia MySQL en modo seguro (sin verificación de privilegios):
   ```powershell
   # Navega a la carpeta bin de MySQL (ajusta la ruta según tu instalación)
   cd "C:\Program Files\MySQL\MySQL Server 8.0\bin"
   
   # Inicia MySQL en modo seguro
   .\mysqld.exe --defaults-file="C:\ProgramData\MySQL\MySQL Server 8.0\my.ini" --init-file="C:\mysql-init.txt" --console
   ```

   Antes de ejecutar el comando anterior, crea un archivo `C:\mysql-init.txt` con el siguiente contenido:
   ```
   ALTER USER 'root'@'localhost' IDENTIFIED BY 'Tomas2007';
   ```

3. Una vez que MySQL se haya iniciado en modo seguro, detén el proceso y reinicia el servicio normal:
   ```powershell
   Start-Service -Name "MySQL80"
   ```

### 4. Crear un nuevo usuario en MySQL

Alternativamente, puedes crear un nuevo usuario en MySQL y actualizar `settings.py`:

1. Conéctate a MySQL con cualquier usuario que tenga privilegios de administrador.

2. Crea un nuevo usuario y otorga privilegios:
   ```sql
   CREATE USER 'django_user'@'localhost' IDENTIFIED BY 'nueva_contraseña';
   GRANT ALL PRIVILEGES ON gestion_horarios.* TO 'django_user'@'localhost';
   FLUSH PRIVILEGES;
   ```

3. Actualiza `settings.py` con las nuevas credenciales:
   ```python
   DATABASES = {
       'default': {
           'ENGINE': 'django.db.backends.mysql',
           'NAME': 'gestion_horarios',
           'USER': 'django_user',
           'PASSWORD': 'nueva_contraseña',
           'HOST': 'localhost',
           'PORT': '3306',
       }
   }
   ```

### 5. Verificar que la base de datos exista

Asegúrate de que la base de datos `gestion_horarios` exista:

```sql
CREATE DATABASE IF NOT EXISTS gestion_horarios;
```

### 6. Usar SQLite temporalmente para desarrollo

Si continúas teniendo problemas con MySQL, puedes cambiar temporalmente a SQLite para desarrollo:

```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}
```

## Verificación

Después de aplicar alguna de las soluciones anteriores, intenta ejecutar nuevamente:

```powershell
python manage.py runserver
```

Si el problema persiste, verifica los logs de MySQL para obtener más información sobre el error de acceso.