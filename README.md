## 🧠 Smart Schedule API – Generador Inteligente de Horarios Escolares

API potente y flexible para la **generación automática de horarios escolares**, basada en algoritmos genéticos y pensada para integrarse en plataformas educativas multi-colegio (como Phidias, entre otras).

## 🚀 Características Principales

✅ Generación automática de horarios mediante algoritmos genéticos optimizados.  
✅ Manejo de restricciones reales: materias, profesores, aulas, bloques, descansos.  
✅ Carga masiva y consulta mediante JSON (ideal para integración de múltiples colegios).  
✅ Exportación a Excel con formato profesional (colores, agrupaciones, etiquetas).  
✅ Interfaz básica para coordinadores académicos.  
✅ Seguridad integrada con **tokens JWT** y control de CORS.  
✅ Preparada para escalar en entornos multi-colegio con subdominios.

---

## 📚 **DOCUMENTACIÓN COMPLETA**

**Toda la documentación detallada se encuentra en la carpeta `/docs/`:**

- **[📖 Documentación General](docs/README.md)** - Guía completa del proyecto
- **[🚀 Inicio Rápido](docs/README_INICIO_RAPIDO.md)** - Configuración y uso inmediato
- **[🏗️ Implementación Técnica](docs/IMPLEMENTACION_COMPLETA.md)** - Detalles de implementación
- **[🔒 Sistema de Reglas Duras](docs/README_SISTEMA_REGLAS_DURAS.md)** - Reglas implementadas
- **[🔧 Configuración de Relleno](docs/README_CONFIGURACION_RELLENO.md)** - Sistema de materias de relleno
- **[🎉 Solución Final](docs/README_SOLUCION_FINAL.md)** - Estado actual del sistema
- **[⚡ Optimizaciones](docs/README_OPTIMIZACIONES.md)** - Mejoras de rendimiento
- **[🐛 Solución de Problemas](docs/SOLUCION_ERROR_DB.md)** - Troubleshooting
- **[📅 Horarios Generados](docs/README_HORARIOS_FINALES.md)** - Resultados del sistema

**[📋 Ver Índice Completo](docs/INDICE.md)**

---

## ⚙️ Tecnologías Utilizadas

- **Python 3.13**
- **Django 5.2**
- **Django REST Framework**
- **MySQL**
- **PyMySQL**
- **OpenPyXL (Excel export)**
- **Algoritmos genéticos (lógica propia)**
- **JWT (djangorestframework-simplejwt)**
- **Swagger (drf-yasg)**

---

## 🛠️ Instalación Rápida (modo desarrollo)

```bash
git clone https://github.com/tu_usuario/genetic-timetable.git
cd genetic-timetable
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
````

### Configura la base de datos en `colegio/settings.py`:

```python
DATABASES = {
  'default': {
    'ENGINE': 'django.db.backends.mysql',
    'NAME': 'gestion_horarios',
    'USER': 'tu_usuario',
    'PASSWORD': 'tu_contraseña',
    'HOST': 'localhost',
    'PORT': '3306',
  }
}
```

### Ejecuta las migraciones:

```bash
python manage.py migrate
python manage.py createsuperuser
```

---

## 📡 Endpoints API Principales

| Recurso         | Método | Endpoint              | Descripción                    |
| --------------- | ------ | --------------------- | ------------------------------ |
| Profesores      | GET    | `/api/profesores/`    | Lista de profesores            |
| Materias        | GET    | `/api/materias/`      | Lista de materias              |
| Cursos          | GET    | `/api/cursos/`        | Lista de cursos                |
| Aulas           | GET    | `/api/aulas/`         | Lista de aulas                 |
| Horarios        | GET    | `/api/horarios/`      | Consulta de horarios generados |
| Generar Horario | POST   | `/api/generar-horario/` | Ejecuta el algoritmo genético  |
| Autenticación   | POST   | `/api/token/`         | Login con usuario/contraseña   |
| Token Refresh   | POST   | `/api/token/refresh/` | Renueva el token JWT           |

---

## 🔐 Seguridad

* Todos los endpoints están protegidos con JWT (`Authorization: Bearer <token>`).
* Soporte completo para CORS (útil para integrarse en plataformas externas).
* Puedes configurar los dominios permitidos en `settings.py`:

```python
CORS_ALLOWED_ORIGINS = [
    "https://plataforma.tuempresa.com",
    "https://subdominio1.tuempresa.com",
]
```

---

## 🧬 Lógica Genética

* Cada horario es una “solución” posible.
* Se generan múltiples soluciones por curso/materia.
* Se evalúan con una función de **fitness** que penaliza colisiones, duplicados o conflictos.
* La mejor solución se guarda y exporta a Excel.

---

## 📦 Exportación a Excel

* El archivo incluye:

  * Nombre del curso
  * Materias por bloque
  * Colores por materia
  * Tiempos de descanso, almuerzo y jornada
* Exporta automáticamente en la carpeta `exports/`.

---

## 📄 Licencia

Este proyecto se distribuye bajo la licencia **MIT**.
¡Úsalo, modifícalo y mejora como desees!

---

## 🙌 Autor

Desarrollado con ❤️ por **Tomas Esquivel**
Con propósito de escalar a plataformas académicas con múltiples colegios.


