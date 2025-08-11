# Mejoras Implementadas - Sistema de Generación de Horarios Escolares

## Resumen de Mejoras

Este proyecto ha sido endurecido y escalado para manejar grandes volúmenes de datos con las siguientes mejoras:

### 1. Dependencias Optimizadas
- **Numba**: JIT compilation para funciones críticas
- **django-redis**: Cache y sesiones con Redis
- **pytest-django**: Testing mejorado
- **ProcessPoolExecutor**: Paralelismo optimizado

### 2. Restricciones de Base de Datos
- **UniqueConstraint** en `Horario` para evitar solapes:
  - `(curso, dia, bloque)` - Un curso no puede tener dos materias en el mismo día y bloque
  - `(profesor, dia, bloque)` - Un profesor no puede estar en dos lugares al mismo tiempo
- **UniqueConstraint** en `BloqueHorario` para `(numero, tipo)`
- Campo `aula_fija` en `Curso` para asignación fija de aulas

### 3. Algoritmo Genético Optimizado
- **Carga a memoria**: Todos los datos se cargan antes del loop evolutivo
- **Mapeos optimizados**: `id → índice` para acceso rápido
- **Arrays NumPy**: Estructuras vectorizadas para evaluación
- **Numba JIT**: Funciones críticas compiladas con `@njit(nopython=True, fastmath=True)`
- **ProcessPoolExecutor**: Paralelismo en evaluación de población
- **Early stopping**: Detiene cuando no hay mejora en `paciencia` generaciones
- **Timeout**: Control de tiempo máximo de ejecución
- **Logs JSON**: Métricas detalladas por generación

### 4. API Mejorada
- **Validaciones**: Prerrequisitos verificados antes de ejecutar GA
- **Métricas**: Respuesta con estadísticas completas del proceso
- **Códigos de error**: 409 para prerrequisitos no cumplidos, 400 para errores de validación
- **Parámetros configurables**: Todos los parámetros del GA son opcionales con defaults

### 5. Datasets Escalables
- **Management command**: `python manage.py cargar_dataset --size {S|M|L|XL}`
- **Tamaños predefinidos**:
  - S: 10 cursos, 15 profes, 12 materias, 6 bloques/día
  - M: 30 cursos, 40 profes, 18 materias, 7 bloques/día
  - L: 60 cursos, 80 profes, 22 materias, 8 bloques/día
  - XL: 100 cursos, 150 profes, 26 materias, 8 bloques/día

### 6. Tests Completos
- **Correctitud**: Verificación de restricciones sin solapes
- **Rendimiento**: Tests de tiempo para diferentes tamaños
- **Validaciones**: Tests de prerrequisitos
- **Paralelismo**: Verificación de funcionamiento multi-proceso

### 7. Exportación CSV
- **Horario completo**: Exportación detallada de todos los horarios
- **Por curso**: Vista organizada por curso
- **Por profesor**: Vista organizada por profesor
- **Resumen estadístico**: Métricas de cobertura

## Instalación y Configuración

### 1. Instalar Dependencias
```bash
pip install -r requirements.txt
```

### 2. Configurar Base de Datos
```bash
python manage.py makemigrations
python manage.py migrate
```

### 3. Cargar Dataset de Prueba
```bash
# Dataset pequeño para desarrollo
python manage.py cargar_dataset --size S --seed 42

# Dataset mediano para pruebas
python manage.py cargar_dataset --size M --seed 42

# Dataset grande para rendimiento
python manage.py cargar_dataset --size L --seed 42

# Dataset extra grande para stress testing
python manage.py cargar_dataset --size XL --seed 42 --force
```

## Uso del Sistema

### 1. Generar Horarios via API
```bash
# Generación básica con parámetros por defecto
curl -X POST http://localhost:8000/api/generar-horarios/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>"

# Generación con parámetros personalizados
curl -X POST http://localhost:8000/api/generar-horarios/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "generaciones": 250,
    "tam_poblacion": 120,
    "prob_cruce": 0.85,
    "prob_mutacion": 0.25,
    "elite": 4,
    "paciencia": 25,
    "timeout_seg": 180,
    "semilla": 42,
    "workers": 4
  }'
```

### 2. Respuesta de la API
```json
{
  "message": "Horario generado exitosamente",
  "metricas": {
    "total_time_s": 45.23,
    "n_generations": 156,
    "early_stopped": true,
    "seed": 42,
    "pool_size": 4,
    "time_load_s": 2.15,
    "time_eval_s": 43.08,
    "best_fitness": 1250.5,
    "conflicts_hard": 0,
    "conflicts_soft": 0
  }
}
```

### 3. Exportar Horarios
```python
from horarios.exportador import exportar_horario_csv, generar_resumen_horario

# Exportar horario completo
response = exportar_horario_csv()

# Obtener resumen estadístico
resumen = generar_resumen_horario()
print(f"Total horarios: {resumen['total_horarios']}")
print(f"Cobertura cursos: {resumen['cursos']['porcentaje']}%")
```

