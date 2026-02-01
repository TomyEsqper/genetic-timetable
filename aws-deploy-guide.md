# Guía de Despliegue en AWS (EC2 + Docker)

Esta guía está personalizada para tu servidor actual.

## Estado Actual
*   **IP Pública:** `52.14.216.149`
*   **Llave:** `Generador.pem`
*   **Usuario:** `ubuntu`

---

### ✅ Paso 1: Conexión (Ya dominado)
Si se te cierra la terminal, vuelve a entrar con:
```powershell
ssh -i "Generador.pem" ubuntu@52.14.216.149
```

### ✅ Paso 2: Memoria Swap (Listo)
*   Si al correr los comandos te salió `Text file busy` o `Device or resource busy`, **¡Es buena noticia!** Significa que ya está activa y protegida. Tu servidor no se bloqueará.

---

### ⏳ Paso 3: Instalar Docker (LO QUE SIGUE)
Copia y pega este bloque completo en tu terminal negra de Ubuntu. Instalará todo el motor de contenedores:

```bash
# 1. Agregar llave oficial de Docker
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

# 2. Agregar repositorio
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# 3. Instalar Docker Engine
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# 4. Dar permisos a tu usuario (CRÍTICO)
sudo usermod -aG docker $USER
```

� **¡ALTO AQUÍ!**
Una vez termine de correr el bloque de arriba, **tienes que salir y volver a entrar** para que los permisos funcionen.
1.  Escribe `exit` en la terminal negra.
2.  Vuelve a conectarte con el comando del Paso 1.
3.  Prueba que funcione escribiendo: `docker ps` (Si no sale error, ¡ganaste!).

---

### ⏳ Paso 4: Subir tu código
Necesitamos llevar tu código de tu PC al servidor. La mejor forma es GitHub.

**En tu PC (PowerShell):**
Si aún no has subido tu código a GitHub:
1.  Crea un repositorio en GitHub.com llamado `genetic-timetable`.
2.  Ejecuta en tu carpeta del proyecto:
    ```powershell
    git remote add origin https://github.com/TU_USUARIO_GITHUB/genetic-timetable.git
    git branch -M main
    git push -u origin main
    ```

**En el Servidor AWS (Ubuntu):**
```bash
git clone https://github.com/TU_USUARIO_GITHUB/genetic-timetable.git
cd genetic-timetable
```

---

### ⏳ Paso 5: Desplegar en Producción
Una vez tengas la carpeta `genetic-timetable` en el servidor:

```bash
# Levantar todo (Web, Base de datos, Nginx)
docker compose -f docker-compose.prod.yml up -d --build

# Configurar base de datos y estáticos
docker compose -f docker-compose.prod.yml exec web python manage.py migrate
docker compose -f docker-compose.prod.yml exec web python manage.py collectstatic --no-input
```

¡Y listo! Tu web estará en: `http://52.14.216.149`
