from datetime import date, timedelta

from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from quinielas.models import Usuario, Torneo, Quiniela, Participante


class FechaNacimientoTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()

    def registro(self, **extra):
        data = {'username': 'nuevo', 'email': 'nuevo@example.test', 'password': 'Strong-password-94!', **extra}
        return self.client.post('/api/auth/register/', data, format='json')

    def test_registro_sin_fecha(self):
        r = self.registro()
        self.assertEqual(r.status_code, 201)
        self.assertIsNone(r.data['fecha_nacimiento'])

    def test_registro_con_fecha(self):
        r = self.registro(fecha_nacimiento='1995-04-23')
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data['fecha_nacimiento'], '1995-04-23')
        self.assertEqual(Usuario.objects.get(username='nuevo').fecha_nacimiento, date(1995, 4, 23))

    def test_registro_fecha_futura_rechazada(self):
        futura = (date.today() + timedelta(days=1)).isoformat()
        r = self.registro(fecha_nacimiento=futura)
        self.assertEqual(r.status_code, 400)
        self.assertFalse(Usuario.objects.filter(username='nuevo').exists())

    def test_registro_edad_irrazonable_y_formato(self):
        self.assertEqual(self.registro(fecha_nacimiento='1850-01-01').status_code, 400)
        self.assertEqual(self.registro(fecha_nacimiento='23/04/1995').status_code, 400)

    def test_perfil_patch_y_lectura(self):
        user = Usuario.objects.create_user('ana', 'ana@example.test', 'Strong-password-94!')
        self.client.force_authenticate(user)
        self.assertIsNone(self.client.get('/api/usuarios/me/').data['fecha_nacimiento'])
        r = self.client.patch('/api/usuarios/me/', {'fecha_nacimiento': '2000-02-29'}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.client.get('/api/usuarios/me/').data['fecha_nacimiento'], '2000-02-29')
        futura = (date.today() + timedelta(days=5)).isoformat()
        self.assertEqual(self.client.patch('/api/usuarios/me/', {'fecha_nacimiento': futura}, format='json').status_code, 400)
        r = self.client.patch('/api/usuarios/me/', {'fecha_nacimiento': None}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertIsNone(r.data['fecha_nacimiento'])


class UnirseQuinielaTests(TestCase):
    def test_unirse_devuelve_quiniela(self):
        cache.clear()
        creador = Usuario.objects.create_user('ana', 'ana@example.test', 'Strong-password-94!')
        otro = Usuario.objects.create_user('luis', 'luis@example.test', 'Strong-password-94!')
        torneo = Torneo.objects.create(nombre='Liga', temporada='2026', estado='ACTIVO')
        quiniela = Quiniela.objects.create(nombre='Amigos', torneo=torneo, creador=creador, codigo_unico='ABC123', max_participantes=3)
        Participante.objects.create(quiniela=quiniela, usuario=creador)
        client = APIClient()
        client.force_authenticate(otro)
        r = client.post('/api/quinielas/unirse/', {'codigo_unico': 'ABC123'})
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data['quiniela_id'], quiniela.pk)
        self.assertEqual(r.data['usuario'], otro.pk)  # campos previos conservados
        self.assertIn('puntos_totales', r.data)
        detalle = client.get(f'/api/quinielas/{quiniela.pk}/').data
        self.assertEqual(r.data['quiniela'], detalle)