## Ejecutar Tests

### 1. Tests de Correctitud
```bash
pytest horarios/tests/test_genetico.py::TestAlgoritmoGenetico -v
```

### 2. Tests de Rendimiento
```bash
pytest horarios/tests/test_genetico.py::TestRendimiento -v
```

### 3. Tests de Validaciones
```bash
pytest horarios/tests/test_genetico.py::TestValidaciones -v
```

### 4. Todos los Tests
```bash
pytest -v
```

## Criterios de Aceptación Verificados

### ✅ Base de Datos
- [x] Constraints activos: Insertar duplicados falla por constraint
- [x] Restricciones de unicidad funcionando
- [x] Campo `aula_fija` en `Curso`

### ✅ Rendimiento
- [x] Dataset S: < 30s
- [x] Dataset M: < 90s  
- [x] Dataset L: < 180s
- [x] Dataset XL: < 300s (ajustable)

### ✅ Logs y Métricas
- [x] Logs JSON por generación
- [x] Resumen final con métricas completas
- [x] Tiempos de carga, evaluación y total

### ✅ API
- [x] 400/409 cuando faltan prerrequisitos
- [x] En éxito, persiste solo el mejor y retorna métricas
- [x] Parámetros configurables con defaults

### ✅ Tests
- [x] Tests de correctitud (sin solapes, bloques tipo "clase")
- [x] Tests de rendimiento con umbrales de tiempo
- [x] Tests de validaciones de prerrequisitos

### ✅ Exportación
- [x] CSV sin solapes
- [x] Múltiples formatos (completo, por curso, por profesor)
- [x] Resumen estadístico

## Optimizaciones Técnicas

### 1. Sin ORM en Loop Evolutivo
- ✅ Carga completa a memoria antes del GA
- ✅ Solo ORM al inicio (carga) y al final (persistir mejor individuo)
- ✅ Arrays NumPy para evaluación rápida

### 2. Paralelismo
- ✅ ProcessPoolExecutor para evaluación de población
- ✅ Configuración automática de workers (CPU cores - 1)
- ✅ Fallback a evaluación secuencial si falla paralelismo

### 3. JIT Compilation
- ✅ Numba para funciones críticas de fitness
- ✅ Compilación nopython con fastmath
- ✅ Fallback a Python puro si Numba no está disponible

### 4. Memoria Optimizada
- ✅ Mapeos id → índice para acceso O(1)
- ✅ Arrays NumPy compactos (int32, int8)
- ✅ Caché de datos preprocesados

## Monitoreo y Debugging

### 1. Logs por Generación
```json
{
  "gen": 45,
  "best_fitness": 1250.5,
  "mean_fitness": 1180.2,
  "conflicts_hard": 0,
  "conflicts_soft": 0,
  "time_gen_s": 1.23,
  "diversidad": 0.75,
  "generaciones_sin_mejora": 3
}
```

### 2. Métricas Finales
```json
{
  "total_time_s": 45.23,
  "n_generations": 156,
  "early_stopped": true,
  "seed": 42,
  "pool_size": 4,
  "time_load_s": 2.15,
  "time_eval_s": 43.08,
  "best_fitness": 1250.5,
  "conflicts_hard": 0,
  "conflicts_soft": 0
}
```

### 3. Perfilado Sugerido
```bash
# Perfilado con cProfile
python -m cProfile -o run.prof manage.py runserver

# Análisis del perfil
python -c "import pstats; p = pstats.Stats('run.prof'); p.sort_stats('cumulative').print_stats(20)"
```

## Comandos de Desarrollo

### 1. Crear Migraciones
```bash
python manage.py makemigrations horarios
python manage.py migrate
```

### 2. Cargar Datos de Prueba
```bash
python manage.py cargar_dataset --size M --seed 42
```

### 3. Ejecutar Tests
```bash
pytest -v --tb=short
```

### 4. Generar Horarios
```bash
curl -X POST http://localhost:8000/api/generar-horarios/ \
  -H "Content-Type: application/json" \
  -d '{"generaciones":100,"tam_poblacion":50}'
```

### 5. Verificar Constraints
```bash
# Intentar insertar duplicado (debe fallar)
python manage.py shell
>>> from horarios.models import Horario
>>> h = Horario.objects.first()
>>> Horario.objects.create(curso=h.curso, dia=h.dia, bloque=h.bloque, materia=h.materia, profesor=h.profesor)
# Debe lanzar IntegrityError
```

## Notas de Implementación

1. **Compatibilidad**: Mantiene compatibilidad con código existente
2. **Fallbacks**: Funciona sin librerías opcionales (Numba, Redis)
3. **Configuración**: Parámetros sensatos por defecto
4. **Escalabilidad**: Diseñado para datasets XL (100+ cursos)
5. **Monitoreo**: Logs detallados para debugging y optimización

El sistema está listo para producción con datasets de cualquier tamaño, manteniendo la calidad de los horarios generados y el rendimiento optimizado. 