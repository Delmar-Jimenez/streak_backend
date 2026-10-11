from datetime import timedelta
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from rest_framework.test import APIClient

from quinielas.models import Usuario, Torneo, Equipo, Fase, Partido, Quiniela, Participante, Pronostico
from quinielas.scoring import recalcular_participantes


class ApiTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.user = Usuario.objects.create_user('ana', 'ana@example.test', 'Strong-password-94!')
        self.rival = Usuario.objects.create_user('luis', 'luis@example.test', 'Strong-password-94!')
        self.outsider = Usuario.objects.create_user('otro', 'otro@example.test', 'Strong-password-94!')
        self.torneo = Torneo.objects.create(nombre='Liga', temporada='2026', estado='ACTIVO')
        self.fase = Fase.objects.create(torneo=self.torneo, nombre='Jornada', orden=1, tipo='LIGA')
        self.local = Equipo.objects.create(torneo=self.torneo, nombre='Local')
        self.visita = Equipo.objects.create(torneo=self.torneo, nombre='Visita')
        self.partido = Partido.objects.create(
            torneo=self.torneo, fase=self.fase, equipo_local=self.local, equipo_visita=self.visita,
            fecha_hora=timezone.now() + timedelta(hours=2),
        )
        self.quiniela = Quiniela.objects.create(nombre='Amigos', torneo=self.torneo, creador=self.user, codigo_unico='ABC123', max_participantes=3)
        self.miembro = Participante.objects.create(quiniela=self.quiniela, usuario=self.user)
        self.otro = Participante.objects.create(quiniela=self.quiniela, usuario=self.rival)
        self.client.force_authenticate(self.user)

    def pronosticar(self, local=2, visita=1, **extra):
        return self.client.post(f'/api/quinielas/{self.quiniela.pk}/pronosticos/', {
            'partido': self.partido.pk, 'goles_local_pred': local, 'goles_visita_pred': visita, **extra,
        }, format='json')

    def test_backdoor_removed_and_errors_are_json(self):
        response = self.client.get('/crear-admin/')
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()['error']['codigo'], 'NO_ENCONTRADO')
        self.assertFalse(Usuario.objects.filter(is_superuser=True).exists())
        self.client.force_authenticate(None)
        response = self.client.get('/api/usuarios/me/')
        self.assertEqual(response.status_code, 401)
        self.assertIn('mensaje', response.json()['error'])

    def test_profile_cannot_escalate_privileges(self):
        response = self.client.patch('/api/usuarios/me/', {
            'first_name': 'Ana', 'es_pro': True, 'is_staff': True, 'is_superuser': True, 'email': 'changed@test.com',
        })
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, 'Ana')
        self.assertEqual(self.user.email, 'ana@example.test')
        self.assertFalse(self.user.es_pro or self.user.is_staff or self.user.is_superuser)
        self.assertNotIn('password', response.data)

    def test_create_enrolls_creator_and_lists_mine(self):
        response = self.client.post('/api/quinielas/', {'nombre': 'Nueva', 'torneo': self.torneo.pk, 'max_participantes': 2})
        self.assertEqual(response.status_code, 201, response.data)
        self.assertTrue(Participante.objects.filter(quiniela_id=response.data['id'], usuario=self.user).exists())
        self.assertEqual(len(self.client.get('/api/quinielas/mias/').data), 2)
        self.assertEqual(self.client.post('/api/quinielas/', {'nombre': 'Cero', 'torneo': self.torneo.pk, 'max_participantes': 0}).status_code, 400)

    def test_join_capacity_duplicate_and_case(self):
        self.client.force_authenticate(self.outsider)
        self.assertEqual(self.client.post('/api/quinielas/unirse/', {'codigo_unico': 'abc123'}).status_code, 201)
        self.assertEqual(self.client.post('/api/quinielas/unirse/', {'codigo_unico': 'ABC123'}).data['error']['codigo'], 'YA_PARTICIPA')
        new = Usuario.objects.create_user('cuarto')
        self.client.force_authenticate(new)
        self.assertEqual(self.client.post('/api/quinielas/unirse/', {'codigo_unico': 'ABC123'}).data['error']['codigo'], 'QUINIELA_LLENA')

    def test_members_only_resources(self):
        self.client.force_authenticate(self.outsider)
        for suffix in ('', 'tabla/', 'participantes/', 'pronosticos/', f'participantes/{self.otro.pk}/pronosticos/'):
            self.assertEqual(self.client.get(f'/api/quinielas/{self.quiniela.pk}/{suffix}').status_code, 404)
        self.assertEqual(self.client.get('/api/quinielas/mias/').data, [])
        self.assertEqual(self.pronosticar().status_code, 404)

    def test_predictions_create_update_and_server_owned_fields(self):
        response = self.pronosticar(puntos_obtenidos=999, participante=self.otro.pk)
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['participante'], self.miembro.pk)
        self.assertEqual(response.data['puntos_obtenidos'], 0)
        self.assertEqual(self.pronosticar(3, 1).status_code, 200)
        self.assertEqual(Pronostico.objects.count(), 1)
        self.assertEqual(self.client.get(f'/api/quinielas/{self.quiniela.pk}/pronosticos/').data[0]['goles_local_pred'], 3)

    def test_prediction_validation(self):
        self.assertEqual(self.pronosticar(-1).status_code, 400)
        self.assertEqual(self.pronosticar(partido='not-an-id').status_code, 400)
        other = Torneo.objects.create(nombre='Otra', temporada='2026', estado='ACTIVO')
        Partido.objects.filter(pk=self.partido.pk).update(torneo=other)
        self.assertEqual(self.pronosticar().status_code, 404)
        self.assertEqual(Pronostico.objects.count(), 0)

    def test_prediction_closes_at_kickoff_even_when_programmed(self):
        self.partido.fecha_hora = timezone.now()
        self.partido.save()
        response = self.pronosticar()
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['error']['codigo'], 'PRONOSTICOS_CERRADOS')
        self.assertEqual(Pronostico.objects.count(), 0)

    def test_prediction_closes_for_non_programmed_matches(self):
        for estado in ('EN_JUEGO', 'SUSPENDIDO', 'CANCELADO', 'FINALIZADO'):
            self.partido.estado = estado
            self.partido.save()
            self.assertEqual(self.pronosticar().status_code, 400)

    def test_rival_predictions_hidden_before_kickoff(self):
        Pronostico.objects.create(participante=self.otro, partido=self.partido, goles_local_pred=1, goles_visita_pred=0)
        url = f'/api/quinielas/{self.quiniela.pk}/participantes/{self.otro.pk}/pronosticos/'
        self.assertEqual(self.client.get(url).data, [])
        self.partido.fecha_hora = timezone.now() - timedelta(minutes=1)
        self.partido.save()
        self.assertEqual(len(self.client.get(url).data), 1)

    def test_temporary_password_blocks_protected_endpoints(self):
        self.user.pass_temporal_flag = True
        self.user.save()
        for url in ('/api/usuarios/me/', '/api/quinielas/mias/', '/api/pro/estado/', '/api/pro/pagos/'):
            self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.pronosticar().status_code, 403)
        response = self.client.post('/api/auth/cambiar-password/', {'old_password': 'Strong-password-94!', 'new_password': 'Another-Strong-772!'})
        self.assertEqual(response.status_code, 200, response.data)
        self.user.refresh_from_db()
        self.assertFalse(self.user.pass_temporal_flag)

    def test_public_catalog_hides_drafts_and_validates_filters(self):
        self.client.force_authenticate(None)
        draft = Torneo.objects.create(nombre='Draft', temporada='2027')
        self.assertEqual(len(self.client.get('/api/torneos/').data), 1)
        self.assertEqual(self.client.get(f'/api/torneos/{draft.pk}/').status_code, 404)
        for suffix in ('', 'equipos/', 'fases/', 'partidos/'):
            self.assertEqual(self.client.get(f'/api/torneos/{self.torneo.pk}/{suffix}').status_code, 200)
        self.assertEqual(self.client.get(f'/api/partidos/{self.partido.pk}/').status_code, 200)
        self.assertEqual(self.client.get(f'/api/torneos/{self.torneo.pk}/partidos/?estado=INVALIDO').status_code, 400)
        self.assertEqual(self.client.get(f'/api/torneos/{self.torneo.pk}/partidos/?fase=abc').status_code, 400)

    def test_table_ranks_ties_without_leaking_email(self):
        response = self.client.get(f'/api/quinielas/{self.quiniela.pk}/tabla/')
        self.assertEqual([row['posicion'] for row in response.data], [1, 1])
        self.assertNotIn('email', response.data[0])

    def test_scoring_accumulates_corrects_and_reverses(self):
        self.pronosticar()
        second = Partido.objects.create(torneo=self.torneo, fase=self.fase, equipo_local=self.local,
            equipo_visita=self.visita, fecha_hora=timezone.now(), estado='FINALIZADO', goles_local=1, goles_visita=0)
        Pronostico.objects.create(participante=self.miembro, partido=second, goles_local_pred=1, goles_visita_pred=0)
        self.partido.estado = 'FINALIZADO'
        self.partido.goles_local, self.partido.goles_visita = 2, 1
        self.partido.save()
        self.miembro.refresh_from_db()
        self.assertEqual(self.miembro.puntos_totales, 10)
        self.partido.save()
        self.miembro.refresh_from_db()
        self.assertEqual(self.miembro.puntos_totales, 10)
        self.partido.goles_local = 3
        self.partido.save()
        self.miembro.refresh_from_db()
        self.assertEqual(self.miembro.puntos_totales, 8)
        self.partido.estado = 'CANCELADO'
        self.partido.save()
        self.miembro.refresh_from_db()
        self.assertEqual(self.miembro.puntos_totales, 5)
        second.delete()
        self.miembro.refresh_from_db()
        self.assertEqual(self.miembro.puntos_totales, 0)

    def test_scoring_rules_exact_difference_outcome_wrong_and_draw(self):
        prediction = Pronostico.objects.create(participante=self.miembro, partido=self.partido, goles_local_pred=2, goles_visita_pred=1)
        for local, visita, expected in ((2, 1, 5), (3, 2, 4), (4, 0, 3), (0, 1, 0), (0, 0, 0)):
            self.partido.estado = 'FINALIZADO'
            self.partido.goles_local, self.partido.goles_visita = local, visita
            self.partido.save()
            prediction.refresh_from_db()
            self.miembro.refresh_from_db()
            self.assertEqual(prediction.puntos_obtenidos, expected)
            self.assertEqual(self.miembro.puntos_totales, expected)
        prediction.goles_local_pred, prediction.goles_visita_pred = 1, 1
        prediction.save()
        self.miembro.refresh_from_db()
        self.assertEqual(self.miembro.puntos_totales, 4)
        prediction.delete()
        self.miembro.refresh_from_db()
        self.assertEqual(self.miembro.puntos_totales, 0)

    def test_rebuild_repairs_stale_totals(self):
        Participante.objects.filter(pk=self.miembro.pk).update(puntos_totales=999)
        recalcular_participantes([self.miembro.pk])
        self.miembro.refresh_from_db()
        self.assertEqual(self.miembro.puntos_totales, 0)

    @override_settings(CORS_ALLOWED_ORIGINS=['https://mobile.example.test'])
    def test_cors_allows_only_configured_origin(self):
        response = self.client.options('/api/usuarios/me/', HTTP_ORIGIN='https://mobile.example.test', HTTP_ACCESS_CONTROL_REQUEST_METHOD='GET')
        self.assertEqual(response['Access-Control-Allow-Origin'], 'https://mobile.example.test')
        response = self.client.options('/api/usuarios/me/', HTTP_ORIGIN='https://other.test', HTTP_ACCESS_CONTROL_REQUEST_METHOD='GET')
        self.assertNotIn('Access-Control-Allow-Origin', response)

    def test_validation_and_method_errors_share_contract(self):
        for response in (self.pronosticar(-5), self.client.delete('/api/usuarios/me/'), self.client.get('/api/not-found/')):
            self.assertIn('codigo', response.json()['error'])
            self.assertIsInstance(response.json()['error']['mensaje'], str)

    def test_registration_validates_password_and_email(self):
        self.client.force_authenticate(None)
        response = self.client.post('/api/auth/register/', {'username': 'nuevo', 'email': 'ANA@EXAMPLE.TEST', 'password': 'Strong-password-94!'})
        self.assertEqual(response.status_code, 400)
        response = self.client.post('/api/auth/register/', {'username': 'nuevo', 'email': 'new@example.test', 'password': '123'})
        self.assertEqual(response.status_code, 400)
        response = self.client.post('/api/auth/register/', {'username': 'nuevo', 'email': 'NEW@EXAMPLE.TEST', 'password': 'Strong-password-94!'})
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['email'], 'new@example.test')
        self.assertNotIn('password', response.data)

    def test_reset_does_not_change_password_until_confirmed(self):
        self.client.force_authenticate(None)
        original = self.user.password
        with patch('builtins.print') as printed:
            known = self.client.post('/api/auth/recuperar/', {'email': self.user.email})
            unknown = self.client.post('/api/auth/recuperar/', {'email': 'unknown@example.test'})
            printed.assert_not_called()
        self.assertEqual(known.data, unknown.data)
        self.user.refresh_from_db()
        self.assertEqual(self.user.password, original)
        self.assertEqual(len(mail.outbox), 1)
        link = mail.outbox[0].body.split()[-1]
        query = parse_qs(urlparse(link).query)
        payload = {'uid': query['uid'][0], 'token': query['token'][0], 'new_password': 'Different-password-99!'}
        response = self.client.post('/api/auth/restablecer/', payload)
        self.assertEqual(response.status_code, 200, response.data)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(payload['new_password']))
        self.assertEqual(self.client.post('/api/auth/restablecer/', payload).status_code, 400)

    def test_reset_rejects_invalid_token_and_weak_password(self):
        self.client.force_authenticate(None)
        payload = {'uid': urlsafe_base64_encode(force_bytes(self.user.pk)), 'token': 'invalid', 'new_password': 'Different-password-99!'}
        self.assertEqual(self.client.post('/api/auth/restablecer/', payload).status_code, 400)
        payload.update(token=default_token_generator.make_token(self.user), new_password='123')
        response = self.client.post('/api/auth/restablecer/', payload)
        self.assertEqual(response.status_code, 400, response.data)

    def test_password_change_invalidates_access_and_refresh(self):
        self.client.force_authenticate(None)
        login = self.client.post('/api/auth/login/', {'username': 'ana', 'password': 'Strong-password-94!'})
        self.assertEqual(login.status_code, 200)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        response = self.client.post('/api/auth/cambiar-password/', {'old_password': 'Strong-password-94!', 'new_password': 'Different-password-99!'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get('/api/usuarios/me/').status_code, 401)
        self.client.credentials()
        self.assertEqual(self.client.post('/api/auth/login/refresh/', {'refresh': login.data['refresh']}).status_code, 401)

    def test_refresh_deleted_user_returns_auth_error(self):
        self.client.force_authenticate(None)
        login = self.client.post('/api/auth/login/', {'username': 'otro', 'password': 'Strong-password-94!'})
        self.outsider.delete()
        self.assertEqual(self.client.post('/api/auth/login/refresh/', {'refresh': login.data['refresh']}).status_code, 401)

    def test_required_put_and_join_codigo_work_without_trailing_slash(self):
        response = self.client.put('/api/usuarios/me', {'first_name': 'Actualizado', 'telefono': '55555555'})
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['first_name'], 'Actualizado')
        self.client.force_authenticate(self.outsider)
        response = self.client.post('/api/quinielas/unirse', {'codigo': 'abc123'})
        self.assertEqual(response.status_code, 201, response.data)
        response = self.client.post('/api/quinielas/unirse', {'codigo': 'ABC123', 'codigo_unico': 'DEF456'})
        self.assertEqual(response.status_code, 400)

    def test_catalog_routes_are_also_available_without_api_prefix(self):
        self.assertEqual(self.client.get('/usuarios/me').status_code, 200)
        self.assertEqual(self.client.put('/usuarios/me', {'first_name': 'Ana'}).status_code, 200)
        self.assertEqual(self.client.get('/torneos').status_code, 200)
        self.assertEqual(self.client.get('/quinielas/mias').status_code, 200)
        self.assertEqual(self.client.get('/pro/estado').status_code, 200)
        response = self.client.post('/quinielas', {'nombre': 'Directa', 'torneo': self.torneo.pk, 'max_participantes': 2})
        self.assertEqual(response.status_code, 201, response.data)

    def test_history_includes_only_own_finished_tournaments(self):
        self.assertEqual(self.client.get('/api/quinielas/historial').data, [])
        self.torneo.estado = 'FINALIZADO'
        self.torneo.save()
        response = self.client.get('/api/quinielas/historial')
        self.assertEqual([row['id'] for row in response.data], [self.quiniela.pk])
        self.client.force_authenticate(self.outsider)
        self.assertEqual(self.client.get('/api/quinielas/historial').data, [])

    def test_quiniela_matches_include_own_prediction_and_points(self):
        self.pronosticar()
        response = self.client.get(f'/api/quinielas/{self.quiniela.pk}/partidos')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[0]['mi_pronostico']['participante'], self.miembro.pk)
        self.assertEqual(response.data[0]['mis_puntos'], 0)
        self.client.force_authenticate(self.outsider)
        self.assertEqual(self.client.get(f'/api/quinielas/{self.quiniela.pk}/partidos').status_code, 404)

    def test_match_detail_hides_rivals_then_returns_points_for_every_member(self):
        self.pronosticar()
        Pronostico.objects.create(participante=self.otro, partido=self.partido, goles_local_pred=3, goles_visita_pred=2)
        url = f'/api/quinielas/{self.quiniela.pk}/partidos/{self.partido.pk}/detalle'
        rows = {row['usuario']: row for row in self.client.get(url).data['participantes']}
        self.assertIsNotNone(rows[self.user.pk]['pronostico'])
        self.assertIsNone(rows[self.rival.pk]['pronostico'])
        self.partido.fecha_hora = timezone.now() - timedelta(hours=2)
        self.partido.estado = 'FINALIZADO'
        self.partido.goles_local, self.partido.goles_visita = 2, 1
        self.partido.save()
        rows = {row['usuario']: row for row in self.client.get(url).data['participantes']}
        self.assertEqual(rows[self.user.pk]['puntos_obtenidos'], 5)
        self.assertEqual(rows[self.rival.pk]['puntos_obtenidos'], 4)
        self.client.force_authenticate(self.outsider)
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_user_detail_uses_user_id_and_includes_unpredicted_matches(self):
        # Deliberately make participant and user IDs differ to verify the uid contract.
        self.otro.delete()
        self.otro = Participante.objects.create(quiniela=self.quiniela, usuario=self.rival)
        Pronostico.objects.create(participante=self.otro, partido=self.partido, goles_local_pred=3, goles_visita_pred=2)
        second = Partido.objects.create(torneo=self.torneo, fase=self.fase, equipo_local=self.local,
            equipo_visita=self.visita, fecha_hora=timezone.now() + timedelta(days=1))
        url = f'/api/quinielas/{self.quiniela.pk}/participantes/{self.rival.pk}/detalle'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['participante']['usuario'], self.rival.pk)
        self.assertEqual(len(response.data['partidos']), 2)
        self.assertTrue(all(row['pronostico'] is None for row in response.data['partidos']))
        self.partido.fecha_hora = timezone.now() - timedelta(hours=2)
        self.partido.estado = 'FINALIZADO'
        self.partido.goles_local, self.partido.goles_visita = 2, 1
        self.partido.save()
        rows = {row['id']: row for row in self.client.get(url).data['partidos']}
        self.assertEqual(rows[self.partido.pk]['puntos_obtenidos'], 4)
        self.assertEqual(rows[second.pk]['puntos_obtenidos'], 0)
        self.client.force_authenticate(self.outsider)
        self.assertEqual(self.client.get(url).status_code, 404)
