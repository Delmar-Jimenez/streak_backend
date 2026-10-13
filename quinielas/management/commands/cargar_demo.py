from django.core.management.base import BaseCommand
from quinielas.demo import cargar_demo


class Command(BaseCommand):
    help = 'Crea datos DEMO idempotentes, sin claves de acceso ni cambios a datos reales.'

    def handle(self, *args, **options):
        result = cargar_demo()
        self.stdout.write(self.style.SUCCESS(f'DEMO lista: {result}'))
