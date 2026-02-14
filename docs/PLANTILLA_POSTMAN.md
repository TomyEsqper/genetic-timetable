# Guía Completa de Pruebas con Postman (AWS) – Genetic Timetable

## 1. Objetivo
- Probar la API desplegada en AWS con Postman, sin experiencia previa.
- Cubrir autenticación (guest/JWT), variables de entorno, headers, cuerpos de petición, respuestas esperadas y manejo de errores.

## 2. Requisitos Previos
- Postman instalado.
- URL de producción (IP pública con HTTPS): `https://18.188.89.221`
- Certificado autofirmado activo en Nginx (redirige HTTP→HTTPS).

## 3. Configuración Inicial en Postman
- Desactivar verificación SSL (certificado autofirmado):
  - Postman → Settings → General → desactiva “SSL certificate verification”.
- Crear un Environment llamado “Genetic Timetable (AWS)” con estas variables:
  - `base_url` = `https://18.188.89.221`
  - `access_token` = (vacío, se llenará tras autenticarse)
  - `username` y `password` (solo si usarás login real: Opción B)

## 4. Autenticación
### Opción A: Modo Invitado (recomendado para empezar)
- Método: POST
- URL: `{{base_url}}/api/auth/guest/`
- Headers:
  - `Content-Type: application/json`
- Body: Raw → JSON → `{}` (o vacío)
- Respuesta 200 (ejemplo):
```json
{
  "access": "eyJhbGciOi...",
  "refresh": "eyJhbGciOi...",
  "user": "invitado_demo",
  "message": "¡Bienvenido al modo Demo! Este token expira en 30 minutos.",
  "expires_in_minutes": 30
}
```
- Guarda el campo `access` en la variable `access_token` del Environment.
  - En la pestaña “Tests” de tu request, pega:
```javascript
const jsonData = pm.response.json();
if (jsonData.access) {
  pm.environment.set("access_token", jsonData.access);
}
```

### Opción B: Usuario Real (JWT con SimpleJWT)
- Método: POST
- URL: `{{base_url}}/api/token/`
- Headers: `Content-Type: application/json`
- Body:
```json
{ "username": "{{username}}", "password": "{{password}}" }
```
- Respuesta 200:
```json
{ "refresh": "xxxx", "access": "xxxx" }
```
- Guarda `access` en `access_token` (mismo script de “Tests”). Para refrescar:
  - POST `{{base_url}}/api/token/refresh/` con `{ "refresh": "xxxx" }`

### Usar el token en las siguientes peticiones
- En cada request protegido, pestaña Authorization → Type = Bearer Token → Token = `{{access_token}}`.

## 5. Endpoints Principales (Lectura)
> Headers comunes: `Authorization: Bearer {{access_token}}`

- Listar Profesores
  - GET `{{base_url}}/api/profesores/`
- Listar Materias
  - GET `{{base_url}}/api/materias/`
- Listar Cursos
  - GET `{{base_url}}/api/cursos/`
- Listar Aulas
  - GET `{{base_url}}/api/aulas/`
- Listar Horarios
  - GET `{{base_url}}/api/horarios/`

Respuestas 200: listas JSON con los objetos del sistema (id, nombre, etc.).

## 6. Validaciones Previas y Estado
- Estado del Sistema
  - GET `{{base_url}}/api/estado-sistema/`
  - Esperado: JSON con conteos de cursos, profesores, materias, etc.
- Validar Prerrequisitos
  - GET `{{base_url}}/api/validar-prerrequisitos/`
  - Esperado: reporte de “listo/no listo” y detalles (ej. materias sin profesor).

## 7. Generación de Horarios (Sincrónica)
- Método: POST
- URL: `{{base_url}}/api/generar-horario/`
- Headers:
  - `Content-Type: application/json`
  - `Authorization: Bearer {{access_token}}`
- Body (ejemplo recomendado):
```json
{
  "semilla": 94601,
  "generaciones": 1000,
  "paciencia": 50,
  "preview": false
}
```
- Respuesta 200 (éxito, ejemplo abreviado):
```json
{
  "status": "success",
  "timeout": false,
  "objetivo": { "fitness_final": 0.87, "generaciones_completadas": 120, "convergencia": true },
  "solapes": 0,
  "huecos": 0,
  "tiempos_fases": { },
  "tiempo_total_s": 12.34,
  "semilla": 94601,
  "asignaciones": [
    { "curso_id": 1, "materia_id": 5, "profesor_id": 7, "dia": "lunes", "bloque": 1, "aula_id": 2 }
  ],
  "dimensiones": { "cursos": 10, "materias": 40, "profesores": 20, "slots": 150 },
  "oferta_vs_demanda": { },
  "log_path": "/ruta/logs/..."
}
```
- Errores esperables:
  - 409 (validación previa fallida):
```json
{ "status": "error", "mensaje": "Validación previa fallida", "errores_validacion": ["..."], "reporte": { } }
```
  - 400 (instancia inviable):
```json
{ "status": "error", "mensaje": "instancia_inviable", "oferta_vs_demanda": { }, "dimensiones": { } }
```

## 8. Jobs Asíncronos (si Celery/Redis disponibles)
- Encolar generación:
  - POST `{{base_url}}/api/jobs/generar-horario/`
  - Body:
```json
{
  "colegio_id": 1,
  "params": { "semilla": 94601, "generaciones": 500, "paciencia": 50 }
}
```
  - Respuesta 202:
```json
{ "status": "queued", "task_id": "a1b2c3..." }
```
- Consultar estado:
  - GET `{{base_url}}/api/jobs/estado/{{task_id}}/`

## 9. Exportes
- Curso a CSV/PDF:
  - GET `{{base_url}}/api/export/curso/1/csv`
  - GET `{{base_url}}/api/export/curso/1/pdf`
- Profesor a CSV/PDF:
  - GET `{{base_url}}/api/export/profesor/7/csv`

## 10. Flujo de Pruebas Sugerido
1) Autenticarse (guest o JWT) y guardar token.
2) GET `estado-sistema` para validar acceso.
3) GET `validar-prerrequisitos` para verificar datos maestros.
4) POST `generar-horario` (preview: true si no quieres persistir).
5) GET `horarios` para revisar lo generado.
6) (Opcional) Jobs asíncronos y exportes.

## 11. Ejemplos de la Colección oficial
Puedes importar la colección incluida en el repo:
- Archivo: `docs/Genetic_Timetable.postman_collection.json`
- Variables:
  - `base_url` → `https://18.188.89.221`
  - `token` (si no usas el script de guardado automático)
Incluye requests preconfigurados: Login, Estado del Sistema y Solver.

## 12. Manejo de Errores y Troubleshooting
- 401 Unauthorized: token ausente/expirado → reautenticar o refrescar.
- 403 Forbidden: permisos insuficientes → usar un usuario con permisos.
- 405 Method Not Allowed: método incorrecto (ej. GET en endpoint que espera POST).
- 502 Bad Gateway: problema de despliegue (Nginx ↔ web). Verificar contenedores.
- SSL: si falla, desactiva “SSL certificate verification” en Postman.

## 13. Referencias Útiles
- Swagger UI: `{{base_url}}/swagger/`
- Endpoints definidos en: [api/urls.py](../api/urls.py) y lógica en [api/views.py](../api/views.py)

---

> Nota: Esta plantilla consolida y amplía la guía `docs/POSTMAN_GUIDE.md` e integra los ejemplos de `docs/Genetic_Timetable.postman_collection.json` para un onboarding más claro en Postman.

