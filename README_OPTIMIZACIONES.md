# Optimizaciones del Algoritmo Genético para Horarios Escolares

Este documento describe las optimizaciones implementadas en el algoritmo genético para la generación de horarios escolares, así como las librerías integradas y las herramientas de diagnóstico disponibles.

## Librerías Integradas

Se han integrado las siguientes librerías para mejorar el rendimiento y la escalabilidad del algoritmo:

### Librerías Obligatorias

- **NumPy**: Procesamiento vectorizado para operaciones masivas y manipulación eficiente de cromosomas.

### Librerías Opcionales (con fallback automático)

- **Numba**: Compilación JIT de funciones críticas para acelerar la evaluación de fitness y verificación de restricciones.
- **Pandas/Polars**: Procesamiento eficiente de grandes volúmenes de datos de disponibilidad y asignaciones.
- **Joblib**: Paralelización mejorada para evaluación de poblaciones.
- **Matplotlib/Seaborn**: Visualización de la evolución del algoritmo y diagnósticos.

## Optimizaciones Implementadas

### 1. Evaluación de Fitness Optimizada

- Implementación vectorizada con NumPy para verificación rápida de conflictos.
- Compilación JIT con Numba para funciones críticas de evaluación.
- Caché de datos preprocesados para evitar conversiones repetitivas.

### 2. Paralelización Mejorada

- Uso de Joblib para evaluación paralela de poblaciones con mejor rendimiento.
- Fallback automático a multiprocessing si Joblib no está disponible.
- Detección automática del número óptimo de workers.

### 3. Operadores Genéticos Optimizados

- Cruce por bloques optimizado con NumPy para mayor eficiencia.
- Mutación adaptativa con enfoque en genes conflictivos.
- Selección de torneo eficiente.

### 4. Monitoreo y Diagnóstico

- Seguimiento de diversidad genética para evitar convergencia prematura.
- Visualización de la evolución del fitness, conflictos y diversidad.
- Herramientas de benchmark para comparar diferentes configuraciones.

## Herramientas de Diagnóstico

Se han implementado dos herramientas principales para diagnóstico y optimización:

### 1. Módulo de Diagnóstico (`horarios/diagnostico.py`)

Permite analizar el rendimiento del algoritmo genético con diferentes configuraciones:

```bash
python -m horarios.diagnostico --modo benchmark --repeticiones 3 --poblacion 100 --generaciones 100 --colegio 1
```

Opciones disponibles:
- `--modo`: `benchmark` o `analisis`
- `--repeticiones`: Número de repeticiones para cada configuración
- `--poblacion`: Tamaño de población base para pruebas
- `--generaciones`: Número máximo de generaciones
- `--colegio`: ID del colegio para pruebas

### 2. Script de Benchmark (`benchmark.py`)

Permite comparar el rendimiento del algoritmo con diferentes configuraciones:

```bash
python benchmark.py --repeticiones 3 --colegio 1 --modo completo
```

Opciones disponibles:
- `--repeticiones`: Número de repeticiones para cada configuración
- `--colegio`: ID del colegio para pruebas
- `--modo`: `rapido` o `completo`

## Visualizaciones

Si Matplotlib y Seaborn están disponibles, se generarán automáticamente visualizaciones en el directorio `diagnosticos/` con:

1. Evolución del fitness a lo largo de las generaciones
2. Evolución del número de conflictos
3. Evolución de la diversidad genética

Adicionalmente, los benchmarks generarán gráficos comparativos en el directorio `benchmarks/`.

## Uso de Librerías Opcionales

Las librerías opcionales se detectan automáticamente y se utilizan si están disponibles. Si no están instaladas, el algoritmo funcionará con implementaciones alternativas en Python puro o NumPy.

Para instalar todas las librerías opcionales:

```bash
pip install joblib numba pandas polars matplotlib seaborn
```

O selectivamente según necesidades:

```bash
# Para aceleración de cálculos
pip install numba

# Para paralelización mejorada
pip install joblib

# Para procesamiento de datos eficiente
pip install pandas
# o
pip install polars

# Para visualizaciones
pip install matplotlib seaborn
```

## Recomendaciones de Configuración

Para obtener el mejor rendimiento, se recomiendan las siguientes configuraciones según el tamaño del problema:

### Problemas Pequeños (< 10 cursos)
- Tamaño de población: 50-100
- Tasa de mutación: 0.1
- Elitismo: 0.1

### Problemas Medianos (10-30 cursos)
- Tamaño de población: 100-200
- Tasa de mutación: 0.1-0.15
- Elitismo: 0.1

### Problemas Grandes (> 30 cursos)
- Tamaño de población: 200-500
- Tasa de mutación: 0.15-0.2
- Elitismo: 0.05-0.1

Utilice las herramientas de benchmark para encontrar la configuración óptima para su caso específico.

## Extensiones Futuras

El código está preparado para futuras extensiones con:

- **Dask/Ray**: Puntos de extensión para distribución en clústeres.
- **Celery+Redis**: Preparado para integración con tareas asíncronas.
- **PostgreSQL optimizado**: Consultas preparadas para índices eficientes.

## Notas de Implementación

- Se mantiene compatibilidad con la API original.
- Se incluyen fallbacks para todas las optimizaciones.
- El código está documentado con comentarios explicativos.
- Se registran métricas detalladas en los logs para análisis posterior.