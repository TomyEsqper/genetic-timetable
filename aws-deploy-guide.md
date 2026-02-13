# 🚀 Guía Maestra de Despliegue (Modo Aprendizaje Low-Cost)

Esta guía cubre desde la creación de la infraestructura hasta el despliegue, optimizada para aprender AWS sin gastar de más.

---

## 🏗️ PARTE 0: Crear Infraestructura AWS (Solo la primera vez)

Como borraste todo, vamos a crear un servidor nuevo optimizado para costos.

1.  **Lanzar Instancia EC2**:
    *   Ve a AWS Console -> EC2 -> **Launch Instance**.
    *   **Name**: `GeneticServer`
    *   **OS**: Ubuntu Server 24.04 LTS (o 22.04).
    *   **Instance Type**: `t3.micro` (Elegible para Free Tier).
    *   **Key Pair**: Crea una nueva llamada `GeneradorKey`. **Descarga el archivo .pem y guárdalo en la carpeta de este proyecto**.

2.  **Configurar Red (Network Settings)**:
    *   **Security Group**: Crear uno nuevo llamado `GeneticSG`.
    *   **Inbound Rules** (Reglas de entrada):
        *   SSH (Puerto 22) -> Source: My IP (Por seguridad).
        *   HTTP (Puerto 80) -> Source: Anywhere (0.0.0.0/0).
        *   HTTPS (Puerto 443) -> Source: Anywhere (0.0.0.0/0).

3.  **Storage**: Deja los 8GB por defecto (gp3).

4.  **Lanzar**: Dale click a "Launch Instance".

5.  **Obtener IP**:
    *   Ve a la lista de instancias.
    *   Copia la **Public IPv4 address** de tu nueva instancia.
    *   *Nota: Cada vez que apagues y prendas la máquina (Stop/Start), esta IP cambiará. ¡Tenlo en cuenta!*

---

## 💻 PARTE 1: Configuración Inicial del Servidor

Una vez creada la máquina, conéctate e instala lo necesario.

1.  **Conectarse por SSH**:
    En tu terminal local (carpeta del proyecto):
    ```powershell
    # Reemplaza 1.2.3.4 con tu NUEVA IP de AWS
    $Env:AWS_IP = "1.2.3.4" 
    ssh -i "GeneradorKey.pem" ubuntu@$Env:AWS_IP
    ```

2.  **Instalar Docker y Git (Copiar y pegar en el servidor)**:
    ```bash
    # Actualizar sistema
    sudo apt update && sudo apt upgrade -y

    # Instalar Docker
    sudo apt install -y docker.io docker-compose-v2 git
    
    # Dar permisos a tu usuario (para no usar sudo con docker)
    sudo usermod -aG docker $USER
    
    # Aplicar cambios de grupo (te desconectará, vuelve a entrar)
    exit
    ```
    *Vuelve a conectarte con SSH.*

3.  **Clonar el Proyecto**:
    ```bash
    git clone https://github.com/TomyEsqper/genetic-timetable.git
    cd genetic-timetable
    ```

---

## ☁️ PARTE 2: Despliegue y Configuración Dinámica

Cada vez que inicies sesión con una IP nueva:

1.  **Generar Certificados SSL**:
    *(Solo necesitas hacer esto si la IP cambió o es la primera vez)*
    ```bash
    chmod +x scripts/init_ssl.sh
    # Pasa tu IP pública actual como argumento
    ./scripts/init_ssl.sh $(curl -s ifconfig.me)
    ```

2.  **Levantar el Proyecto**:
    ```bash
    # Define la variable con tu IP actual automáticamente
    export PROD_IP=$(curl -s ifconfig.me)
    
    # Desplegar
    docker compose -f docker-compose.prod.yml down
    docker compose -f docker-compose.prod.yml up -d --build
    ```

---

## 💰 PARTE 3: Control de Costos (Checklist Anti-Gastos)

Para que tus créditos duren los 155 días:

1.  **🛑 APAGAR (Stop) cuando no uses**:
    *   En AWS Console -> Instance State -> **Stop Instance**.
    *   *No uses "Terminate" (eso borra todo). Solo "Stop".*
    *   Costo en Stop: Casi cero (solo pagas unos centavos por los 8GB de disco).

2.  **🧹 Limpieza Mensual**:
    *   Entra al servidor y ejecuta: `docker system prune -a -f` para borrar imágenes viejas que ocupan espacio.

3.  **⚠️ Al Reiniciar (Start)**:
    *   AWS te dará una **NUEVA IP**.
    *   Tendrás que volver a conectarte con la nueva IP.
    *   Tendrás que ejecutar de nuevo el paso de **Generar Certificados SSL** con la nueva IP.

---

## 🛠️ PARTE 4: Actualizaciones (Flujo Normal)

Si haces cambios en el código en tu PC:

1.  **Local**: `./scripts/deploy_hub.ps1` (Sube imágenes a Docker Hub).
2.  **Local**: `git push` (Sube cambios de config).
3.  **Servidor**: `git pull` + `docker compose ... pull` + `docker compose ... up -d`.


