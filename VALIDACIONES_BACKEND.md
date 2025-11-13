# Validaciones del Backend - Registro de Usuarios

Este documento describe todas las validaciones que se aplican en el backend para el registro de usuarios.

## Endpoint de Registro
- **URL**: `/api/user/register/`
- **Método**: `POST`
- **Vista**: `UserCreateView` (Django REST Framework `CreateAPIView`)
- **Serializer**: `UserSerializer`

## Campos Requeridos

El serializer solo acepta los siguientes campos:
- `username` (requerido)
- `password` (requerido)

## Validaciones Aplicadas

### 1. Validaciones del Modelo User de Django

#### Username
- **Requerido**: Sí (campo obligatorio)
- **Longitud máxima**: 150 caracteres
- **Unicidad**: El username debe ser único en la base de datos
- **Caracteres permitidos**: Letras, números y los caracteres: `@`, `.`, `+`, `-`, `_`
- **No puede estar vacío**: No se permite un string vacío
- **No puede ser solo espacios**: Django trimea los espacios en blanco

**Errores esperados**:
- Si el username ya existe: `{"username": ["A user with that username already exists."]}`
- Si el username está vacío: `{"username": ["This field is required."]}`
- Si el username excede 150 caracteres: `{"username": ["Ensure this field has no more than 150 characters."]}`

#### Password
- **Requerido**: Sí (campo obligatorio)
- **No puede estar vacío**: No se permite un string vacío

**Errores esperados**:
- Si el password está vacío: `{"password": ["This field is required."]}`

### 2. Validadores de Contraseña (AUTH_PASSWORD_VALIDATORS)

El backend tiene configurados 4 validadores de contraseña en `settings.py`:

#### a) UserAttributeSimilarityValidator
- **Propósito**: Verifica que la contraseña no sea similar a los atributos del usuario
- **Validación**: La contraseña no debe ser similar al username u otros atributos del usuario
- **Error esperado**: `{"password": ["The password is too similar to the username."]}`

#### b) MinimumLengthValidator
- **Propósito**: Verifica la longitud mínima de la contraseña
- **Longitud mínima por defecto**: 8 caracteres
- **Error esperado**: `{"password": ["This password is too short. It must contain at least 8 characters."]}`

#### c) CommonPasswordValidator
- **Propósito**: Verifica que la contraseña no sea una contraseña común
- **Lista de contraseñas comunes**: Django tiene una lista de 20,000 contraseñas comunes
- **Error esperado**: `{"password": ["This password is too common."]}`

#### d) NumericPasswordValidator
- **Propósito**: Verifica que la contraseña no sea completamente numérica
- **Error esperado**: `{"password": ["This password is entirely numeric."]}`

### 3. Validaciones del Serializer

El `UserSerializer` no tiene validaciones personalizadas adicionales, solo utiliza las validaciones del modelo y los validadores de contraseña.

## Casos de Prueba Recomendados

### Casos de Éxito

1. **Registro exitoso con datos válidos**
   - **Request**: `{"username": "usuario123", "password": "Password123!"}`
   - **Response esperado**: `201 Created` con `{"id": X, "username": "usuario123"}`

### Casos de Error - Username

2. **Username vacío**
   - **Request**: `{"username": "", "password": "Password123!"}`
   - **Response esperado**: `400 Bad Request` con `{"username": ["This field may not be blank."]}`

3. **Username faltante**
   - **Request**: `{"password": "Password123!"}`
   - **Response esperado**: `400 Bad Request` con `{"username": ["This field is required."]}`

4. **Username duplicado**
   - **Request**: `{"username": "usuario_existente", "password": "Password123!"}`
   - **Response esperado**: `400 Bad Request` con `{"username": ["A user with that username already exists."]}`

5. **Username muy largo (>150 caracteres)**
   - **Request**: `{"username": "a" * 151, "password": "Password123!"}`
   - **Response esperado**: `400 Bad Request` con `{"username": ["Ensure this field has no more than 150 characters."]}`

6. **Username con caracteres inválidos**
   - **Request**: `{"username": "user@name!", "password": "Password123!"}`
   - **Nota**: Django permite `@` pero puede haber restricciones según la configuración

