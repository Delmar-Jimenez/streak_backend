from datetime import timedelta
import csv
from io import StringIO

from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from quinielas.models import Usuario, Torneo, Equipo, EquipoTorneo, Fase, Partido, Quiniela, Participante, Pronostico
from quinielas.views_insights import fold_line, ics_text


class ProFiltersTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.user = Usuario.objects.create_user('pro', 'pro@example.test', 'Local!482Seguro', es_pro=True)
        self.other = Usuario.objects.create_user('other', 'other@example.test', 'Local!482Seguro')
        self.t = Torneo.objects.create(nombre='Copa del Mundo de prueba', temporada='2026', estado='ACTIVO', formato='GRUPOS_ELIMINATORIA', tipo_participantes='SELECCIONES')
        self.draft = Torneo.objects.create(nombre='Mundial sin publicar', temporada='2030')
        self.group = Fase.objects.create(torneo=self.t, nombre='Grupos', tipo='GRUPOS', orden=1)
        self.knockout = Fase.objects.create(torneo=self.t, nombre='Final', tipo='ELIMINATORIA', orden=2)
        self.a, self.b, self.c = [Equipo.objects.create(nombre=name) for name in ['Argentina', 'México', 'Japón']]
        for team, group in [(self.a, ' A '), (self.b, 'a'), (self.c, 'B')]:
            EquipoTorneo.objects.create(torneo=self.t, equipo=team, grupo=group)
        self.match = self.make_match()
        self.final = self.make_match(fase=self.knockout)
        self.cross = self.make_match(equipo_visita=self.c)
        self.pool = Quiniela.objects.create(nombre='Amigos', torneo=self.t, creador=self.user, codigo_unico='PRO123', max_participantes=100)
        self.member = Participante.objects.create(quiniela=self.pool, usuario=self.user)
        self.rival = Participante.objects.create(quiniela=self.pool, usuario=self.other)
        self.client.force_authenticate(self.user)

    def make_match(self, **kwargs):
        data = dict(torneo=self.t, fase=self.group, equipo_local=self.a, equipo_visita=self.b,
                    fecha_hora=timezone.now()+timedelta(days=2))
        return Partido.objects.create(**(data | kwargs))

    def prediction(self, member=None, match=None, **kwargs):
        return Pronostico.objects.create(participante=member or self.member, partido=match or self.match,
                                        goles_local_pred=2, goles_visita_pred=1, **kwargs)

    def test_public_filters_exclude_drafts_and_validate_values(self):
        self.client.force_authenticate(None)
        rows = self.client.get('/api/torneos/?buscar=mundo&temporada=2026&formato=GRUPOS_ELIMINATORIA&estado=ACTIVO').json()
        self.assertEqual([row['id'] for row in rows], [self.t.pk])
        self.assertEqual(self.client.get('/api/torneos/?formato=LIGA').json(), [])
        self.assertEqual(self.client.get('/api/torneos/?formato=unknown').status_code, 400)
        self.assertEqual(self.client.get('/api/torneos/?estado=BORRADOR').status_code, 400)
        self.assertEqual(self.client.get(f'/api/torneos/{self.draft.pk}/filtros/').status_code, 404)
        options = self.client.get(f'/api/torneos/{self.t.pk}/filtros/').json()
        self.assertEqual(options['grupos'], ['A', 'B'])
        self.assertEqual(len(options['fases']), 2)

    def test_groups_only_match_same_group_in_group_phase_on_both_clients(self):
        for path in [f'/api/torneos/{self.t.pk}/partidos/', f'/api/quinielas/{self.pool.pk}/partidos/']:
            rows = self.client.get(path, {'grupo': 'a', 'equipo': self.b.pk, 'fase': self.group.pk}).json()
            self.assertEqual([row['id'] for row in rows], [self.match.pk])
            self.assertEqual(rows[0]['grupo'], 'A')
            self.assertEqual(self.client.get(path, {'grupo':'A', 'fase':self.knockout.pk}).json(), [])
            self.assertEqual(self.client.get(path, {'grupo':'Z'}).status_code, 400)
            self.assertEqual(self.client.get(path, {'equipo':'-1'}).status_code, 400)
        self.assertIsNone(self.client.get(f'/api/partidos/{self.final.pk}/').json()['grupo'])
        self.assertIsNone(self.client.get(f'/api/partidos/{self.cross.pk}/').json()['grupo'])

    def test_clubs_and_national_teams_are_explicit_and_independent_of_format(self):
        club = Torneo.objects.create(nombre='Mundial de clubes de prueba', temporada='2026', estado='ACTIVO',
                                    formato='GRUPOS_ELIMINATORIA', tipo_participantes='CLUBES')
        legacy = Torneo.objects.create(nombre='Sin categoría', temporada='2026', estado='ACTIVO')
        for category, expected in [('CLUBES', club.pk), ('SELECCIONES', self.t.pk), ('SIN_CLASIFICAR', legacy.pk)]:
            rows = self.client.get('/api/torneos/', {'tipo_participantes': category}).json()
            self.assertEqual([row['id'] for row in rows], [expected])
            self.assertEqual(rows[0]['tipo_participantes'], category)
        self.assertEqual(self.client.get('/api/torneos/?tipo_participantes=unknown').status_code, 400)
        self.assertEqual(self.client.get(f'/api/torneos/{self.t.pk}/filtros/').json()['tipo_participantes'], 'SELECCIONES')

    def test_own_finalized_stats_and_corrected_results(self):
        self.prediction()
        self.prediction(self.rival)
        self.prediction(match=self.final)
        self.match.estado = 'FINALIZADO'
        self.match.goles_local, self.match.goles_visita = 2, 1
        self.match.save()
        r = self.client.get('/api/pro/estadisticas/').json()
        self.assertEqual((r['resumen']['evaluados'], r['resumen']['exactos'], r['resumen']['puntos']), (1, 1, 5))
        self.assertEqual(r['resumen']['porcentaje_acierto'], 100)
        self.match.estado = 'CANCELADO'
        self.match.save()
        r = self.client.get('/api/pro/estadisticas/').json()['resumen']
        self.assertEqual((r['evaluados'], r['porcentaje_acierto'], r['puntos']), (0, 0, 0))

    def test_pro_permissions_revocation_and_temporary_password(self):
        paths = ['/api/pro/estadisticas/', '/api/pro/pronosticos/exportar/', '/api/pro/calendario/', f'/api/quinielas/{self.pool.pk}/tabla/exportar/']
        self.user.es_pro = False
        self.user.save()
        for path in paths:
            response = self.client.get(path)
            self.assertEqual(response.status_code, 403)
            self.assertEqual(response.json()['error']['codigo'], 'PRO_REQUERIDO')
        self.user.es_pro = True
        self.user.pass_temporal_flag = True
        self.user.save()
        for path in paths:
            self.assertEqual(self.client.get(path).json()['error']['codigo'], 'PASSWORD_TEMPORAL')
        self.client.force_authenticate(None)
        for path in paths:
            self.assertEqual(self.client.get(path).status_code, 401)

    def test_stats_and_downloads_work_with_mobile_jwt(self):
        self.client.force_authenticate(None)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(self.user).access_token}')
        self.assertEqual(self.client.get('/api/pro/estadisticas/').status_code, 200)
        self.assertEqual(self.client.get('/api/pro/calendario/').status_code, 200)
        data = self.client.get('/api/pro/estado/').json()
        self.assertTrue(data['capacidades']['estadisticas'])
        self.assertEqual(data['plan']['max_participantes'], 100)
        self.assertGreaterEqual(len(data['plan']['beneficios']), 6)

    def test_csv_no_rivals_predictions_or_spreadsheet_formulas(self):
        self.pool.nombre = '=HYPERLINK("https://example.test")'
        self.pool.save()
        self.prediction()
        self.prediction(self.rival)
        response = self.client.get('/api/pro/pronosticos/exportar/')
        rows = list(csv.reader(StringIO(response.content.decode('utf-8-sig'))))
        self.assertEqual(len(rows), 2)
        self.assertTrue(rows[1][0].startswith("'="))
        self.assertIn('no-store', response['Cache-Control'])
        self.assertIn('attachment;', response['Content-Disposition'])

    def test_ranking_export_membership_and_ties(self):
        response = self.client.get(f'/api/quinielas/{self.pool.pk}/tabla/exportar/')
        rows = list(csv.reader(StringIO(response.content.decode('utf-8-sig'))))
        self.assertEqual([row[0] for row in rows[1:]], ['1', '1'])
        self.member.delete()
        self.assertEqual(self.client.get(f'/api/quinielas/{self.pool.pk}/tabla/exportar/').status_code, 404)

    def test_filter_tournament_does_not_expose_other_memberships(self):
        for path in ['/api/pro/estadisticas/', '/api/pro/pronosticos/exportar/', '/api/pro/calendario/']:
            self.assertEqual(self.client.get(path, {'torneo': self.draft.pk}).status_code, 404)
            self.assertEqual(self.client.get(path, {'torneo': 'invalid'}).status_code, 400)
            self.assertEqual(self.client.get(path, {'torneo': self.t.pk}).status_code, 200)

    def test_calendar_only_open_matches_and_deduplicates_across_pools(self):
        second = Quiniela.objects.create(nombre='Otra', torneo=self.t, creador=self.user, codigo_unico='PRO456', max_participantes=20)
        Participante.objects.create(quiniela=second, usuario=self.user)
        self.final.estado = 'SUSPENDIDO'
        self.final.save()
        self.cross.fecha_hora = timezone.now()+timedelta(minutes=4)
        self.cross.save()
        response = self.client.get('/api/pro/calendario/')
        text = response.content.decode('utf-8')
        self.assertEqual(text.count('BEGIN:VEVENT'), 1)
        self.assertIn(f'UID:partido-{self.match.pk}-cierre@streak', text)
        self.assertIn('TRIGGER:-PT30M', text)
        self.assertIn(self.match.cierre_pronosticos.strftime('%Y%m%dT%H%M%SZ'), text)
        self.assertIn('no-store', response['Cache-Control'])
        self.assertTrue(all(len(line.encode('utf-8')) <= 75 for line in text.split('\r\n')))

    def test_calendar_escapes_and_folds_multibyte_text(self):
        text = ics_text('México, Japón; Copa\\\r\nBEGIN:VEVENT' * 10)
        folded = fold_line('SUMMARY:' + text)
        self.assertTrue(all(len(line.encode('utf-8')) <= 75 for line in folded.split('\r\n')))
        self.assertEqual(folded.replace('\r\n ', ''), 'SUMMARY:' + text)
        self.assertNotIn('\r\nBEGIN:VEVENT', folded)
