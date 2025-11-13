# Guía de Recuperación de Contraseña

Este documento explica cómo funciona la recuperación de contraseña en el backend.

## Cambios Implementados

### 1. Campo Email Requerido

El campo `email` ahora es **requerido** en el registro de usuarios:

- **Serializer**: `UserSerializer` ahora incluye el campo `email` como requerido
- **Validaciones**:
  - El email no puede estar vacío
  - El formato del email debe ser válido
  - El email debe ser único (no puede estar ya registrado)
  - El email se normaliza a minúsculas automáticamente

### 2. Configuración de Email

Se ha configurado el envío de emails en `settings.py`:

**Para Desarrollo** (actual):
- Los emails se imprimen en la consola del servidor
- No se requiere configuración adicional

**Para Producción**:
- Descomentar y configurar las variables en `settings.py`:
  ```python
  EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
  EMAIL_HOST = os.getenv('EMAIL_HOST', 'smtp.gmail.com')
  EMAIL_PORT = int(os.getenv('EMAIL_PORT', 587))
  EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'True').lower() == 'true'
  EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', '')
  EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')
  DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', 'noreply@example.com')
  ```

- Agregar las variables al archivo `.env`:
  ```
  EMAIL_HOST=smtp.gmail.com
  EMAIL_PORT=587
  EMAIL_USE_TLS=True
  EMAIL_HOST_USER=tu-email@gmail.com
  EMAIL_HOST_PASSWORD=tu-contraseña-de-aplicación
  DEFAULT_FROM_EMAIL=noreply@tudominio.com
  FRONTEND_URL=http://localhost:5173
  ```

## Endpoints de Recuperación de Contraseña

### 1. Solicitar Recuperación de Contraseña

**Endpoint**: `POST /api/password/reset/request/`

**Descripción**: Envía un email con un enlace para recuperar la contraseña.

**Request Body**:
```json
{
  "email": "usuario@example.com"
}
```

**Response (200 OK)**:
```json
{
  "success": true,
  "message": "Si el email existe en nuestro sistema, recibirás un enlace para recuperar tu contraseña."
}
```

**Response (400 Bad Request)**:
```json
{
  "success": false,
  "message": "Error en los datos proporcionados",
  "errors": {
    "email": ["Este campo es requerido."]
  }
}
```

**Nota de Seguridad**: Por seguridad, siempre se devuelve el mismo mensaje, independientemente de si el email existe o no en la base de datos. Esto previene que atacantes descubran qué emails están registrados.

### 2. Confirmar Recuperación de Contraseña

**Endpoint**: `POST /api/password/reset/confirm/`

**Descripción**: Restablece la contraseña usando el token recibido por email.

**Request Body**:
```json
{
  "uid": "base64_encoded_user_id",
  "token": "password_reset_token",
  "new_password": "NuevaContraseña123",
  "confirm_password": "NuevaContraseña123"
}
```

**Response (200 OK)**:
```json
{
  "success": true,
  "message": "Contraseña restablecida exitosamente. Ahora puedes iniciar sesión con tu nueva contraseña."
}
```

**Response (400 Bad Request)**:
```json
{
  "success": false,
  "message": "El token de recuperación no es válido o ha expirado."
}
```

## Flujo de Recuperación de Contraseña

1. **Usuario solicita recuperación**:
   - El usuario ingresa su email en el frontend
   - El frontend envía una petición POST a `/api/password/reset/request/`
   - El backend genera un token de recuperación y envía un email

2. **Usuario recibe el email**:
   - El email contiene un enlace con `uid` y `token`
   - El enlace apunta al frontend: `{FRONTEND_URL}/reset-password?uid={uid}&token={token}`

3. **Usuario restablece la contraseña**:
   - El frontend muestra un formulario para ingresar la nueva contraseña
   - El frontend envía una petición POST a `/api/password/reset/confirm/` con:
     - `uid`: El ID del usuario codificado en base64
     - `token`: El token de recuperación
     - `new_password`: La nueva contraseña
     - `confirm_password`: Confirmación de la nueva contraseña

4. **Backend valida y actualiza**:
   - El backend verifica que el token sea válido
   - El backend valida que las contraseñas coincidan
   - El backend actualiza la contraseña del usuario

## Validaciones

### Email
- ✅ Requerido
- ✅ Formato válido
- ✅ Único (no puede estar ya registrado)
- ✅ Se normaliza a minúsculas

### Nueva Contraseña
- ✅ Mínimo 8 caracteres
- ✅ Debe contener al menos una letra
- ✅ Debe contener al menos un número
- ✅ Debe coincidir con `confirm_password`

### Token
- ✅ Debe ser válido
- ✅ Debe estar asociado al usuario correcto
- ✅ Expira después de 24 horas (configuración de Django)

## Ejemplo de Uso

### Solicitar Recuperación

```bash
curl -X POST http://localhost:8000/api/password/reset/request/ \
  -H "Content-Type: application/json" \
  -d '{"email": "usuario@example.com"}'
```

### Confirmar Recuperación

```bash
curl -X POST http://localhost:8000/api/password/reset/confirm/ \
  -H "Content-Type: application/json" \
  -d '{
    "uid": "MTIz",
    "token": "abc123def456",
    "new_password": "NuevaContraseña123",
    "confirm_password": "NuevaContraseña123"
  }'
```

## Notas Importantes

1. **Seguridad**: El mensaje de respuesta siempre es el mismo, independientemente de si el email existe o no.

2. **Token de Recuperación**: Los tokens expiran después de 24 horas por defecto (configuración de Django).

3. **Email en Desarrollo**: En desarrollo, los emails se imprimen en la consola del servidor. Revisa la consola donde ejecutas `python manage.py runserver`.

4. **Email en Producción**: Para producción, configura un servidor SMTP real (Gmail, SendGrid, etc.).

5. **Frontend URL**: Asegúrate de configurar `FRONTEND_URL` en tu archivo `.env` para que los enlaces de recuperación apunten al frontend correcto.

## Próximos Pasos

1. **Frontend**: Crear la interfaz de usuario para:
   - Formulario de solicitud de recuperación (solo email)
   - Página de restablecimiento de contraseña (con uid y token en la URL)

2. **Email HTML**: Mejorar el formato del email usando templates HTML en lugar de texto plano.

3. **Rate Limiting**: Considerar agregar límites de tasa para prevenir abuso del endpoint de recuperación.

