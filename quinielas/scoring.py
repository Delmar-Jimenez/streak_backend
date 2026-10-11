from django.db import transaction
from .models import Participante, Pronostico


def puntos_pronostico(pronostico):
    partido = pronostico.partido
    if partido.estado != 'FINALIZADO' or partido.goles_local is None or partido.goles_visita is None:
        return 0
    real = partido.goles_local - partido.goles_visita
    pred = pronostico.goles_local_pred - pronostico.goles_visita_pred
    if (partido.goles_local, partido.goles_visita) == (pronostico.goles_local_pred, pronostico.goles_visita_pred):
        return 5
    if (real > 0) - (real < 0) == (pred > 0) - (pred < 0):
        return 4 if real == pred else 3
    return 0


@transaction.atomic
def recalcular_participantes(ids):
    # A stable lock order serializes scoring of different matches for the same players.
    participantes = list(Participante.objects.select_for_update().filter(pk__in=list(ids)).order_by('pk'))
    totals = {p.pk: 0 for p in participantes}
    pronosticos = list(Pronostico.objects.filter(participante_id__in=totals).select_related('partido'))
    for pronostico in pronosticos:
        pronostico.puntos_obtenidos = puntos_pronostico(pronostico)
        totals[pronostico.participante_id] += pronostico.puntos_obtenidos
    Pronostico.objects.bulk_update(pronosticos, ['puntos_obtenidos'])
    for participante in participantes:
        participante.puntos_totales = totals[participante.pk]
    Participante.objects.bulk_update(participantes, ['puntos_totales'])
