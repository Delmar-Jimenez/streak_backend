from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier

from django.db import close_old_connections
from django.test import TransactionTestCase, skipUnlessDBFeature
from django.utils import timezone
from rest_framework.test import APIClient

from quinielas.models import Usuario, Torneo, Equipo, Fase, Partido, Quiniela, Participante, Pronostico


@skipUnlessDBFeature('has_select_for_update')
class ConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.owner = Usuario.objects.create_user('owner')
        self.a = Usuario.objects.create_user('a')
        self.b = Usuario.objects.create_user('b')
        self.torneo = Torneo.objects.create(nombre='Liga', temporada='2026', estado='ACTIVO')
        self.fase = Fase.objects.create(torneo=self.torneo, nombre='Fase', orden=1, tipo='LIGA')
        self.local = Equipo.objects.create(torneo=self.torneo, nombre='Local')
        self.visita = Equipo.objects.create(torneo=self.torneo, nombre='Visita')
        self.quiniela = Quiniela.objects.create(torneo=self.torneo, creador=self.owner, nombre='Amigos', codigo_unico='ABC123', max_participantes=2)
        self.member = Participante.objects.create(quiniela=self.quiniela, usuario=self.owner)

    def test_two_joins_cannot_overfill_last_seat(self):
        barrier = Barrier(2)

        def join(pk):
            close_old_connections()
            try:
                client = APIClient()
                client.force_authenticate(Usuario.objects.get(pk=pk))
                barrier.wait(timeout=10)
                return client.post('/api/quinielas/unirse/', {'codigo_unico': 'ABC123'}).status_code
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            statuses = list(pool.map(join, [self.a.pk, self.b.pk]))
        self.assertEqual(sorted(statuses), [201, 400])
        self.assertEqual(self.quiniela.participantes.count(), 2)

    def test_simultaneous_match_results_preserve_both_scores(self):
        matches = []
        for _ in range(2):
            partido = Partido.objects.create(torneo=self.torneo, fase=self.fase, equipo_local=self.local,
                equipo_visita=self.visita, fecha_hora=timezone.now() + timedelta(hours=1))
            Pronostico.objects.create(participante=self.member, partido=partido, goles_local_pred=2, goles_visita_pred=1)
            matches.append(partido.pk)
        barrier = Barrier(2)

        def finish(pk):
            close_old_connections()
            try:
                partido = Partido.objects.get(pk=pk)
                partido.estado = 'FINALIZADO'
                partido.goles_local, partido.goles_visita = 2, 1
                barrier.wait(timeout=10)
                partido.save()
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(finish, matches))
        self.member.refresh_from_db()
        self.assertEqual(self.member.puntos_totales, 10)
        self.assertEqual(list(self.member.pronosticos.values_list('puntos_obtenidos', flat=True)), [5, 5])
