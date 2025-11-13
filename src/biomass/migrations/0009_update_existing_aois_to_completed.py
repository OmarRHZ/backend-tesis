# Generated manually to update existing AOIs to 'completed' status

from django.db import migrations


def update_existing_aois_to_completed(apps, schema_editor):
    """
    Actualiza todos los AOIs existentes que tienen status 'analysing' 
    (valor por defecto) a 'completed', asumiendo que fueron analizados antes
    de agregar el campo status.
    """
    AOI = apps.get_model('biomass', 'AOI')
    # Actualizar todos los AOIs que tienen status 'analysing' a 'completed'
    # Esto asume que los AOIs existentes ya fueron procesados
    AOI.objects.filter(status='analysing').update(status='completed')


def reverse_update(apps, schema_editor):
    """
    Función reversa: vuelve a poner 'analysing' a los que fueron actualizados
    (aunque esto no es necesario, es buena práctica tenerla)
    """
    AOI = apps.get_model('biomass', 'AOI')
    # No hacemos nada en reversa, ya que no podemos distinguir
    # cuáles eran 'analysing' originalmente
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('biomass', '0008_aoi_status'),
    ]

    operations = [
        migrations.RunPython(
            update_existing_aois_to_completed,
            reverse_update
        ),
    ]

