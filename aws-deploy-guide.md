# 🚀 Guía Maestra de Despliegue: Genetic Timetable

Esta es la guía definitiva para actualizar tu proyecto. Sigue estos pasos **cada vez que hagas cambios**.

---

## 💻 PARTE 1: En tu PC (Local)

**Objetivo:** Empaquetar tu código nuevo y subirlo a la nube (Docker Hub + GitHub).

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
    *   Usa tu llave (asegúrate de estar en la carpeta donde la guardaste):
    ```powershell
    ssh -i "Generador.pem" ubuntu@52.14.216.149
    ```

2.  **Actualizar Código Base**
    ```bash
    cd genetic-timetable
    git pull origin main
    ```
    *(Si dice "Already up to date", es normal si solo cambiaste código Python y no configuración).*

3.  **Descargar las Imágenes Nuevas (Lo pesado)**
    ```bash
    docker compose -f docker-compose.prod.yml pull
    ```

4.  **Reiniciar los Contenedores**
    ```bash
    docker compose -f docker-compose.prod.yml up -d
    ```

---

## 🛠️ PARTE 3: Mantenimiento (Solo si es necesario)

Ejecuta estos comandos en el servidor AWS **solo cuando la situación lo pida**:

### 1. Si cambiaste modelos de base de datos (Tablas, Campos)
Si agregaste tablas o campos nuevos, necesitas migrar:
```bash
docker compose -f docker-compose.prod.yml exec web python manage.py migrate
```

### 2. Si la web se ve "fea" o cambiaste CSS/JS
Si los estilos no cargan, recopílalos de nuevo:
```bash
docker compose -f docker-compose.prod.yml exec web python manage.py collectstatic --noinput
```

### 3. Si necesitas crear un Administrador
Para entrar al panel `/admin`:
```bash
docker compose -f docker-compose.prod.yml exec web python manage.py createsuperuser
```

### 4. Ver si hay errores (Logs)
Si la web da Error 500, mira qué pasa en tiempo real:
```bash
# Ver logs del servidor web
docker compose -f docker-compose.prod.yml logs -f web

# Ver logs de Nginx (conexiones)
docker compose -f docker-compose.prod.yml logs -f nginx
```
*(Presiona `Ctrl + C` para salir de los logs)*
