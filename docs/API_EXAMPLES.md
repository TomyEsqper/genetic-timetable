# 🧪 Ejemplos de Uso de la API (Postman / cURL)

Este documento contiene ejemplos JSON listos para usar en tus pruebas con Postman, Insomnia o cURL.

---

## 🔐 1. Autenticación (Obtener Token)

Antes de usar cualquier endpoint protegido, necesitas un token JWT.

**Endpoint:** `POST /api/token/`  
**Content-Type:** `application/json`

**Body:**
```json
{
  "username": "admin",
  "password": "admin_password"
}
```

**Respuesta Exitosa (200 OK):**
```json
{
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "access": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
}
```

⚠️ **Nota:** Usa el valor de `access` en el header `Authorization` de tus siguientes peticiones:
`Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...`

---

## 🧬 2. Motor de Cálculo (Solver Puro)

Este endpoint recibe un escenario completo (configuración + materias + profesores + cursos) y devuelve el horario resuelto sin persistirlo obligatoriamente en la BD principal (dependiendo de la implementación, este endpoint suele ser "stateless" o reinicia la BD).

**Endpoint:** `POST /api/engine/solve/`  
**Auth:** No requerida (o configurable en `views.py` como `AllowAny` para pruebas).

**Body (Ejemplo Mini - Copiar y Pegar):**

```json
{
  "configuracion": {
    "dias_clase": "lunes,martes,miércoles,jueves,viernes",
    "bloques_por_dia": 6,
    "duracion_bloque": 55,
    "jornada": "mañana"
  },
  "materias": [
    { "nombre": "Matemáticas" },
    { "nombre": "Español" },
    { "nombre": "Inglés" }
  ],
  "profesores": [
    {
      "nombre": "Prof. Matemáticas",
      "materias_capaces": ["Matemáticas"],
      "disponibilidad": [] 
    },
    {
      "nombre": "Prof. Humanidades",
      "materias_capaces": ["Español", "Inglés"],
      "disponibilidad": [
         { "dia": "lunes", "bloque_inicio": 1, "bloque_fin": 3 }
      ]
    }
  ],
  "cursos": [
    {
      "nombre": "SEXTO A",
      "grado": "6",
      "plan_estudios": {
        "Matemáticas": 5,
        "Español": 4,
        "Inglés": 4
      }
    }
  ]
}
```

---

## 🏫 3. Generar Horario (Sistema Interno)

Este endpoint dispara el algoritmo usando los datos YA cargados en la base de datos (Profesores, Cursos, etc. que hayas creado vía Admin o `seed_data`).

**Endpoint:** `POST /api/generar-horario/`  
**Auth:** Requerida (`Bearer <token>`)

**Body (Opciones de Configuración):**

```json
{
  "semilla": 42,
  "generaciones": 500,
  "paciencia": 50,
  "preview": false,
  "async": false
}
```

| Parámetro | Tipo | Descripción |
|---|---|---|
| `semilla` | int | Semilla aleatoria para reproducibilidad. |
| `generaciones` | int | Número máximo de iteraciones del algoritmo genético. |
| `paciencia` | int | Cuántas generaciones esperar sin mejora antes de detenerse. |
| `preview` | bool | Si `true`, no guarda cambios en BD, solo muestra diferencias. |
| `async` | bool | Si `true`, ejecuta en background (requiere Celery/Redis). |

---

## 📊 4. Consultar Estado del Sistema

Verifica cuántos recursos (cursos, profesores, etc.) tienes cargados.

**Endpoint:** `GET /api/estado-sistema/`  
**Auth:** Requerida

**Respuesta Ejemplo:**
```json
{
    "recursos": {
        "cursos": 12,
        "profesores": 25,
        "materias": 20,
        "aulas": 15,
        "horarios": 360,
        "bloques_horario": 6
    },
    "configuracion": { ... },
    "metricas": {
        "factor_ocupacion": 0.85
    }
}
```
