# 🚀 Generador de Horarios - Sistema Robusto

## ✅ Estado del Proyecto

**¡El proyecto está completamente funcional y listo para usar!**

Todas las mejoras solicitadas han sido implementadas:
- ✅ Validadores robustos para evitar duplicados y choques
- ✅ Reparador automático de cromosomas inviables
- ✅ Algoritmo genético con validación previa al fitness
- ✅ Transacciones atómicas para persistencia segura
- ✅ API con manejo robusto de errores
- ✅ Frontend optimizado con solo horario semanal
- ✅ Tests completos que verifican todas las validaciones

## 🎯 Inicio Rápido

### Opción 1: Script Automático (Recomendado)
```bash
./iniciar_proyecto.sh
```

### Opción 2: Pasos Manuales

1. **Activar entorno virtual:**
   ```bash
   source venv/bin/activate
   ```

2. **Verificar dependencias:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Verificar configuración:**
   ```bash
   python manage.py check
   ```

4. **Aplicar migraciones:**
   ```bash
   python manage.py migrate
   ```

5. **Cargar datos de ejemplo (si es necesario):**
   ```bash
   python cargar_datos_ejemplo.py
   ```

6. **Iniciar servidor:**
   ```bash
   python manage.py runserver 0.0.0.0:8000
   ```

## 🌐 Acceso al Sistema

- **Dashboard principal:** http://localhost:8000/horarios/
- **Panel de administración:** http://localhost:8000/admin/
  - Usuario: `admin`
  - Contraseña: `admin`

## 🎯 Funcionalidades Implementadas

### 🔧 Algoritmo Genético Robusto
- **Validación previa al fitness** con reparación automática
- **Operadores de cruce y mutación seguros**
- **Evaluación paralela** con joblib
- **Early stopping** inteligente
- **Logging detallado** de estadísticas

### 🛡️ Validadores Exhaustivos
- **Unicidad** `(curso, día, bloque)` y `(profesor, día, bloque)`
- **Disponibilidad de profesores** respetada al 100%
- **bloques_por_semana** exactos por materia
- **Solo bloques tipo 'clase'** utilizados
- **Aulas fijas** por curso respetadas

### 🔄 Reparador Automático
- **Detección de conflictos** en tiempo real
- **Reparación automática** de individuos inviables
- **Múltiples estrategias** de reparación
- **Mantenimiento de factibilidad** durante reparaciones

### 🎨 Frontend Optimizado
- **Dashboard moderno** con Tailwind CSS
- **Solo horario semanal** (sin tabla redundante)
- **Formulario de parámetros** para control fino
- **Alertas informativas** con métricas
- **Bloques dinámicos** según configuración del colegio

### 🔌 API Robusto
- **Respuestas estructuradas** con status y métricas
- **Manejo de errores** sin crashes del servidor
- **Transacciones atómicas** para persistencia segura
- **Logging detallado** para trazabilidad

## 📊 Datos de Ejemplo Cargados

El sistema incluye datos de ejemplo completos:
- **8 grados** (Primero, Segundo, etc.)
- **22 cursos** (1A, 1B, 1C, 2A, 2B, 2C, etc.)
- **19 materias** (Matemáticas, Lenguaje, Ciencias, etc.)
- **23 profesores** con disponibilidad completa
- **25 aulas** de diferentes tipos
- **7 bloques horarios** tipo 'clase'
- **Relaciones completas** materia-grado y materia-profesor

## 🧪 Tests Verificados

Todos los tests pasan exitosamente:
```bash
python manage.py test horarios.tests.test_validaciones -v 2
```

## 🎯 Cómo Usar

1. **Accede al dashboard:** http://localhost:8000/horarios/
2. **Configura parámetros** del algoritmo genético:
   - Población: 80 (recomendado)
   - Generaciones: 500 (recomendado)
   - Probabilidad de cruce: 0.85
   - Probabilidad de mutación: 0.25
   - Elite: 4
   - Timeout: 180 segundos
3. **Haz clic en "Generar Horarios"**
4. **Espera** a que el algoritmo termine (1-3 minutos)
5. **Visualiza** el horario semanal generado

## 🔍 Características de Robustez

### ✅ Garantías de Calidad
- **0 individuos inviables** en la élite final
- **Sin IntegrityError** en la base de datos
- **Validación exhaustiva** antes de persistir
- **Reparación automática** de conflictos
- **Logs detallados** para trazabilidad

### ✅ Restricciones Duras Cumplidas
- **Unicidad** en todas las combinaciones críticas
- **Disponibilidad** de profesores respetada
- **bloques_por_semana** exactos
- **Solo bloques válidos** utilizados
- **Aulas fijas** asignadas correctamente

## 🚨 Solución de Problemas

### Si el servidor no inicia:
1. Verifica que MySQL esté ejecutándose: `sudo systemctl status mysql`
2. Verifica la conexión a la BD: `python manage.py dbshell`
3. Revisa los logs de Django

### Si hay errores de dependencias:
1. Reinstala: `pip install -r requirements.txt`
2. Verifica Python 3.13+: `python --version`

### Si no hay datos:
1. Ejecuta: `python cargar_datos_ejemplo.py`
2. Verifica: `python manage.py shell -c "from horarios.models import Curso; print(Curso.objects.count())"`

## 📝 Logs y Monitoreo

El sistema genera logs detallados:
- **INFO:** Progreso del algoritmo genético
- **WARN:** Conflictos detectados y reparados
- **ERROR:** Errores críticos (si los hay)

## 🎉 ¡Listo para Demo!

El sistema está completamente funcional y listo para demostración. Todas las mejoras solicitadas han sido implementadas y verificadas.

**¡Disfruta generando horarios robustos! 🎯** 