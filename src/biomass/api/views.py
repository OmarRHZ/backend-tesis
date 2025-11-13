from django.shortcuts import redirect
from django.contrib.auth.models import User
from rest_framework import generics, status
from .serializers import (
    UserSerializer, AnalyzeGeoJSONSerializer, AOISerializer, BiomassStatsSerializer, 
    ChangePasswordSerializer, UserDetailSerializer, PasswordResetRequestSerializer, 
    PasswordResetConfirmSerializer
)        
from rest_framework.permissions import AllowAny, IsAuthenticated
from allauth.socialaccount.models import SocialAccount, SocialToken
from allauth.account.views import PasswordChangeView
from django.contrib.auth.decorators import login_required
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.contrib.sites.shortcuts import get_current_site
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from rest_framework.decorators import api_view, action, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from core.ml_models.gee_predictor import extract_features_from_geojson
from datetime import datetime
from biomass.models import AOI, BiomassStats
from joblib import load
from django.utils.timezone import now
import json
from .tasks import analyze_geojson_task
from celery.result import AsyncResult
from django.contrib.gis.geos import GEOSGeometry
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets
from sklearn.linear_model import LinearRegression
import numpy as np
import os
import uuid

User= get_user_model()
frontend_url = os.getenv('FRONTEND_URL')
print("Frontend URL:", frontend_url)

