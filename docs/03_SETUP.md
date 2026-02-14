# 🛠️ Guía de Setup y Desarrollo

## Requisitos
- Python 3.12+
- Docker Desktop (Recomendado para PostgreSQL/Redis)
- Virtualenv (Si desarrollas sin Docker)

## Instalación

1. **Clonar y entorno virtual**:
   ```bash
   git clone https://github.com/tomyesqper/genetic-timetable.git
   cd genetic-timetable
   python -m venv .venv
   .\.venv\Scripts\activate  # Windows
   pip install -r requirements.txt
   ```

2. **Variables de Entorno**:
   Crea un archivo `.env` en la raíz (puedes copiar `.env.example`).
   - Para usar **PostgreSQL** (Docker), define `DB_ENGINE=django.db.backends.postgresql`.
   - Para usar **SQLite** (Local simple), define `DB_ENGINE=django.db.backends.sqlite3` o déjalo vacío.

3. **Iniciar Infraestructura (Docker)**:
   Si vas a usar PostgreSQL y Redis (Recomendado):
   ```bash
   docker compose up -d
   ```

4. **Base de Datos (Migraciones)**:
   ```bash
   python manage.py migrate
   ```

5. **Datos de Prueba (Seeding)**:
   El sistema incluye un comando para poblar la BD con datos de prueba realistas.
   ```bash
   python manage.py seed_data
   ```

## Comandos Útiles

- **Generar Horarios (CLI)**:
  ```bash
  python manage.py generar_horarios --verbose
  ```
- **Limpiar Horarios**:
  ```bash
  python manage.py generar_horarios --limpiar-antes --validar-solo
  ```
- **Correr Tests (Unitarios)**:
  ```bash
  pytest
  ```
- **Correr Tests de Carga (Locust)**:
  ```bash
  locust -f tests/load_test.py --host=http://localhost:8000
  ```

## Estructura de Tests
Los tests están ubicados en `horarios/tests/` y usan `pytest`.
- `test_validaciones.py`: Pruebas unitarias de las reglas duras.
- `test_models.py`: Integridad de modelos.
