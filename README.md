# 🧠 Smart Schedule API – Generador Inteligente de Horarios Escolares

API potente y flexible para la **generación automática de horarios escolares**, basada en algoritmos genéticos y arquitectura hexagonal. Diseñada para integrarse en plataformas educativas y desplegarse fácilmente con Docker.

## 🚀 Características Principales

✅ **Generación Automática**: Algoritmos genéticos (Demand-First + Hill Climbing) para optimizar horarios.
✅ **Restricciones Reales**: Manejo de aulas fijas/especiales, disponibilidad docente, bloques contiguos, y descansos.
✅ **Arquitectura Hexagonal**: Separación clara entre Dominio, Aplicación e Infraestructura.
✅ **Docker Ready**: Configuración lista para desarrollo y producción con Nginx.
✅ **Seguridad**: Autenticación JWT y configuración segura para producción.
✅ **API RESTful**: Endpoints documentados para integración frontend/backend.

---

## ⚙️ Tecnologías Utilizadas

- **Python 3.12+**
- **Django 5.0.2**
- **Django REST Framework**
- **PostgreSQL 15** (Producción) / **SQLite** (Desarrollo local)
- **Redis** (Cola de tareas Celery + Caché)
- **Sentry** (Monitoreo de errores en tiempo real)
- **Docker & Docker Compose**
- **Nginx** (Reverse Proxy & SSL)
- **JWT** (SimpleJWT)
- **Pandas/NumPy** (Procesamiento de datos)

---

## 🛠️ Instalación y Uso (Docker)

La forma recomendada de ejecutar el proyecto es utilizando Docker.

### 1. Clonar el repositorio
```bash
git clone https://github.com/tomyesqper/genetic-timetable.git
cd genetic-timetable
```

### 2. Configurar variables de entorno
Crea un archivo `.env` (o `.env.prod` para producción) basado en el ejemplo, definiendo `SECRET_KEY` y `DEBUG`.

### 3. Iniciar con Docker Compose
```bash
# Desarrollo
docker compose up -d --build

# Producción
docker compose -f docker-compose.prod.yml up -d --build
```

### 4. Inicializar Base de Datos
Una vez el contenedor `web` esté corriendo:

```bash
# Migraciones
docker compose exec web python manage.py migrate

# Crear tabla de caché (Crítico para el rendimiento)
docker compose exec web python manage.py createcachetable

# (Opcional) Poblar con datos de prueba realistas
docker compose exec web python manage.py seed_data

# Crear superusuario
docker compose exec web python manage.py createsuperuser
```

---

## 📡 Endpoints API Principales

| Recurso | Método | Endpoint | Descripción |
|---------|--------|----------|-------------|
| **Generar** | POST | `/api/generar-horario/` | Inicia el algoritmo genético (requiere auth). |
| **Solver** | POST | `/api/engine/solve/` | Motor de cálculo puro. Recibe JSON completo, retorna horario. |
| **Estado** | GET | `/api/estado-sistema/` | Métricas y conteo de recursos del sistema. |
| **Validar** | GET | `/api/validar-prerrequisitos/` | Chequeo de factibilidad antes de generar. |
| **Auth** | POST | `/api/token/` | Obtener token JWT (Login). |

## 🧪 Ejemplos de Uso (JSON)

Para facilitar la integración y pruebas, consulta el documento de ejemplos donde encontrarás **JSONs listos para copiar y pegar** en Postman:

👉 **[Ver Ejemplos de API (Postman/JSON)](docs/API_EXAMPLES.md)**

Incluye payloads para:
*   Autenticación
*   Motor de Cálculo (Solver)
*   Generación de Horarios


---

## � Estructura del Proyecto

El proyecto sigue una arquitectura modular:

*   **`api/`**: Vistas REST, Serializers y exposición de endpoints.
*   **`horarios/`**: Núcleo de la lógica de negocio.
    *   `domain/`: Modelos, validadores y reglas de negocio.
    *   `application/`: Casos de uso y servicios (Algoritmo Genético).
    *   `infrastructure/`: Adaptadores, exportadores y utilidades.
    *   `management/commands/`: Scripts de gestión (`seed_data`, etc.).
*   **`colegio/`**: Configuración principal de Django (`settings.py`).
*   **`nginx/`**: Configuración del servidor web para producción.

---

## � Notas de Despliegue (AWS)

Para despliegue en producción (AWS EC2):

1.  Asegurar que `.env.prod` contenga `SECRET_KEY` segura y `DEBUG=False`.
2.  Usar `docker-compose.prod.yml`.
3.  Configurar certificados SSL en `nginx/certs/` (o usar Let's Encrypt).
4.  Consultar `aws-deploy-guide.md` para pasos detallados.

---

## 📄 Licencia

Este proyecto es propiedad privada. Todos los derechos reservados.
