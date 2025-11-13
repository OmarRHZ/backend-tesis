import re
from rest_framework import serializers
from django.contrib.auth.models import User
from biomass.models import AOI, BiomassStats

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'password']
        extra_kwargs = {
            'password': {
                'write_only': True,
                'min_length': 8,  # Longitud mínima
                'style': {'input_type': 'password'}  # Para el browsable API
            },
            'username': {
                'min_length': 3,  # Longitud mínima para username
                'max_length': 150  # Longitud máxima (ya está en el modelo)
            },
            'email': {
                'required': True,  # Email es requerido
            }
        }

    # Validación específica para el campo username
    def validate_username(self, value):
        """
        Valida el campo username
        """
        # Convertir a minúsculas para evitar duplicados por mayúsculas/minúsculas
        value = value.lower().strip()
        
        # Verificar que no esté vacío después del trim
        if not value:
            raise serializers.ValidationError("El nombre de usuario no puede estar vacío.")
        
        # Verificar que no contenga espacios
        if ' ' in value:
            raise serializers.ValidationError("El nombre de usuario no puede contener espacios.")
        
        # Verificar que solo contenga caracteres alfanuméricos y algunos especiales
        if not re.match(r'^[a-zA-Z0-9@.+_-]+$', value):
            raise serializers.ValidationError(
                "El nombre de usuario solo puede contener letras, números y los caracteres: @, ., +, -, _"
            )
        
        # Verificar que no sea una palabra reservada
        reserved_words = ['admin', 'administrator', 'root', 'user', 'test', 'api']
        if value.lower() in reserved_words:
            raise serializers.ValidationError("Este nombre de usuario no está permitido.")
        
        return value

    # Validación específica para el campo password
    def validate_password(self, value):
        """
        Valida el campo password
        """
        # Verificar que no esté vacío
        if not value:
            raise serializers.ValidationError("La contraseña no puede estar vacía.")
        
        # Verificar longitud mínima (aunque ya está en extra_kwargs, esto da un mensaje personalizado)
        if len(value) < 8:
            raise serializers.ValidationError("La contraseña debe tener al menos 8 caracteres.")
        
        # Verificar que contenga al menos una letra
        if not re.search(r'[a-zA-Z]', value):
            raise serializers.ValidationError("La contraseña debe contener al menos una letra.")
        
        # Verificar que contenga al menos un número
        if not re.search(r'\d', value):
            raise serializers.ValidationError("La contraseña debe contener al menos un número.")
        
        return value

    # Validación específica para el campo email
    def validate_email(self, value):
        """
        Valida el campo email
        """
        # Verificar que no esté vacío
        if not value:
            raise serializers.ValidationError("El email es requerido.")
        
        # Normalizar el email (convertir a minúsculas)
        value = value.lower().strip()
        
        # Verificar formato básico de email
        if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', value):
            raise serializers.ValidationError("El formato del email no es válido.")
        
        # Verificar que el email no esté ya en uso
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Este email ya está registrado.")
        
        return value

    # Validación que involucra múltiples campos
    def validate(self, data):
        """
        Valida los datos completos del serializer
        """
        username = data.get('username', '')
        password = data.get('password', '')
        
        # Verificar que el password no sea igual al username
        if username and password and username.lower() == password.lower():
            raise serializers.ValidationError({
                'password': 'La contraseña no puede ser igual al nombre de usuario.'
            })
        
        # Verificar que el password no contenga el username
        if username and password and username.lower() in password.lower():
            raise serializers.ValidationError({
                'password': 'La contraseña no puede contener el nombre de usuario.'
            })
        
        return data

    def create(self, validated_data):
        user = User.objects.create_user(**validated_data)
        return user
    
class UserDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name']
    
    def validate_username(self, value):
        """
        Valida que el username no esté en uso por otro usuario
        """
        value = value.lower().strip()
        user = self.instance  # El usuario actual que se está actualizando
        
        # Verificar que no esté vacío
        if not value:
            raise serializers.ValidationError("El nombre de usuario no puede estar vacío.")
        
        # Verificar que no contenga espacios
        if ' ' in value:
            raise serializers.ValidationError("El nombre de usuario no puede contener espacios.")
        
        # Verificar que solo contenga caracteres permitidos
        if not re.match(r'^[a-zA-Z0-9@.+_-]+$', value):
            raise serializers.ValidationError(
                "El nombre de usuario solo puede contener letras, números y los caracteres: @, ., +, -, _"
            )
        
        # Verificar que no esté en uso por otro usuario
        if User.objects.filter(username=value).exclude(pk=user.pk).exists():
            raise serializers.ValidationError("Este nombre de usuario ya está en uso.")
        
        return value
    
    def validate_email(self, value):
        """
        Valida que el email no esté en uso por otro usuario
        """
        value = value.lower().strip()
        user = self.instance  # El usuario actual que se está actualizando
        
        # Verificar que no esté vacío
        if not value:
            raise serializers.ValidationError("El email es requerido.")
        
        # Verificar formato básico de email
        if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', value):
            raise serializers.ValidationError("El formato del email no es válido.")
        
        # Verificar que no esté en uso por otro usuario
        if User.objects.filter(email=value).exclude(pk=user.pk).exists():
            raise serializers.ValidationError("Este email ya está registrado.")
        
        return value

class AnalyzeGeoJSONSerializer(serializers.Serializer):
    geojson = serializers.FileField()

    class Meta:
        fields = ['geojson']

class AOISerializer(serializers.ModelSerializer):
    class Meta:
        model = AOI
        fields = ['id', 'name', 'file_path', 'uploaded_at', 'geometry', 'task_id', 'user', 'favorite', 'share_token', 'status']
    
class BiomassStatsSerializer(serializers.ModelSerializer):
    class Meta:
        model = BiomassStats
        fields = ['id', 'aoi', 'year', 'mean_mg', 'mean_carbon', ]

class ChangePasswordSerializer(serializers.Serializer):
    password = serializers.CharField()
    confirm_password = serializers.CharField()

    def validate(self, data):
        if data["password"] != data["confirm_password"]:
            raise serializers.ValidationError("Las contraseñas no coinciden.")
        return data

class PasswordResetRequestSerializer(serializers.Serializer):
    """
    Serializer para solicitar recuperación de contraseña
    """
    email = serializers.EmailField(required=True)
    
    def validate_email(self, value):
        """
        Valida que el email exista en la base de datos
        """
        value = value.lower().strip()
        if not User.objects.filter(email=value).exists():
            # Por seguridad, no revelamos si el email existe o no
            # Pero internamente sabemos que no existe
            pass
        return value

class PasswordResetConfirmSerializer(serializers.Serializer):
    """
    Serializer para confirmar el reset de contraseña con token
    """
    token = serializers.CharField(required=True)
    uid = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, min_length=8)
    confirm_password = serializers.CharField(required=True)
    
    def validate(self, data):
        """
        Valida que las contraseñas coincidan
        """
        if data["new_password"] != data["confirm_password"]:
            raise serializers.ValidationError("Las contraseñas no coinciden.")
        
        # Validar que la contraseña tenga al menos una letra y un número
        password = data["new_password"]
        if not re.search(r'[a-zA-Z]', password):
            raise serializers.ValidationError("La contraseña debe contener al menos una letra.")
        if not re.search(r'\d', password):
            raise serializers.ValidationError("La contraseña debe contener al menos un número.")
        
        return data