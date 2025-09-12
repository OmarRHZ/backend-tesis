#!/usr/bin/env python
"""
Script para iniciar los workers de Celery
"""
import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'src.geoapp.settings')
django.setup()

from src.geoapp.celery import app

if __name__ == '__main__':
    app.start() 