### Casos de Error - Password

7. **Password vacío**
   - **Request**: `{"username": "usuario123", "password": ""}`
   - **Response esperado**: `400 Bad Request` con `{"password": ["This field may not be blank."]}`

8. **Password faltante**
   - **Request**: `{"username": "usuario123"}`
   - **Response esperado**: `400 Bad Request` con `{"password": ["This field is required."]}`

9. **Password muy corto (<8 caracteres)**
   - **Request**: `{"username": "usuario123", "password": "Pass1!"}`
   - **Response esperado**: `400 Bad Request` con `{"password": ["This password is too short. It must contain at least 8 characters."]}`

10. **Password completamente numérico**
    - **Request**: `{"username": "usuario123", "password": "12345678"}`
    - **Response esperado**: `400 Bad Request` con `{"password": ["This password is entirely numeric."]}`

11. **Password muy común**
    - **Request**: `{"username": "usuario123", "password": "password"}`
    - **Response esperado**: `400 Bad Request` con `{"password": ["This password is too common."]}`

12. **Password similar al username**
    - **Request**: `{"username": "usuario123", "password": "usuario123"}`
    - **Response esperado**: `400 Bad Request` con `{"password": ["The password is too similar to the username."]}`

### Casos de Error - Múltiples Campos

13. **Múltiples errores**
    - **Request**: `{"username": "", "password": "123"}`
    - **Response esperado**: `400 Bad Request` con errores para ambos campos:
      ```json
      {
        "username": ["This field may not be blank."],
        "password": ["This password is too short. It must contain at least 8 characters.", "This password is entirely numeric."]
      }
      ```

### Casos de Error - Formato de Request

14. **Request con formato JSON inválido**
    - **Request**: `"invalid json"`
    - **Response esperado**: `400 Bad Request` o `415 Unsupported Media Type`

15. **Request sin Content-Type correcto**
    - **Request**: Sin header `Content-Type: application/json`
    - **Response esperado**: Puede variar según la configuración

## Notas Importantes

1. **Mensajes de error en inglés**: Los mensajes de error de Django vienen en inglés por defecto. Si necesitas traducirlos, necesitarías configurar la internacionalización.

2. **Validaciones del modelo**: Las validaciones del modelo User de Django se ejecutan automáticamente cuando se intenta crear el usuario.

3. **Validadores de contraseña**: Los validadores de contraseña se ejecutan en el método `create_user()` de Django, que es llamado por el serializer.

4. **Orden de validación**: 
   - Primero se validan los campos requeridos del serializer
   - Luego se validan las restricciones del modelo (longitud, unicidad)
   - Finalmente se ejecutan los validadores de contraseña

## Cómo Probar

### Usando curl

```bash
# Registro exitoso
curl -X POST http://localhost:8000/api/user/register/ \
  -H "Content-Type: application/json" \
  -d '{"username": "testuser", "password": "SecurePass123!"}'

# Username duplicado
curl -X POST http://localhost:8000/api/user/register/ \
  -H "Content-Type: application/json" \
  -d '{"username": "testuser", "password": "SecurePass123!"}'

# Password muy corto
curl -X POST http://localhost:8000/api/user/register/ \
  -H "Content-Type: application/json" \
  -d '{"username": "testuser2", "password": "123"}'
```

### Usando Python requests

```python
import requests

url = "http://localhost:8000/api/user/register/"

# Caso exitoso
response = requests.post(url, json={
    "username": "testuser",
    "password": "SecurePass123!"
})
print(response.status_code)  # 201
print(response.json())

# Caso con error
response = requests.post(url, json={
    "username": "testuser",  # Duplicado
    "password": "123"  # Muy corto y numérico
})
print(response.status_code)  # 400
print(response.json())  # Ver errores específicos
```

### Usando Postman

1. Crear una nueva request POST
2. URL: `http://localhost:8000/api/user/register/`
3. Headers: `Content-Type: application/json`
4. Body (raw JSON): `{"username": "testuser", "password": "SecurePass123!"}`
5. Enviar y verificar la respuesta

