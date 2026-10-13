from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver
from .models import Partido, Pronostico, Usuario, Equipo
from .scoring import recalcular_participantes


@receiver(post_save, sender=Partido)
def calcular_puntuacion_partido(sender, instance, raw=False, **kwargs):
    if not raw:
        recalcular_participantes(instance.pronosticos.values_list('participante_id', flat=True))


@receiver(post_save, sender=Pronostico)
def calcular_puntuacion_pronostico(sender, instance, raw=False, **kwargs):
    if not raw:
        recalcular_participantes([instance.participante_id])


@receiver(post_delete, sender=Pronostico)
def quitar_puntuacion_pronostico(sender, instance, **kwargs):
    recalcular_participantes([instance.participante_id])


@receiver(pre_save, sender=Usuario)
@receiver(pre_save, sender=Equipo)
def recordar_imagen_anterior(sender, instance, raw=False, **kwargs):
    if raw or not instance.pk:
        return
    field = 'foto' if sender is Usuario else 'escudo'
    old = sender.objects.filter(pk=instance.pk).values_list(field, flat=True).first()
    instance._imagen_anterior = old if old and old != getattr(instance, field).name else None


@receiver(post_save, sender=Usuario)
@receiver(post_save, sender=Equipo)
def retirar_imagen_reemplazada(sender, instance, raw=False, **kwargs):
    if not raw and getattr(instance, '_imagen_anterior', None):
        field = 'foto' if sender is Usuario else 'escudo'
        retirar_imagen_sin_referencias(getattr(instance, field).storage, instance._imagen_anterior)
        instance._imagen_anterior = None


def retirar_imagen_sin_referencias(storage, name):
    # Legacy rows can share an image path; preserve it until the last reference is gone.
    if not Usuario.objects.filter(foto=name).exists() and not Equipo.objects.filter(escudo=name).exists():
        storage.delete(name)


@receiver(post_delete, sender=Usuario)
@receiver(post_delete, sender=Equipo)
def retirar_imagen_eliminada(sender, instance, **kwargs):
    field = 'foto' if sender is Usuario else 'escudo'
    image = getattr(instance, field)
    if image:
        retirar_imagen_sin_referencias(image.storage, image.name)
