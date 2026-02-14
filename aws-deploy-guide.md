# 🚀 Guía Maestra de Despliegue: Genetic Timetable

Esta es la guía definitiva para actualizar tu proyecto en AWS. Sigue estos pasos **cada vez que hagas cambios**.

> 💡 **Tip Pro:** Si tienes configurado **GitHub Actions**, el despliegue es **automático** al hacer `git push origin main`. No necesitas seguir la Parte 1 ni la Parte 2 manualmente a menos que el pipeline falle.

---

## 💻 PARTE 1: En tu PC (Local)

**Objetivo:** Empaquetar tu código nuevo y subirlo a la nube (Docker Hub).

1.  **Guarda tus cambios** en Visual Studio Code.
2.  **Construir y Subir Imágenes a Docker Hub**
    *   Abre una terminal **PowerShell** en la carpeta del proyecto.
    *   Ejecuta el script automático:
    ```powershell
    ./scripts/deploy_hub.ps1
    ```
    *(Este script compila todo y lo sube a la nube para que tu servidor AWS no tenga que esforzarse).*

3.  **Subir cambios de configuración a GitHub**
    *   Si modificaste archivos como `docker-compose.prod.yml`, `settings.py` o `.env`:
    ```powershell
    git add .
    git commit -m "Actualización: describir cambios"
    git push origin main
    ```

---

## ☁️ PARTE 2: En tu Servidor AWS (Remoto)

**Objetivo:** Descargar lo nuevo y reiniciar.

1.  **Conectarse al Servidor**
    *   Abre una terminal nueva (PowerShell o CMD).
    *   Usa tu llave `.pem` (asegúrate de estar en la carpeta donde la guardaste):
    ```powershell
    ssh -i "GeneradorKey.pem" ubuntu@18.188.89.221
    ```

2.  **Actualizar Código Base**
    ```bash
    cd genetic-timetable
    git pull origin main
    ```
    *(Si dice "Already up to date", es normal si solo cambiaste código Python y no configuración).*

---

## 3. Configuración del Archivo .env (CRÍTICO)

Asegúrate de que tu archivo `.env` en el servidor contenga la IP correcta:
```bash
PROD_IP=18.188.89.221
ALLOWED_HOSTS=localhost,127.0.0.1,18.188.89.221
CSRF_TRUSTED_ORIGINS=https://18.188.89.221,http://18.188.89.221
SENTRY_DSN=tu_url_de_sentry_aqui
```

---

## 4. Configuración Inicial (Solo la primera vez)

Si es la **primera vez** que despliegas (o borraste la base de datos), necesitas configurar lo siguiente:

1.  **Crear Superusuario (Admin)**:
    Para poder entrar al panel de administración (`/admin`):
    ```bash
    docker compose -f docker-compose.prod.yml exec web python manage.py createsuperuser
    ```
    *Sigue las instrucciones para poner usuario y contraseña.*

2.  **Verificar Base de Datos**:
    El sistema ahora intenta crear las tablas automáticamente al iniciar. Si aún tienes errores, ejecuta esto manualmente:
    ```bash
    docker compose -f docker-compose.prod.yml exec web python manage.py migrate
    ```

## 5. Configuración de HTTPS y Certificados (CRÍTICO)

Para que HTTPS funcione, necesitas generar los certificados SSL. Hemos creado un script para facilitar esto.

1.  **Generar Certificados**:
    Ejecuta el siguiente comando en la raíz del proyecto en tu instancia AWS:
    ```bash
    chmod +x scripts/init_ssl.sh
    ./scripts/init_ssl.sh
    ```
    *Esto creará `nginx/certs/selfsigned.crt` y `nginx/certs/selfsigned.key`.*

2.  **Verificar Security Group (Firewall)**:
    Asegúrate de que tu instancia EC2 tenga los siguientes puertos abiertos en el **Security Group**:
    -   **80 (HTTP)**: 0.0.0.0/0
    -   **443 (HTTPS)**: 0.0.0.0/0
    *Si el puerto 443 está cerrado, HTTPS fallará y dará timeout.*

## 6. Despliegue con Docker Compose

La configuración ahora es dinámica. El archivo `docker-compose.prod.yml` usa la variable `PROD_IP` definida en tu `.env`.

```bash
# Actualizar y reiniciar
docker-compose -f docker-compose.prod.yml down
docker-compose -f docker-compose.prod.yml up -d --build
```

### Troubleshooting HTTPS
- Si ves una advertencia de "Sitio no seguro", es normal porque usamos un certificado autofirmado. Acepta el riesgo para continuar.
- Si la conexión es rechazada o da timeout, verifica nuevamente el **Security Group** en AWS.
- Si obtienes un error 500/502, revisa los logs de Nginx:
    ```bash
    docker-compose -f docker-compose.prod.yml logs nginx
    ```

---


## 🛠️ PARTE 3: Mantenimiento (Solo si es necesario)

Ejecuta estos comandos en el servidor AWS **solo cuando la situación lo pida**:

### 1. Migraciones de Base de Datos
Si agregaste tablas o campos nuevos:
```bash
docker compose -f docker-compose.prod.yml exec web python manage.py migrate
```

### 2. Tabla de Caché
Si ves errores de caché o 500 en endpoints nuevos:
```bash
docker compose -f docker-compose.prod.yml exec web python manage.py createcachetable
```

### 3. Archivos Estáticos
Si la web se ve "fea" o cambiaste CSS/JS:
```bash
docker compose -f docker-compose.prod.yml exec web python manage.py collectstatic --noinput
```

### 4. Limpieza de Disco (Mantenimiento Proactivo)
El pipeline de CI/CD ya limpia imágenes antiguas automáticamente y verifica el espacio antes de cada despliegue. Si el disco supera el **90%**, el sistema intentará una limpieza profunda (`prune -af`) antes de fallar.

Si necesitas liberar espacio manualmente:

```bash
# Eliminar imágenes huérfanas (dangling)
docker image prune

# Limpieza total (imágenes no usadas, redes y cache de construcción)
# CUIDADO: Esto obligará a descargar todo de nuevo en el próximo deploy
docker system prune -af
```

**Monitoreo de Espacio:**
El despliegue ahora fallará o emitirá una alerta si el disco supera el **90%**. Puedes revisarlo manualmente con:
```bash
df -h /
```

### 4. Crear Administrador
Para entrar al panel `/admin`:
```bash
docker compose -f docker-compose.prod.yml exec web python manage.py createsuperuser
```

### 5. Ver Logs (Errores 500)
```bash
# Ver logs del servidor web
docker compose -f docker-compose.prod.yml logs -f web --tail=100

# Ver logs de Nginx (conexiones)
docker compose -f docker-compose.prod.yml logs -f nginx --tail=100
```
*(Presiona `Ctrl + C` para salir de los logs)*

### 6. Liberar Espacio en Disco
Si AWS dice "no space left on device":
```bash
# Borrar todo lo que no se esté usando (imágenes viejas, cachés, contenedores parados)
docker system prune -a -f

# Borrar volúmenes huérfanos
docker volume prune -f

# Verificar espacio disponible
df -h
```