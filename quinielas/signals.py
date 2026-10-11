from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from .models import Partido, Pronostico
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