class UserCreateView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [AllowAny]
    
    def create(self, request, *args, **kwargs):
        """
        Crea un nuevo usuario y devuelve una respuesta personalizada
        """
        serializer = self.get_serializer(data=request.data)
        
        # Validar los datos
        if not serializer.is_valid():
            # Respuesta personalizada para errores de validación
            return Response(
                {
                    'success': False,
                    'message': 'Error al registrar usuario',
                    'errors': serializer.errors
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Crear el usuario
        try:
            user = serializer.save()
            
            # Respuesta personalizada de éxito
            return Response(
                {
                    'success': True,
                    'message': 'Usuario registrado exitosamente',
                    'data': {
                        'id': user.id,
                        'username': user.username,
                        'email': user.email
                    }
                },
                status=status.HTTP_201_CREATED
            )
        except Exception as e:
            # Respuesta personalizada para errores inesperados
            return Response(
                {
                    'success': False,
                    'message': 'Error al crear el usuario',
                    'error': str(e)
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class UserDetailView(generics.RetrieveUpdateAPIView):
    queryset = User.objects.all()
    serializer_class = UserDetailSerializer

    def get_object(self):
        user = self.request.user
        return user

class PasswordResetRequestView(APIView):
    """
    Vista para solicitar recuperación de contraseña
    Envía un email con el enlace para resetear la contraseña
    """
    permission_classes = [AllowAny]
    
    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(
                {
                    'success': False,
                    'message': 'Error en los datos proporcionados',
                    'errors': serializer.errors
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        email = serializer.validated_data['email'].lower().strip()
        
        try:
            # Buscar el usuario por email
            user = User.objects.filter(email=email).first()
            
            # Por seguridad, siempre devolvemos el mismo mensaje
            # No revelamos si el email existe o no en la base de datos
            if user:
                # Generar token de recuperación
                token = default_token_generator.make_token(user)
                uid = urlsafe_base64_encode(force_bytes(user.pk))
                
                # Construir la URL de reset
                frontend_url = getattr(settings, 'FRONTEND_URL', os.getenv('FRONTEND_URL', 'http://localhost:5173'))
                reset_url = f"{frontend_url}/reset-password?uid={uid}&token={token}"
                
                # Crear el contenido del email
                subject = 'Recuperación de Contraseña'
                message = f"""
Hola {user.username},

Has solicitado recuperar tu contraseña. Por favor, haz clic en el siguiente enlace para restablecer tu contraseña:

{reset_url}

Este enlace expirará en 24 horas.

Si no solicitaste este cambio, puedes ignorar este email.

Saludos,
El equipo de la aplicación
                """
                
                # Enviar el email
                try:
                    send_mail(
                        subject,
                        message,
                        settings.DEFAULT_FROM_EMAIL if hasattr(settings, 'DEFAULT_FROM_EMAIL') else 'noreply@example.com',
                        [user.email],
                        fail_silently=False,
                    )
                except Exception as e:
                    print(f"Error al enviar email: {str(e)}")
                    # En desarrollo, el email se imprime en la consola
                    # En producción, esto debería manejarse mejor
            
            # Siempre devolvemos el mismo mensaje por seguridad
            return Response(
                {
                    'success': True,
                    'message': 'Si el email existe en nuestro sistema, recibirás un enlace para recuperar tu contraseña.'
                },
                status=status.HTTP_200_OK
            )
            
        except Exception as e:
            return Response(
                {
                    'success': False,
                    'message': 'Error al procesar la solicitud',
                    'error': str(e)
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class PasswordResetConfirmView(APIView):
    """
    Vista para confirmar el reset de contraseña con token
    """
    permission_classes = [AllowAny]
    
    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(
                {
                    'success': False,
                    'message': 'Error en los datos proporcionados',
                    'errors': serializer.errors
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        uid = serializer.validated_data['uid']
        token = serializer.validated_data['token']
        new_password = serializer.validated_data['new_password']
        
        try:
            # Decodificar el UID
            user_id = force_str(urlsafe_base64_decode(uid))
            user = User.objects.get(pk=user_id)
            
            # Verificar el token
            if not default_token_generator.check_token(user, token):
                return Response(
                    {
                        'success': False,
                        'message': 'El token de recuperación no es válido o ha expirado.'
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Cambiar la contraseña
            user.set_password(new_password)
            user.save()
            
            return Response(
                {
                    'success': True,
                    'message': 'Contraseña restablecida exitosamente. Ahora puedes iniciar sesión con tu nueva contraseña.'
                },
                status=status.HTTP_200_OK
            )
            
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            return Response(
                {
                    'success': False,
                    'message': 'El enlace de recuperación no es válido.'
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {
                    'success': False,
                    'message': 'Error al restablecer la contraseña',
                    'error': str(e)
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
@login_required
def google_login_callback(request):
    user = request.user
    social_accounts = SocialAccount.objects.filter(user=user)
    print("Social accounts for user:", social_accounts)

    social_account = social_accounts.first()

    if not social_account:
        print("No social account found for user:", user)
        return redirect(f'{frontend_url}/login/callback/?error=NoSocialAccount')
    
    social_token = SocialToken.objects.filter(account=social_account, account__provider='google').first()
    
    if social_token:
        print("Google social token for user:", social_token.token)

        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)

        return redirect(f'{frontend_url}/login/callback/?access_token={access_token}')
    else:
        print("No Google social token found for user:", user)
        return redirect(f'{frontend_url}/login/callback/?error=NoGoogleToken')

@csrf_exempt
def validate_google_token(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            google_access_token = data.get('access_token')
            print("Google access token:", google_access_token)

            if not google_access_token:
                return JsonResponse({'detail': 'Google access token is required'}, status=400)
            return JsonResponse({'valid': True})
        
        except json.JSONDecodeError:
            return JsonResponse({'detail': 'Invalid JSON'}, status=400)
    return JsonResponse({'detail': 'Invalid request method'}, status=405)

model = load("core/ml_models/model.joblib")

class AnalyzeGeoJSONView(APIView):
    #añadir campos para la api "geojson", el user_id se obtiene del token
    serializer_class = AnalyzeGeoJSONSerializer

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        geojson = serializer.validated_data['geojson']

        #obtener el user_id del usuario logueado
        user_id = request.user.id

        #print("Geojson:", geojson)
        print("User ID:", user_id)

        if not geojson:
            return Response({"error": "Missing geojson"}, status=400)

        try:
            content = geojson.read().decode('utf-8')
            geojson_data = json.loads(content)

            # Validar que el GeoJSON contenga exactamente una geometría
            geometry_dict = None

            if geojson_data.get('type') == 'FeatureCollection':
                features = geojson_data.get('features', [])
                if not features:
                    return Response({"error": "El GeoJSON no contiene geometrías."}, status=400)
                if len(features) != 1:
                    return Response({"error": "El GeoJSON debe contener exactamente un polígono."}, status=400)
                geometry_dict = features[0].get('geometry')
            elif geojson_data.get('type') == 'Feature':
                geometry_dict = geojson_data.get('geometry')
            else:
                # Podría ser una geometría directa (Polygon, MultiPolygon, etc.)
                geometry_dict = geojson_data

            if not geometry_dict:
                return Response({"error": "No se encontró geometría válida en el GeoJSON."}, status=400)

            if geometry_dict['type'] not in ['Polygon', 'MultiPolygon']:
                return Response({"error": "Solo se aceptan geometrías tipo Polygon o MultiPolygon"}, status=400)

            # Si es MultiPolygon, validar que represente una única forma
            if geometry_dict['type'] == 'MultiPolygon':
                coordinates = geometry_dict.get('coordinates', [])
                if not coordinates:
                    return Response({"error": "La geometría MultiPolygon no contiene coordenadas."}, status=400)
                if len(coordinates) > 1:
                    return Response({"error": "El GeoJSON debe contener un único polígono."}, status=400)

            geom = GEOSGeometry(json.dumps(geometry_dict), srid=4326)

            # Crear AOI en base de datos
            aoi = AOI.objects.create(
                user_id=user_id,
                name=f"AOI_{now().date()}",
                geometry=geom,
                task_id=None,
                status='analysing'
            )

            # Iniciar tarea en segundo plano
            task = analyze_geojson_task.delay(geometry_dict, user_id, aoi.id)
            
            # Actualizar el task_id del AOI
            aoi.task_id = task.id
            aoi.save()

            return Response({
                "message": "Análisis iniciado en segundo plano",
                "task_id": task.id,
                "aoi_id": aoi.id,
                "name": aoi.name,
                "status": "PROCESSING"
            }, status=202)  # 202 Accepted

        except Exception as e:
            return Response({"error": f"Invalid geometry: {str(e)}"}, status=400)
class TaskStatusView(APIView):
    def get(self, request, task_id):
        """
        Consultar el estado de una tarea en segundo plano
        """
        task_result = AsyncResult(task_id)
        
        # Buscar el AOI asociado a esta tarea y actualizar su status
        try:
            aoi = AOI.objects.filter(task_id=task_id).first()
            if aoi:
                if task_result.state == 'SUCCESS':
                    aoi.status = 'completed'
                    aoi.save()
                elif task_result.state in ['FAILURE', 'REVOKED']:
                    aoi.status = 'error'
                    aoi.save()
                elif task_result.state in ['PENDING', 'PROGRESS']:
                    aoi.status = 'analysing'
                    aoi.save()
        except Exception as e:
            print(f"Error al actualizar status del AOI: {str(e)}")
        
        if task_result.state == 'PENDING':
            response = {
                'state': task_result.state,
                'current': 0,
                'total': 100,
                'status': 'Tarea pendiente...'
            }
        elif task_result.state == 'PROGRESS':
            response = {
                'state': task_result.state,
                'current': task_result.info.get('current', 0),
                'total': task_result.info.get('total', 100),
                'status': task_result.info.get('status', '')
            }
        elif task_result.state == 'SUCCESS':
            response = {
                'state': task_result.state,
                'current': 100,
                'total': 100,
                'status': 'Completado',
                'result': task_result.result
            }
        else:
            response = {
                'state': task_result.state,
                'current': 0,
                'total': 100,
                'status': str(task_result.info),
            }
        
        return Response(response)
    
class AOIListView(viewsets.ModelViewSet):
    serializer_class = AOISerializer
    queryset = AOI.objects.all()
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['user']
    #hacer que el user sea el usuario logueado
    def get_queryset(self):
        return super().get_queryset().filter(user=self.request.user)

    @action(detail=True, methods=["post"], url_path="share", permission_classes=[IsAuthenticated])
    def generate_share_link(self, request, pk=None):
        aoi = self.get_object()
        token = uuid.uuid4().hex
        aoi.share_token = token
        aoi.save(update_fields=["share_token"])
        return Response({"share_token": token}, status=200)

    @action(detail=True, methods=["post"], url_path="revoke-share", permission_classes=[IsAuthenticated])
    def revoke_share_link(self, request, pk=None):
        aoi = self.get_object()
        aoi.share_token = None
        aoi.save(update_fields=["share_token"])
        return Response({"share_token": None}, status=200)

class BiomassStatsListView(viewsets.ModelViewSet):  
    serializer_class = BiomassStatsSerializer
    queryset = BiomassStats.objects.all()
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['aoi']

class ChangePasswordViewSet(viewsets.ViewSet):

    def create(self, request):
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = request.user
        password = serializer.validated_data["password"]

        # Actualiza la contraseña del usuario
        user.set_password(password)
        user.save()

        return Response({"message": "Contraseña cambiada exitosamente."})
    

    

@api_view(['GET'])
@permission_classes([AllowAny])
def get_data_stats(request):
    aoi_id = request.query_params.get('aoi_id')
    share_token = request.query_params.get('share_token')

    if not aoi_id:
        return Response({"error": "aoi_id is required"}, status=400)
    
    try:
        aoi = AOI.objects.get(id=aoi_id)
    except AOI.DoesNotExist:
        return Response({"error": "AOI no encontrado"}, status=404)

    if share_token:
        if aoi.share_token != share_token:
            return Response({"error": "Token de acceso inválido"}, status=403)
    else:
        if not request.user.is_authenticated or aoi.user_id != request.user.id:
            return Response({"error": "No tienes permiso para acceder a este AOI."}, status=403)
    #obtener el centro con coordenadas
    centroid = aoi.geometry.centroid
    centroid_coords = (centroid.x, centroid.y)

    #calcular el zoom para el mapa según el area del aoi
    area = aoi.geometry.area
    if area < 1000000:
        zoom = 11
    elif area < 10000000:
        zoom = 12
    else:
        zoom = 13

    print("Centroide:", centroid_coords)
    
    
    
    biomass_stats = BiomassStats.objects.filter(aoi_id=aoi_id)
    mean_mg = 0
    mean_carbon = 0
    mean_co2 = 0
    dict_biomass_stats = {}
    dict_carbon_stats = {}
    dict_co2_stats = {}

    dict_pred_biomass_stats = {}
    dict_pred_carbon_stats = {}
    dict_pred_co2_stats = {}

    for stat in biomass_stats:
        dict_biomass_stats[stat.year] = stat.mean_mg
        dict_carbon_stats[stat.year] = stat.mean_carbon
        dict_co2_stats[stat.year] = stat.mean_carbon * 3.67
        mean_mg += stat.mean_mg
        mean_carbon += stat.mean_carbon
        mean_co2 += stat.mean_carbon * 3.67
    #verificar si tiene los años seguidos, si no, agregar los años faltantes con la media del año anterior y el siguiente
    years = list(dict_biomass_stats.keys())
    years.sort()
    min_year = min(years)
    max_year = max(years)
    for year in range(min_year, max_year + 1):
        if year not in years:
            dict_biomass_stats[year] = (dict_biomass_stats[year - 1] + dict_biomass_stats[year + 1]) / 2
            dict_carbon_stats[year] = (dict_carbon_stats[year - 1] + dict_carbon_stats[year + 1]) / 2
            dict_co2_stats[year] = (dict_co2_stats[year - 1] + dict_co2_stats[year + 1]) / 2

    #ordenar los años
    years = list(dict_biomass_stats.keys())
    years.sort()
    dict_biomass_stats = {year: dict_biomass_stats[year] for year in years}
    dict_carbon_stats = {year: dict_carbon_stats[year] for year in years}
    dict_co2_stats = {year: dict_co2_stats[year] for year in years}
    mean_mg /= len(years)
    mean_carbon /= len(years)
    mean_co2 /= len(years)
     # Paso 1: convertir llaves a enteros
    years_list = sorted([int(y) for y in dict_biomass_stats.keys()])
    values = [dict_biomass_stats[y] for y in years_list]

    # Paso 2: preparar arrays
    X = np.array(years_list).reshape(-1, 1)
    y = np.array(values)

    # Paso 3: entrenar modelo de regresión
    model = LinearRegression()
    model.fit(X, y)
    # Predecir para los próximos 3 años
    last_year = max(years_list)
    #predecir para los proximos 3 años desde el ultimo año
    future_years = [last_year + i for i in range(1, 4)]

    X_future = np.array(future_years).reshape(-1, 1)
    biomass_pred = model.predict(X_future)



    for i in range(len(future_years)):
        dict_pred_biomass_stats[future_years[i]] = biomass_pred[i]
        dict_pred_carbon_stats[future_years[i]] = biomass_pred[i] * 0.47
        dict_pred_co2_stats[future_years[i]] = dict_pred_carbon_stats[future_years[i]] * 3.67

    

    return Response({
        "biomass_stats": dict_biomass_stats,
        "carbon_stats": dict_carbon_stats,
        "co2_stats": dict_co2_stats,
        "pred_biomass_stats": dict_pred_biomass_stats,
        "pred_carbon_stats": dict_pred_carbon_stats,
        "pred_co2_stats": dict_pred_co2_stats,
        "centroid_coords": centroid_coords,
        "aoi_geometry": aoi.geometry.json, #corregir para que sea un json valido
        "zoom": zoom,
        "mean_mg": mean_mg,
        "mean_carbon": mean_carbon,
        "mean_co2": mean_co2,
        "share_token": aoi.share_token,
        "aoi_name": aoi.name,
    })

    