from django.db import migrations, models


def normalizar(apps, schema_editor):
    Fase = apps.get_model('quinielas', 'Fase')
    aliases = {'LIGA': 'LIGA', 'REGULAR': 'LIGA', 'FASE_REGULAR': 'LIGA',
        'GRUPOS': 'GRUPOS', 'FASE_DE_GRUPOS': 'GRUPOS', 'FASE_GRUPOS': 'GRUPOS',
        'ELIMINATORIA': 'ELIMINATORIA', 'ELIMINATORIAS': 'ELIMINATORIA',
        'OCTAVOS': 'ELIMINATORIA', 'CUARTOS': 'ELIMINATORIA',
        'SEMIFINAL': 'ELIMINATORIA', 'SEMIFINALES': 'ELIMINATORIA', 'FINAL': 'ELIMINATORIA'}
    for fase in Fase.objects.using(schema_editor.connection.alias).select_related('torneo').all():
        original = fase.tipo.strip().upper().replace(' ', '_')
        value = aliases.get(original)
        if not value and original.isdigit() and fase.torneo.formato == 'LIGA':
            value = 'LIGA'
        if value is None:
            raise RuntimeError(f'La fase {fase.pk} tiene un tipo sin clasificar. Definir LIGA, GRUPOS o ELIMINATORIA antes de migrar.')
        Fase.objects.using(schema_editor.connection.alias).filter(pk=fase.pk).update(tipo=value)


class Migration(migrations.Migration):
    dependencies = [('quinielas', '0006_imagenarchivo_partido_goles_local_prorroga_and_more')]
    operations = [
        migrations.RunPython(normalizar, migrations.RunPython.noop),
        migrations.AddConstraint(model_name='fase', constraint=models.CheckConstraint(
            condition=models.Q(tipo__in=['LIGA', 'GRUPOS', 'ELIMINATORIA']), name='fase_tipo_valido')),
    ]
