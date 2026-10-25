from datetime import timedelta

from django.contrib.auth.models import Permission
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from quinielas.models import Usuario, Torneo, Equipo, EquipoTorneo, Fase, Partido


class PortalTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = Usuario.objects.create_user('jugador_web', 'jugador@example.test', 'Partido!Seguro482')
        self.client = APIClient(enforce_csrf_checks=True)
        self.torneo = Torneo.objects.create(nombre='Liga web', temporada='2026', estado='ACTIVO')
        self.fase = Fase.objects.create(torneo=self.torneo, nombre='Jornada', tipo='LIGA', orden=1)
        self.local = Equipo.objects.create(nombre='Local')
        self.visitante = Equipo.objects.create(nombre='Visitante')
        for team in (self.local, self.visitante):
            EquipoTorneo.objects.create(torneo=self.torneo, equipo=team)
        self.partido = Partido.objects.create(torneo=self.torneo, fase=self.fase, equipo_local=self.local,
            equipo_visita=self.visitante, fecha_hora=timezone.now()+timedelta(days=1))

    def csrf(self):
        return self.client.get('/web/sesion/').json()['csrf']

    def login(self, username='jugador_web', password='Partido!Seguro482'):
        return self.client.post('/web/entrar/', {'username': username, 'password': password},
            format='json', HTTP_X_CSRFTOKEN=self.csrf())

    def post(self, url, data):
        return self.client.post(url, data, format='json', HTTP_X_CSRFTOKEN=self.csrf())

    def test_public_shell_and_session_do_not_expose_credentials(self):
        response = self.client.get('/')
        self.assertContains(response, 'STREAK')
        self.assertIn("script-src 'self'", response['Content-Security-Policy'])
        self.assertIn('no-store', response['Cache-Control'])
        data = self.client.get('/web/sesion/').json()
        self.assertIsNone(data['usuario'])
        self.assertFalse(data['administrador'])
        self.assertEqual(set(data), {'usuario', 'administrador', 'csrf'})

    def test_login_csrf_required_including_anonymous(self):
        response = self.client.post('/web/entrar/', {'username': self.user.username, 'password':'Partido!Seguro482'}, format='json')
        self.assertEqual(response.status_code, 403)
        self.assertIsNone(self.client.get('/web/sesion/').json()['usuario'])

    def test_session_can_create_pool_and_predict_but_unsafe_calls_need_csrf(self):
        response = self.login()
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('access', response.json())
        self.assertTrue(self.client.cookies['sessionid']['httponly'])
        data = {'nombre':'Amigos', 'torneo':self.torneo.pk, 'max_participantes':20}
        self.assertEqual(self.client.post('/api/quinielas/', data, format='json').status_code, 403)
        response = self.post('/api/quinielas/', data)
        self.assertEqual(response.status_code, 201, response.content)
        pool = response.json()['id']
        prediction = self.post(f'/api/quinielas/{pool}/pronosticos/', {'partido':self.partido.pk, 'goles_local_pred':2, 'goles_visita_pred':1})
        self.assertEqual(prediction.status_code, 201, prediction.content)
        self.assertEqual(self.client.get(f'/api/quinielas/{pool}/partidos/').json()[0]['mi_pronostico']['goles_local_pred'], 2)

    def test_normal_user_cannot_access_administration_or_escalate(self):
        self.login()
        self.assertEqual(self.client.get('/web/administracion/').status_code, 403)
        self.client.patch('/api/usuarios/me/', {'is_staff':True, 'es_pro':True}, format='json', HTTP_X_CSRFTOKEN=self.csrf())
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_staff)
        self.assertFalse(self.user.es_pro)

    def test_admin_modules_follow_model_permissions(self):
        self.user.is_staff = True
        self.user.save()
        self.user.user_permissions.add(Permission.objects.get(codename='view_equipo'))
        self.login()
        self.assertTrue(self.client.get('/web/sesion/').json()['administrador'])
        response = self.client.get('/web/administracion/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual([m['modelo'] for m in response.json()['modulos']], ['Equipo'])
        self.assertIsNone(response.json()['modulos'][0]['crear_url'])
        self.assertContains(self.client.get('/admin/quinielas/equipo/'), 'Volver a STREAK')
        self.assertEqual(self.client.get('/admin/quinielas/usuario/').status_code, 403)

    def test_temporary_password_requires_change_and_expired_one_cannot_login(self):
        self.user.pass_temporal_flag = True
        self.user.pass_temporal_expira = timezone.now()+timedelta(hours=2)
        self.user.save()
        self.assertEqual(self.login().status_code, 200)
        self.assertEqual(self.client.get('/api/quinielas/mias/').status_code, 403)
        self.assertTrue(self.client.get('/web/sesion/').json()['usuario']['pass_temporal_flag'])
        self.post('/web/salir/', {})
        self.user.pass_temporal_expira = timezone.now()-timedelta(hours=1)
        self.user.save()
        self.assertEqual(self.login().status_code, 400)

    def test_logout_csrf_and_password_change_invalidate_web_session(self):
        self.login()
        self.assertEqual(self.client.post('/web/salir/', {}, format='json').status_code, 403)
        response = self.post('/api/auth/cambiar-password/', {'old_password':'Partido!Seguro482', 'new_password':'Otra!ClavePartido972'})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertIsNone(self.client.get('/web/sesion/').json()['usuario'])
        self.assertEqual(self.login(password='Otra!ClavePartido972').status_code, 200)
        self.assertEqual(self.post('/web/salir/', {}).status_code, 200)
        self.assertEqual(self.client.get('/api/quinielas/mias/').status_code, 401)

    def test_mobile_jwt_remains_usable_without_session_cookie_or_csrf(self):
        mobile = APIClient(enforce_csrf_checks=True)
        token = mobile.post('/api/auth/login/', {'username':self.user.username, 'password':'Partido!Seguro482'},format='json').json()['access']
        mobile.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        response = mobile.post('/api/quinielas/', {'nombre':'Móvil', 'torneo':self.torneo.pk, 'max_participantes':10},format='json')
        self.assertEqual(response.status_code, 201, response.content)

    def test_anonymous_cannot_create_pool_or_see_administration(self):
        self.assertEqual(self.post('/api/quinielas/', {'nombre':'Anon','torneo':self.torneo.pk,'max_participantes':2}).status_code,401)
        self.assertEqual(self.client.get('/web/administracion/').status_code,403)
