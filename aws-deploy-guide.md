# 🚀 Guía Maestra de Despliegue: Genetic Timetable

Esta es la guía definitiva para actualizar tu proyecto en AWS. Sigue estos pasos **cada vez que hagas cambios**.

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
    ssh -i "Generador.pem" ubuntu@52.14.216.149
    ```

2.  **Actualizar Código Base**
    ```bash
    cd genetic-timetable
    git pull origin main
    ```
    *(Si dice "Already up to date", es normal si solo cambiaste código Python y no configuración).*

3.  **Generar Certificados SSL (Solo la primera vez o si expiran)**
    Como ahora usamos HTTPS, necesitamos certificados. Ejecuta esto una vez:
    ```bash
    mkdir -p nginx/certs
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 -keyout nginx/certs/selfsigned.key -out nginx/certs/selfsigned.crt -subj "/C=US/ST=State/L=City/O=Organization/CN=localhost"
    ```

4.  **Descargar las Imágenes Nuevas y Reiniciar**
    ```bash
    # Bajar versiones recientes
    docker compose -f docker-compose.prod.yml pull

    # Reiniciar contenedores
    docker compose -f docker-compose.prod.yml up -d
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
