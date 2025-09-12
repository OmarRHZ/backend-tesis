import ee
import numpy as np
import pandas as pd

# Inicializa Earth Engine (esto se hace una vez)
ee.Initialize(project="ee-ortesis1221")

def get_geometry_from_geojson(geojson):
    # Si es FeatureCollection, toma la geometría del primer feature
    if geojson.get('type') == 'FeatureCollection':
        return geojson['features'][0]['geometry']
    # Si es Feature, toma la geometría
    elif geojson.get('type') == 'Feature':
        return geojson['geometry']
    # Si es Geometry directamente
    elif geojson.get('type') in ['Polygon', 'MultiPolygon']:
        return geojson
    else:
        raise ValueError("Formato de GeoJSON no reconocido")

def extract_features_from_geojson(geojson, year: int, scale=100) -> pd.DataFrame:

    start_date = '2019-01-01'
    end_date   = '2022-12-31'
    # 1. Definir el área de interés
    geometry = get_geometry_from_geojson(geojson)
    aoi = (ee.FeatureCollection(geojson).geometry()
       if geojson.get('type') == 'FeatureCollection'
       else ee.Geometry(geojson['geometry'] if geojson.get('type')=='Feature'
                        else geojson))

    # 2. Colecciones y procesamiento (igual que tu código)
    s2  = ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")     
    csp = ee.ImageCollection('GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED')
    s2_proj = ee.Image(s2.first()).select('B4').projection()

    def link_collection(img):
        cs_img = csp.filterDate(img.date(), img.date().advance(1, 'day')).first()
        return img.addBands(cs_img)

    def mask_clouds(img):
        return img.updateMask(img.select('cs').gte(0.5))

    def scale_bands(img):
        return img.multiply(0.0001).copyProperties(img, ['system:time_start'])

    def add_indices(img):
        ndvi  = img.normalizedDifference(['B8','B4']).rename('ndvi')
        mndwi = img.normalizedDifference(['B3','B11']).rename('mndwi')
        ndbi  = img.normalizedDifference(['B11','B8']).rename('ndbi')
        evi   = img.expression(
            '2.5*((NIR-RED)/(NIR+6*RED-7.5*BLUE+1))',
            {'NIR':img.select('B8'),'RED':img.select('B4'),'BLUE':img.select('B2')}
        ).rename('evi')
        bsi   = img.expression(
            '((X+Y)-(A+B))/((X+Y)+(A+B))',
            {'X':img.select('B11'),'Y':img.select('B4'),
            'A':img.select('B8'),'B':img.select('B2')}
        ).rename('bsi')
        return img.addBands([ndvi,mndwi,ndbi,evi,bsi])

    s2_comp = (s2.filterBounds(aoi)
                .filterDate(f"{year}-01-01", f"{year}-12-31")
                .map(link_collection)
                .map(mask_clouds)
                .select('B.*')
                .map(scale_bands)
                .map(add_indices)
                .median()
                .setDefaultProjection(s2_proj)
                )
    
    #print("s2_comp: ", s2_comp)
    
    dem_ic = (ee.ImageCollection('COPERNICUS/DEM/GLO30')
           .filterBounds(aoi).select('DEM'))
    dem_proj  = dem_ic.first().select(0).projection()
    elev      = dem_ic.mosaic().rename('dem').setDefaultProjection(dem_proj)
    slope     = ee.Terrain.slope(elev)
    dem_bands = elev.addBands(slope)   

    grid_scale   = 100
    grid_proj    = ee.Projection('EPSG:3857').atScale(grid_scale)

    stacked = s2_comp.addBands(dem_bands).reproject(grid_proj)

    #print("stacked: ", stacked.getInfo())

    #print("stacked: ", stacked)

    # 3. Extraer los valores de los píxeles dentro del polígono
    # Puedes limitar el número de muestras con 'numPixels' si el área es muy grande
    # samples     = (stacked.stratifiedSample(numPoints=1000,
    #                                       region=aoi,
    #                                       scale=grid_scale,
    #                                       classValues=[0,1],
    #                                       classPoints=[0,1000],
    #                                       dropNulls=True,
    #                                       tileScale=16))
    
    # Extraer muestras aleatorias para predicción (NO datos GEDI)
    samples = stacked.sample(region=aoi, scale=grid_scale, numPixels=1000, geometries=False)

    #print('Muestras extraídas:', samples.size().getInfo())
    features = samples.getInfo()['features']
    if not features:
        #raise ValueError("No se extrajeron muestras. Revisa el área o el año.")
        #print("No se extrajeron muestras. Revisa el área o el año.", year)
        return None
    # 4. Convertir a DataFrame
    df = pd.DataFrame([f['properties'] for f in features])

    return df

# from joblib import load
# import json
# from datetime import datetime

# # Cargar el modelo
# modelo = load('model.joblib')

# geojson_path_3 = 'Geojson/test-draw-map.json'         # ← pon aquí tu archivo
# with open(geojson_path_3) as f:
#     aoi_json = json.load(f)

# #recoletar por año hasta el año actual
# for year in range(2019, datetime.now().year + 1):
#     # Extraer X
#     df = extract_features_from_geojson(aoi_json, year=year)
#     if df is None:
#         continue
#     X = df[modelo.feature_names_in_]  # Asegúrate de usar los mismos nombres de columnas

#     # Predecir
#     y_pred = modelo.predict(X)

#     biomasa_media = y_pred.mean()
#     print(f"Biomasa promedio del área: {biomasa_media:.2f} Mg/ha")

#     # Supongamos que cada muestra representa 1 ha (ajusta según tu escala real)
#     biomasa_total = biomasa_media * len(y_pred)  # O multiplica por el área real en ha
#     print(f"Biomasa total estimada: {biomasa_total:.2f} Mg")
