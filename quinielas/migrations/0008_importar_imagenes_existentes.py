from io import BytesIO
from pathlib import Path

from django.conf import settings
from django.db import migrations
from PIL import Image, UnidentifiedImageError


def importar_imagenes(apps, schema_editor):
    archivo = apps.get_model('quinielas', 'ImagenArchivo')
    alias = schema_editor.connection.alias
    roots = [Path(settings.MEDIA_ROOT).resolve(), Path(settings.BASE_DIR).resolve()]
    nombres = set()
    for modelo, campo in [('Usuario', 'foto'), ('Equipo', 'escudo')]:
        nombres.update(apps.get_model('quinielas', modelo).objects.using(alias).exclude(
            **{campo: ''}).values_list(campo, flat=True))
    missing = 0
    for nombre in filter(None, nombres):
        if archivo.objects.using(alias).filter(pk=nombre).exists():
            continue
        imported = False
        for root in roots:
            path = (root / nombre).resolve()
            if not path.is_relative_to(root) or not path.is_file() or path.stat().st_size > 5 * 1024 * 1024:
                continue
            try:
                with Image.open(path) as source:
                    if source.format not in ('JPEG', 'PNG', 'WEBP') or source.width * source.height > 16_000_000:
                        continue
                    normalized = source.convert('RGBA')
                    normalized.thumbnail((1024, 1024))
                    output = BytesIO()
                    normalized.save(output, format='WEBP', quality=85)
                    archivo.objects.using(alias).create(nombre=nombre, contenido=output.getvalue(), tipo='image/webp')
                    imported = True
                    break
            except (OSError, UnidentifiedImageError, Image.DecompressionBombError):
                continue
        if not imported:
            missing += 1
    if missing:
        print(f'Imagenes antiguas no disponibles en disco: {missing}. Requieren volver a cargarse desde el administrador.')


class Migration(migrations.Migration):
    dependencies = [('quinielas', '0007_normalizar_fases')]
    operations = [migrations.RunPython(importar_imagenes, migrations.RunPython.noop)]
