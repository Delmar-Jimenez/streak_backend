from django.db import migrations


def reparar(apps, schema_editor):
    alias = schema_editor.connection.alias
    Quiniela = apps.get_model('quinielas', 'Quiniela')
    Participante = apps.get_model('quinielas', 'Participante')
    Pronostico = apps.get_model('quinielas', 'Pronostico')
    Pago = apps.get_model('quinielas', 'Pago')
    for quiniela in Quiniela.objects.using(alias).iterator():
        Participante.objects.using(alias).get_or_create(quiniela_id=quiniela.pk, usuario_id=quiniela.creador_id)
        count = Participante.objects.using(alias).filter(quiniela_id=quiniela.pk).count()
        if quiniela.max_participantes < count:
            Quiniela.objects.using(alias).filter(pk=quiniela.pk).update(max_participantes=count)
    Participante.objects.using(alias).update(puntos_totales=0)
    totals = {}
    for pred in Pronostico.objects.using(alias).select_related('partido').iterator():
        partido = pred.partido
        points = 0
        if partido.estado == 'FINALIZADO' and partido.goles_local is not None and partido.goles_visita is not None:
            real = partido.goles_local - partido.goles_visita
            forecast = pred.goles_local_pred - pred.goles_visita_pred
            if (partido.goles_local, partido.goles_visita) == (pred.goles_local_pred, pred.goles_visita_pred):
                points = 5
            elif (real > 0) - (real < 0) == (forecast > 0) - (forecast < 0):
                points = 4 if real == forecast else 3
        Pronostico.objects.using(alias).filter(pk=pred.pk).update(puntos_obtenidos=points)
        totals[pred.participante_id] = totals.get(pred.participante_id, 0) + points
    for pk, total in totals.items():
        Participante.objects.using(alias).filter(pk=pk).update(puntos_totales=total)
    Pago.objects.using(alias).filter(estado='APROBADO').update(estado='COMPLETADO')


class Migration(migrations.Migration):
    dependencies = [('quinielas', '0002_pago_clave_idempotencia_pago_moneda_and_more')]
    operations = [migrations.RunPython(reparar, migrations.RunPython.noop)]
