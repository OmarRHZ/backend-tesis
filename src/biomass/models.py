from django.db import models
from django.contrib.auth.models import User  # Importas el modelo existente
from django.contrib.gis.db import models as gis_models

class AOI(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=200)
    file_path = models.TextField(blank=True, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    geometry = gis_models.PolygonField(null=True, blank=True, srid=4326)  # PostGIS field

class BiomassStats(models.Model):
    aoi = models.ForeignKey(AOI, on_delete=models.CASCADE)
    year = models.SmallIntegerField()
    total_mg = models.FloatField()
    total_carbon = models.FloatField()
    rmse_model = models.FloatField()
    r2_model = models.FloatField()

class BiomassRaster(models.Model):
    aoi = models.ForeignKey(AOI, on_delete=models.CASCADE)
    year = models.SmallIntegerField()
    cog_url = models.TextField()
    mean = models.FloatField()
    min = models.FloatField()
    max = models.FloatField()
    created_at = models.DateTimeField(auto_now_add=True)

class AnalysisJob(models.Model):
    aoi = models.ForeignKey(AOI, on_delete=models.CASCADE)
    status = models.CharField(max_length=50)
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
