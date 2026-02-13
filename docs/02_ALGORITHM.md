# 🧬 Algoritmo de Generación de Horarios

Aunque el proyecto lleva el nombre "Genetic", la implementación actual (v2) utiliza una estrategia híbrida más eficiente para este tipo de restricciones fuertes: **Demand-First Construction + Stochastic Hill Climbing**.

## Fases del Algoritmo

### Fase 1: Construcción (Demand-First)
El objetivo es crear una solución válida (sin choques) lo más rápido posible, aunque no sea óptima.
- **Estrategia**: Llena los horarios curso por curso.
- **Prioridad**:
    1. Materias obligatorias (Hard constraints).
    2. Materias de relleno (para completar la jornada).
- **Aleatoriedad**: Baraja los slots disponibles para evitar patrones repetitivos.

### Fase 2: Mejora Iterativa (Hill Climbing)
Una vez se tiene una solución válida, se intenta mejorar su "Calidad".
- **Operador**: `Swap Intra-Curso`. Selecciona dos bloques de un mismo curso e intenta intercambiarlos.
- **Evaluación**: Si el intercambio mejora la puntuación global y no viola restricciones, se mantiene. Si no, se descarta.
- **Terminación**: Se detiene tras `N` iteraciones sin mejora (paciencia).

## Función de Fitness (Calidad)
La calidad de un horario se mide de 0.0 a 100.0 basada en:
1. **Huecos (40%)**: Minimizar ventanas libres entre clases.
2. **Distribución Semanal (30%)**: Evitar días muy cargados vs días vacíos.
3. **Consecutividad (20%)**: Agrupar bloques de la misma materia si es pedagógicamente preferible.
4. **Compactibilidad Docente (10%)**: Tratar de agrupar las horas de los profesores.

## Glosario
- **Slot**: Unidad mínima (Día + Bloque + Aula + Profesor).
- **Regla Dura**: Inviolable (ej. un profesor no puede estar en dos sitios a la vez).
- **Regla Blanda**: Deseable (ej. preferible no tener clases los viernes a última hora).
