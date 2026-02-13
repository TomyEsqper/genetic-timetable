# 🛠️ Guía de Setup y Desarrollo

## Requisitos
- Python 3.12+
- SQLite (Configurado por defecto)
- Virtualenv

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
   Crea un archivo `.env` en la raíz (ver `.env.example` si existe, o usar configuración default en `settings.py`).

3. **Base de Datos**:
   ```bash
   python manage.py migrate
   ```

4. **Datos de Prueba (Seeding)**:
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
- **Correr Tests**:
  ```bash
  pytest
  ```

## Estructura de Tests
Los tests están ubicados en `horarios/tests/` y usan `pytest`.
- `test_validaciones.py`: Pruebas unitarias de las reglas duras.
- `test_models.py`: Integridad de modelos.
