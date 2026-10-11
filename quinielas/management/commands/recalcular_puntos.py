from django.core.management.base import BaseCommand
from quinielas.models import Participante
from quinielas.scoring import recalcular_participantes


class Command(BaseCommand):
    help = 'Recalcula pronosticos y totales a partir de los marcadores actuales.'

    def handle(self, *args, **options):
        ids = list(Participante.objects.values_list('id', flat=True).order_by('id'))
        for offset in range(0, len(ids), 500):
            recalcular_participantes(ids[offset:offset + 500])
        self.stdout.write(self.style.SUCCESS(f'{len(ids)} participantes recalculados.'))
