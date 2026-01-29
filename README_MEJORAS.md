# Mejoras de Arquitectura y Refactorización

## Reestructuración a Arquitectura Hexagonal

Se ha reorganizado la estructura del proyecto siguiendo los principios de Arquitectura Hexagonal (Clean Architecture) para mejorar la mantenibilidad, escalabilidad y separación de responsabilidades.

### Estructura de Directorios

- **horarios/domain/**: Contiene la lógica de negocio pura y reglas del dominio.
  - **models.py**: Entidades del dominio (Django Models).
  - **validators/**: Reglas de validación (duras y blandas).
  - **services/**: Servicios de dominio puros (máscaras, reparación de cromosomas).

- **horarios/application/**: Casos de uso y orquestación.
  - **services/**: Servicios de aplicación (algoritmo genético, generación de horarios).

- **horarios/infrastructure/**: Implementaciones técnicas y adaptadores.
  - **adapters/**: Adaptadores de salida (exportadores, reportes, OR-Tools).
  - **utils/**: Utilidades transversales (logging, tareas asíncronas).
  - **repositories/**: (Futuro) Repositorios para acceso a datos.

### Mejoras Implementadas

1. **Separación de Concerns**: Los validadores, exportadores y lógica del algoritmo genético están desacoplados.
2. **Claridad en Imports**: Se utilizan rutas absolutas y organizadas.
3. **Mantenibilidad**: Es más fácil localizar y modificar componentes específicos sin afectar otras capas.

## Ejecución

El flujo de trabajo principal se mantiene a través de los comandos de management y la API, que ahora consumen los servicios desde sus nuevas ubicaciones.

### Comandos
- `python manage.py generar_horarios`: Ejecuta el algoritmo genético.

### Tests
- `pytest`: Ejecuta la suite de pruebas adaptada a la nueva estructura.
