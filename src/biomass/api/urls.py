from django.urls import path, include
from .views import *
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register(r'biomass-stats', BiomassStatsListView, basename='biomass-stats')
router.register(r'aois', AOIListView, basename='aois')

urlpatterns = [
    path('analyze-geojson/', AnalyzeGeoJSONView.as_view(), name='analyze-geojson'),
    path('task-status/<str:task_id>/', TaskStatusView.as_view(), name='task-status'),
    path('data-stats/', get_data_stats, name='data-stats'),

    #path('biomass-stats/', BiomassStatsListView.as_view(), name='biomass-stats-list'),
]

urlpatterns += router.urls