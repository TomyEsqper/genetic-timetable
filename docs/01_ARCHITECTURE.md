# 🏛️ Arquitectura del Sistema

Este proyecto implementa una variación de **Arquitectura Hexagonal (Ports & Adapters)** adaptada a Django. El objetivo es desacoplar la lógica de negocio (reglas de horarios) del framework web.

## Estructura de Carpetas (`horarios/`)

### 1. Domain (`horarios/domain/`)
El núcleo del negocio. **No depende de Django ORM ni de librerías externas** (idealmente).
- **Models**: Entidades puras (aunque por practicidad en Django, a veces referencian `models.py`).
- **Validators**: Reglas de negocio invariantes.
  - `validador_reglas_duras.py`: Restricciones inviolables (choques de horario, profesor ocupado).
  - `validador_precondiciones.py`: Chequeos antes de intentar generar (ej. ¿hay suficientes profesores?).

### 2. Application (`horarios/application/`)
Casos de uso y orquestación. Conecta el dominio con la infraestructura.
- **Services**: Lógica de aplicación.
  - `generador_demand_first.py`: El "cerebro" que coordina la creación de horarios.

### 3. Infrastructure (`horarios/infrastructure/`)
Implementación técnica y herramientas externas.
- **Adapters**:
  - `exportador.py`: Generación de Excel.
  - `sistema_reportes.py`: Generación de JSONs de diagnóstico.
- **Utils**: Logging estructurado (JSON), serialización, tareas asíncronas (Celery/Redis).

### 4. Interface (API/Django)
- **Django Apps**: `api`, `colegio`, `frontend`.
- Estas capas consumen los servicios de `application`, nunca acceden al dominio directamente si pueden evitarlo.

## Infraestructura de Datos
El sistema soporta una arquitectura híbrida de persistencia:
- **Desarrollo Local**: SQLite (por simplicidad).
- **Producción (Docker/AWS)**: PostgreSQL 15 + Redis 7 (con persistencia AOF).
- **Monitoreo**: Sentry SDK integrado para trazas y alertas de error.

## Flujo de Datos Típico
1. **API View** recibe request POST.
2. Llama a un **Application Service** (`GeneradorDemandFirst`).
3. El servicio usa **Domain Validators** para asegurar integridad.
4. El servicio persiste resultados usando **Django Models**.
5. El servicio retorna DTOs o resultados a la vista.
