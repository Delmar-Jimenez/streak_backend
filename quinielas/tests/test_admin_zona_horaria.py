from datetime import datetime, timezone as dt_timezone

from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from quinielas.middleware import ZonaHorariaAdminMiddleware
from quinielas.models import Equipo, Fase, Partido, Torneo


class ZonaHorariaAdminMiddlewareTests(TestCase):
    def _zona_durante(self, ruta):
        vista = []

        def responder(request):
            vista.append(timezone.get_current_timezone_name())
            return HttpResponse()

        ZonaHorariaAdminMiddleware(responder)(RequestFactory().get(ruta))
        return vista[0]

    def test_admin_usa_hora_de_guatemala(self):
        self.assertEqual(self._zona_durante('/admin/quinielas/partido/'), 'America/Guatemala')

    def test_api_sigue_en_utc(self):
        self.assertEqual(self._zona_durante('/api/torneos/'), 'UTC')

    def test_restaura_utc_despues_del_admin(self):
        self._zona_durante('/admin/')
        self.assertEqual(timezone.get_current_timezone_name(), 'UTC')


class PartidoDesdeAdminTests(TestCase):
    def setUp(self):
        admin = get_user_model().objects.create_superuser('admin_tz', 'admin@x.com', 'Clave1234x')
        self.client.force_login(admin)
        self.torneo = Torneo.objects.create(nombre='Liga', temporada='2026', estado='ACTIVO')
        self.fase = Fase.objects.create(torneo=self.torneo, nombre='Jornada 1', orden=1, tipo='LIGA')
        self.local = Equipo.objects.create(torneo=self.torneo, nombre='Local')
        self.visita = Equipo.objects.create(torneo=self.torneo, nombre='Visita')

    def test_hora_local_del_admin_se_guarda_en_utc(self):
        respuesta = self.client.post(reverse('admin:quinielas_partido_add'), {
            'torneo': self.torneo.pk,
            'fase': self.fase.pk,
            'equipo_local': self.local.pk,
            'equipo_visita': self.visita.pk,
            'fecha_hora_0': '18/10/2026',
            'fecha_hora_1': '14:00:00',
            'estado': Partido.Estado.PROGRAMADO,
        })
        self.assertEqual(respuesta.status_code, 302, getattr(respuesta, 'context', None) and respuesta.context['adminform'].form.errors)
        partido = Partido.objects.get()
        # 14:00 en Guatemala (UTC-6) = 20:00 UTC.
        self.assertEqual(partido.fecha_hora, datetime(2026, 10, 18, 20, 0, tzinfo=dt_timezone.utc))
