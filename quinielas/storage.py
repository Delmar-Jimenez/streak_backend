from io import BytesIO
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.files.storage import Storage
from django.urls import reverse
from django.utils.deconstruct import deconstructible
from PIL import Image, UnidentifiedImageError


@deconstructible
class DatabaseImageStorage(Storage):
    """Small public images persist with PostgreSQL, not Render's temporary disk."""

    def _save(self, name, content):
        from .models import ImagenArchivo

        if content.size > 5 * 1024 * 1024:
            raise ValidationError('La imagen no puede superar 5 MB.')
        try:
            content.seek(0)
            with Image.open(content) as source:
                if source.width * source.height > 16_000_000:
                    raise ValidationError('La imagen supera 16 megapixeles.')
                if source.format not in ('JPEG', 'PNG', 'WEBP'):
                    raise ValidationError('Usa una imagen JPEG, PNG o WebP.')
                source.load()
                normalized = source.convert('RGBA')
                normalized.thumbnail((1024, 1024))
                output = BytesIO()
                normalized.save(output, format='WEBP', quality=85)
        except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
            raise ValidationError('La imagen no es valida.') from None
        prefix = 'escudos' if name.startswith('escudos/') else 'perfiles'
        name = f'{prefix}/{uuid4().hex}.webp'
        ImagenArchivo.objects.create(nombre=name, contenido=output.getvalue())
        return name

    def _open(self, name, mode='rb'):
        from .models import ImagenArchivo

        try:
            image = ImagenArchivo.objects.get(pk=name)
        except ImagenArchivo.DoesNotExist:
            raise FileNotFoundError(name) from None
        return ContentFile(bytes(image.contenido), name=name)

    def exists(self, name):
        from .models import ImagenArchivo
        return ImagenArchivo.objects.filter(pk=name).exists()

    def delete(self, name):
        from .models import ImagenArchivo
        ImagenArchivo.objects.filter(pk=name).delete()

    def size(self, name):
        with self.open(name) as content:
            return content.size

    def url(self, name):
        return reverse('media_imagen', kwargs={'nombre': name})
