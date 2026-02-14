# 🚀 Guía de Pruebas con Postman (Servidor AWS)

Esta guía te enseña a configurar Postman para conectarte a **tu servidor AWS**. Sigue esta tabla para configurar el **Environment** correctamente.

---

## 1. Configuración del Entorno (Environment)

Crea un nuevo **Environment** en Postman y agrega estas variables exactas:

| Variable | Valor Sugerido / Acción | ¿Qué hacer? |
| :--- | :--- | :--- |
| `base_url` | `http://18.188.89.221` | **Déjalo así** (Es tu IP de AWS). |
| `username` | `admin` | **Llena esto** si usas la Opción B (Producción). |
| `password` | `tu_password_aqui` | **Llena esto** si usas la Opción B (Producción). |
| `access_token` | *(Vacío)* | **NO TOCAR**. Se llena solo con la Opción A o B. |

---

## 2. Autenticación (Paso a Paso)

### Opción A: Modo Demo (Recomendado para pruebas rápidas)
Si no tienes un usuario o solo quieres ver cómo funciona el motor:
1.  Crea una petición `POST` a: `{{base_url}}/api/auth/guest/`
2.  No necesitas enviar nada en el Body.
3.  **Resultado**: Recibirás un token de acceso válido por 30 minutos. El script lo guardará automáticamente si pegas el código del Paso 2.2.

### Opción B: Usuario Administrador (Producción)
Si ya tienes tus credenciales reales:
1.  **Metodo:** `POST`
2.  **URL:** `{{base_url}}/api/token/`
3.  **Body (JSON):**
    ```json
    {
        "username": "{{username}}",
        "password": "{{password}}"
    }
    ```

### 2.2 Script de Guardado Automático
Para cualquiera de las dos opciones, ve a la pestaña **Scripts -> Post-response** y pega esto:
    ```javascript
    // Este código guarda el token automáticamente en la variable 'access_token'
    const jsonData = pm.response.json();
    if (jsonData.access) {
        pm.environment.set("access_token", jsonData.access);
        console.log("¡Token guardado! Ya puedes usar los demás endpoints.");
    }
    ```

---

## 3. Cómo usar los demás Endpoints

Una vez hecho el Login, para cualquier otra petición (como ver el estado o generar horarios):

1.  Ve a la pestaña **Authorization**.
2.  En **Type**, selecciona **Bearer Token**.
3.  En **Token**, escribe exactamente: `{{access_token}}`
4.  ¡Listo! Postman usará el token que se guardó solo.

---

## 4. Flujo de Pruebas Recomendado

Sigue estos pasos en orden para asegurar que todo funciona en tu servidor:

### Paso A: Verificar Conexión
*   **Método:** `GET`
*   **URL:** `{{base_url}}/api/estado-sistema/`
*   **Qué esperar:** Un JSON con el conteo de tus cursos, profesores y materias. Si esto falla, revisa la IP.

### Paso B: Validar Prerrequisitos
*   **Método:** `GET`
*   **URL:** `{{base_url}}/api/validar-prerrequisitos/`
*   **Qué esperar:** Una lista que te dice si el colegio está listo para generar horarios o si faltan datos (ej. "Materia X no tiene profesor").

### Paso C: Generar Horario (Modo Prueba)
*   **Método:** `POST`
*   **URL:** `{{base_url}}/api/generar-horario/`
*   **Body (JSON):**
    ```json
    {
        "generaciones": 100,
        "preview": true
    }
    ```
*   **Qué esperar:** El algoritmo correrá y te devolverá el resultado, pero **NO guardará nada** en la base de datos (por el `preview: true`). Ideal para probar sin romper nada.

---

## 🛠️ Solución de Problemas (Troubleshooting)

*   **¿Error de SSL?**: Si usas HTTPS y Postman da error, ve a `Settings` -> `General` y apaga **"SSL certificate verification"**.
*   **¿Error 401 Unauthorized?**: Tu token expiró o no hiciste el Paso 2 correctamente. Repite el Login.
*   **¿Error 502 / Timeout?**: El servidor AWS está caído o procesando algo muy pesado. Revisa los logs con `docker compose logs`.
