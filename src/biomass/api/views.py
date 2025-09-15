from django.shortcuts import redirect
from django.contrib.auth.models import User
from rest_framework import generics
from .serializers import UserSerializer, AnalyzeGeoJSONSerializer, AOISerializer, BiomassStatsSerializer, ChangePasswordSerializer, UserDetailSerializer        
from rest_framework.permissions import AllowAny, IsAuthenticated
from allauth.socialaccount.models import SocialAccount, SocialToken
from allauth.account.views import PasswordChangeView
from django.contrib.auth.decorators import login_required
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import get_user_model
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view
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

User= get_user_model()
frontend_url = os.getenv('FRONTEND_URL')
print("Frontend URL:", frontend_url)

class UserCreateView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [AllowAny]

class UserDetailView(generics.RetrieveUpdateAPIView):
    queryset = User.objects.all()
    serializer_class = UserDetailSerializer

    def get_object(self):
        user = self.request.user
        return user
    
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

            features = geojson_data['features'][0]
            geometry_dict = features['geometry']

            if geometry_dict['type'] not in ['Polygon', 'MultiPolygon']:
                return Response({"error": "Solo se aceptan geometrías tipo Polygon o MultiPolygon"}, status=400)

            geom = GEOSGeometry(json.dumps(geometry_dict), srid=4326)

            # Crear AOI en base de datos
            aoi = AOI.objects.create(
                user_id=user_id,
                name=f"AOI_{now().date()}",
                geometry=geom,
                task_id=None
            )

            # Iniciar tarea en segundo plano
            task = analyze_geojson_task.delay(geometry_dict, user_id, aoi.id)

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
def get_data_stats(request):
    aoi_id = request.query_params.get('aoi_id')
    if not aoi_id:
        return Response({"error": "aoi_id is required"}, status=400)
    
    aoi = AOI.objects.get(id=aoi_id)
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
        "zoom": zoom
    })

    