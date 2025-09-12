from celery import shared_task
from django.utils import timezone
from datetime import datetime
from ..models import AOI, BiomassStats
from core.ml_models.gee_predictor import extract_features_from_geojson
import joblib
import os
import numpy as np
from sklearn.metrics import r2_score, mean_squared_error

# Cargar el modelo - ruta corregida
model_path = os.path.join(os.path.dirname(__file__), '..', '..', 'core', 'ml_models', 'model.joblib')
model = joblib.load(model_path)

@shared_task(bind=True)
def analyze_geojson_task(self, geojson_data, user_id, aoi_id):
    """
    Tarea en segundo plano para analizar GeoJSON y calcular biomasa
    """
    try:
        # Actualizar el estado de la tarea
        self.update_state(
            state='PROGRESS',
            meta={'current': 0, 'total': 100, 'status': 'Iniciando análisis...'}
        )
        
        # Obtener el AOI
        aoi = AOI.objects.get(id=aoi_id)
        
        current_year = datetime.now().year
        years = list(range(2019, current_year + 1))
        results = []
        aoi.task_id = self.request.id
        aoi.save()
        
        for i, year in enumerate(years):
            try:
                # Actualizar progreso
                progress = int((i / len(years)) * 100)
                self.update_state(
                    state='PROGRESS',
                    meta={
                        'current': progress,
                        'total': 100,
                        'status': f'Procesando año {year}...'
                    }
                )
                
                # Extraer características y predecir
                df = extract_features_from_geojson(geojson_data, year)
                if df is None:
                    continue
                X = df[model.feature_names_in_]
                pred_biomass = model.predict(X)

                mean_mg = float(pred_biomass.mean())
                mean_carbon = float(mean_mg * 0.47)

                print(f"Mean MG: {mean_mg}, Mean Carbon: {mean_carbon}")
                
                #rmse = np.sqrt(mean_squared_error(df['biomass'], pred_biomass))
                #r2 = r2_score(df['biomass'], pred_biomass)

                #print(f"RMSE: {rmse}, R2: {r2}")
                # Guardar estadísticas
                BiomassStats.objects.create(
                    aoi=aoi,
                    year=year,
                    mean_mg=mean_mg,
                    mean_carbon=mean_carbon,
                )
                
                results.append({
                    "year": year,
                    "biomass": round(mean_mg, 2),
                    "carbon": round(mean_carbon, 2),
                    "co2": round(mean_carbon * 3.67, 2)
                    
                })
                
            except Exception as e:
                print(e)
                results.append({
                    "year": year,
                    "error": f"Could not process year {year}: {str(e)}"
                })
        
        # Actualizar progreso final
        self.update_state(
            state='SUCCESS',
            meta={
                'current': 100,
                'total': 100,
                'status': 'Análisis completado',
                'results': results
            }
        )
        
        return {
            'aoi_id': aoi_id,
            'name': aoi.name,
            'results': results
        }
        
    except Exception as e:
        # En caso de error
        self.update_state(
            state='FAILURE',
            meta={'error': str(e)}
        )
        raise
