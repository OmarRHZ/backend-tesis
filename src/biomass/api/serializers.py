from rest_framework import serializers
from django.contrib.auth.models import User
from biomass.models import AOI, BiomassStats

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'password']
        extra_kwargs = {'password': {'write_only': True}}

    def create(self, validated_data):
        user = User.objects.create_user(**validated_data)
        return user
    
class UserDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name']

class AnalyzeGeoJSONSerializer(serializers.Serializer):
    geojson = serializers.FileField()

    class Meta:
        fields = ['geojson']

class AOISerializer(serializers.ModelSerializer):
    class Meta:
        model = AOI
        fields = ['id', 'name', 'file_path', 'uploaded_at', 'geometry', 'task_id', 'user']
    
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