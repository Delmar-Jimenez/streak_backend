from datetime import timedelta
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import patch

import stripe
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.utils import timezone
from PIL import Image

from quinielas.demo import cargar_demo
from quinielas.models import Fase, ImagenArchivo, Pago, Participante, Pronostico, Torneo, Usuario
from . import test_api, test_payments


class MobileAuditTests(TestCase):
    setUp = test_api.ApiTests.setUp
    pronosticar = test_api.ApiTests.pronosticar

    def test_limits_and_unambiguous_codes(self):
        for limit, expected in [(1, 400), (2, 201), (50, 201), (51, 400), (100, 400)]:
            response = self.client.post('/api/quinielas/', {'nombre': 'Limites', 'torneo': self.torneo.pk, 'max_participantes': limit})
            self.assertEqual(response.status_code, expected, response.data)
            if expected == 201:
                self.assertFalse(set(response.data['codigo_unico']) & set('01ILO'))
        self.user.es_pro = True
        self.user.save()
        for limit, expected in [(100, 201), (101, 400)]:
            self.assertEqual(self.client.post('/api/quinielas/', {'nombre': 'Pro', 'torneo': self.torneo.pk, 'max_participantes': limit}).status_code, expected)

    def test_preview_does_not_enroll_and_late_join_requires_consent(self):
        self.partido.fecha_hora = timezone.now() + timedelta(minutes=4)
        self.partido.save()
        self.client.force_authenticate(self.outsider)
        data = {'codigo': self.quiniela.codigo_unico}
        preview = self.client.post('/api/quinielas/validar-codigo/', data).json()
        self.assertTrue(preview['ingreso_tardio'])
        self.assertEqual(preview['partidos_cerrados'], 1)
        self.assertEqual(preview['penalizacion_puntos'], 0)
        self.assertFalse(self.outsider.participaciones.exists())
        self.assertEqual(self.client.post('/api/quinielas/unirse/', data).status_code, 409)
        self.assertFalse(self.outsider.participaciones.exists())
        response = self.client.post('/api/quinielas/unirse/', {**data, 'aceptar_ingreso_tardio': True}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['puntos_totales'], 0)

    def test_late_join_only_scores_open_matches_and_excludes_suspended_games(self):
        now = timezone.now()
        self.partido.fecha_hora = now - timedelta(hours=2)
        self.partido.estado = 'FINALIZADO'
        self.partido.goles_local = 2
        self.partido.goles_visita = 1
        self.partido.save()
        en_juego = type(self.partido).objects.create(
            torneo=self.torneo, fase=self.fase, equipo_local=self.local, equipo_visita=self.visita,
            fecha_hora=now + timedelta(hours=1), estado='EN_JUEGO',
        )
        suspendido = type(self.partido).objects.create(
            torneo=self.torneo, fase=self.fase, equipo_local=self.visita, equipo_visita=self.local,
            fecha_hora=now - timedelta(hours=1), estado='SUSPENDIDO',
        )
        cancelado = type(self.partido).objects.create(
            torneo=self.torneo, fase=self.fase, equipo_local=self.local, equipo_visita=self.visita,
            fecha_hora=now - timedelta(hours=1), estado='CANCELADO',
        )
        self.client.force_authenticate(self.outsider)
        data = {'codigo': self.quiniela.codigo_unico}
        preview = self.client.post('/api/quinielas/validar-codigo/', data).json()
        self.assertEqual(preview['partidos_cerrados'], 2)
        self.assertEqual(preview['penalizacion_puntos'], 0)
        joined = self.client.post('/api/quinielas/unirse/', {
            **data, 'aceptar_ingreso_tardio': True,
        }, format='json')
        self.assertEqual(joined.status_code, 201, joined.data)
        participant = Participante.objects.get(pk=joined.data['id'])

        for closed_match in (self.partido, en_juego, suspendido, cancelado):
            response = self.client.post(
                f'/api/quinielas/{self.quiniela.pk}/pronosticos/',
                {'partido': closed_match.pk, 'goles_local_pred': 2, 'goles_visita_pred': 1},
                format='json',
            )
            self.assertEqual(response.status_code, 400)
        self.assertFalse(participant.pronosticos.exists())
        participant.refresh_from_db()
        self.assertEqual(participant.puntos_totales, 0)

        proximo = type(self.partido).objects.create(
            torneo=self.torneo, fase=self.fase, equipo_local=self.local, equipo_visita=self.visita,
            fecha_hora=now + timedelta(hours=3), estado='PROGRAMADO',
        )
        response = self.client.post(
            f'/api/quinielas/{self.quiniela.pk}/pronosticos/',
            {'partido': proximo.pk, 'goles_local_pred': 2, 'goles_visita_pred': 1},
            format='json',
        )
        self.assertEqual(response.status_code, 201, response.data)
        proximo.goles_local = 2
        proximo.goles_visita = 1
        proximo.estado = 'FINALIZADO'
        proximo.save()
        participant.refresh_from_db()
        self.assertEqual(participant.puntos_totales, 5)
        self.assertEqual(participant.pronosticos.count(), 1)

    def test_exact_five_minute_deadline(self):
        now = timezone.now()
        self.partido.fecha_hora = now + timedelta(minutes=5)
        self.partido.save()
        with patch('django.utils.timezone.now', return_value=now - timedelta(microseconds=1)):
            self.assertEqual(self.pronosticar().status_code, 201)
        with patch('django.utils.timezone.now', return_value=now):
            self.assertEqual(self.pronosticar().status_code, 400)
            self.assertFalse(self.partido.pronosticos_abiertos)

    def test_prediction_states_and_nested_teams(self):
        endpoint = f'/api/quinielas/{self.quiniela.pk}/partidos/{self.partido.pk}/detalle/'
        response = self.client.get(endpoint).json()
        self.assertEqual(response['partido']['equipo_local_detalle']['nombre'], 'Local')
        self.assertIn('escudo', response['partido']['equipo_local_detalle'])
        self.assertEqual([p['estado_pronostico'] for p in response['participantes']], ['NO_REGISTRADO', 'OCULTO'])
        self.pronosticar()
        response = self.client.get(endpoint).json()
        self.assertEqual(response['participantes'][0]['estado_pronostico'], 'VISIBLE')
        self.partido.fecha_hora = timezone.now() - timedelta(seconds=1)
        self.partido.save()
        self.assertEqual(self.client.get(endpoint).json()['participantes'][1]['estado_pronostico'], 'NO_REGISTRADO')

    def test_history_and_plan_are_self_contained(self):
        self.torneo.estado = 'FINALIZADO'
        self.torneo.save()
        row = self.client.get('/api/quinielas/historial/').json()[0]
        self.assertEqual((row['torneo_nombre'], row['cantidad_inscritos'], row['mis_puntos'], row['mi_posicion']), ('Liga', 2, 0, 1))
        row = self.client.get(f'/api/quinielas/{self.quiniela.pk}/tabla/').json()[0]
        self.assertIn('foto', row)
        self.assertIn('es_pro', row)
        plan = self.client.get('/api/pro/estado/').json()['plan']
        self.assertEqual(plan['max_participantes'], 100)
        self.assertIn('moneda', plan)
        self.assertIn('monto_centavos', plan)

    def test_elimination_scoring_ignores_extra_time_and_penalties(self):
        self.pronosticar(1, 1)
        self.fase.tipo = 'ELIMINATORIA'
        self.fase.save()
        self.partido.goles_local = self.partido.goles_visita = 1
        self.partido.goles_local_prorroga = 2
        self.partido.goles_visita_prorroga = 1
        self.partido.penales_local = 5
        self.partido.penales_visita = 4
        self.partido.estado = 'FINALIZADO'
        self.partido.save()
        self.miembro.refresh_from_db()
        self.assertEqual(self.miembro.puntos_totales, 5)
        self.fase.tipo = 'texto libre'
        with self.assertRaises(ValidationError):
            self.fase.save()

    def upload_photo(self):
        image = BytesIO()
        Image.new('RGB', (20, 20), 'green').save(image, format='PNG')
        return self.client.patch('/api/usuarios/me/', {'foto': SimpleUploadedFile('avatar.png', image.getvalue(), 'image/png')}, format='multipart')

    def test_photo_served_without_debug_and_replaced_without_orphans(self):
        response = self.upload_photo()
        self.assertEqual(response.status_code, 200, response.data)
        url = response.data['foto']
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'image/webp')
        self.assertEqual(response['Cache-Control'], 'no-store')
        image = Image.open(BytesIO(b''.join(response.streaming_content)))
        self.assertEqual(image.size, (20, 20))
        self.upload_photo()
        self.assertEqual(ImagenArchivo.objects.count(), 1)
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_delete_requires_password_and_preserves_shared_group_and_payment(self):
        self.upload_photo()
        self.pronosticar()
        pago = Pago.objects.create(usuario=self.user, monto='5.00', referencia='pi_retained', clave_idempotencia='old-device-key')
        self.assertEqual(self.client.delete('/api/usuarios/me/', {}, format='json').status_code, 400)
        self.assertEqual(self.client.delete('/api/usuarios/me/', {'confirmar': True, 'password': 'wrong'}, format='json').status_code, 400)
        self.assertTrue(Usuario.objects.filter(pk=self.user.pk).exists())
        response = self.client.delete('/api/usuarios/me/', {'confirmar': True, 'password': 'Strong-password-94!'}, format='json')
        self.assertEqual(response.status_code, 204, response.data)
        self.quiniela.refresh_from_db()
        pago.refresh_from_db()
        self.assertIsNone(self.quiniela.creador_id)
        self.assertIsNone(pago.usuario_id)
        self.assertIsNone(pago.clave_idempotencia)
        self.assertTrue(Participante.objects.filter(pk=self.otro.pk).exists())
        self.assertFalse(Pronostico.objects.exists())
        self.assertFalse(ImagenArchivo.objects.exists())

    def test_legacy_shared_image_survives_other_accounts_deletion(self):
        self.upload_photo()
        self.user.refresh_from_db()
        self.rival.foto = self.user.foto.name
        self.rival.save()
        self.user.delete()
        self.assertTrue(ImagenArchivo.objects.filter(pk=self.rival.foto.name).exists())
        self.rival.delete()
        self.assertFalse(ImagenArchivo.objects.exists())

    def test_public_account_pages_and_csrf(self):
        client = Client(enforce_csrf_checks=True)
        for url in ['/eliminar-cuenta/', '/recuperar-acceso/']:
            response = client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response['Referrer-Policy'], 'no-referrer')
        data = {'username': self.user.username, 'password': 'Strong-password-94!', 'confirmar': 'si'}
        self.assertEqual(client.post('/eliminar-cuenta/', data).status_code, 403)
        client.get('/eliminar-cuenta/')
        self.assertEqual(client.post('/eliminar-cuenta/', data, HTTP_X_CSRFTOKEN=client.cookies['csrftoken'].value).status_code, 200)
        self.assertFalse(Usuario.objects.filter(pk=self.user.pk).exists())


@override_settings(STRIPE_SECRET_KEY='sk_test_fake', STRIPE_WEBHOOK_SECRET='whsec_fake')
class PendingPaymentTests(TestCase):
    setUp = test_payments.PaymentTests.setUp
    order = test_payments.PaymentTests.order

    def intent(self, pago, status='requires_payment_method'):
        return stripe.PaymentIntent.construct_from({
            'id': 'pi_test', 'client_secret': 'pi_test_secret_fake', 'status': status,
            'amount': 500, 'amount_received': 500 if status == 'succeeded' else 0,
            'currency': 'usd', 'livemode': False,
            'metadata': {'pago_id': str(pago.pk), 'usuario_id': str(self.user.pk)},
        }, 'sk_test_fake')

    @patch('quinielas.views_payments.stripe.StripeClient')
    def test_recover_lost_key_without_creating_duplicate(self, factory):
        pago = self.order()
        api = factory.return_value.v1.payment_intents
        api.retrieve.return_value = self.intent(pago)
        response = self.client.get('/api/pro/pago-pendiente/')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['clave_idempotencia'], pago.clave_idempotencia)
        self.assertEqual(response['Cache-Control'], 'no-store')
        api.create.assert_not_called()
        other = Usuario.objects.create_user('other')
        self.client.force_authenticate(other)
        self.assertEqual(self.client.get('/api/pro/pago-pendiente/').data, {'pago': None})
        self.assertEqual(self.client.post(f'/api/pro/pagos/{pago.pk}/cancelar/').status_code, 404)

    @patch('quinielas.views_payments.stripe.StripeClient')
    def test_cancel_then_retry_is_idempotent(self, factory):
        pago = self.order()
        api = factory.return_value.v1.payment_intents
        api.retrieve.side_effect = [self.intent(pago), self.intent(pago, 'canceled')]
        for _ in range(2):
            response = self.client.post(f'/api/pro/pagos/{pago.pk}/cancelar/')
            self.assertEqual(response.status_code, 200, response.data)
            self.assertEqual(response.data['estado'], 'CANCELADO')
        api.cancel.assert_called_once()

    @patch('quinielas.views_payments.stripe.StripeClient')
    def test_settled_order_reconciles_without_cancellation(self, factory):
        pago = self.order()
        api = factory.return_value.v1.payment_intents
        api.retrieve.return_value = self.intent(pago, 'succeeded')
        self.assertEqual(self.client.post(f'/api/pro/pagos/{pago.pk}/cancelar/').status_code, 409)
        api.cancel.assert_not_called()
        self.user.refresh_from_db()
        self.assertTrue(self.user.es_pro)

    @patch('quinielas.views_payments.stripe.StripeClient')
    def test_old_unknown_order_is_not_recreated(self, factory):
        pago = self.order()
        Pago.objects.filter(pk=pago.pk).update(referencia='', fecha=timezone.now() - timedelta(days=2))
        api = factory.return_value.v1.payment_intents
        api.search.return_value = SimpleNamespace(data=[], has_more=False)
        self.assertEqual(self.client.get('/api/pro/pago-pendiente/').status_code, 409)
        api.create.assert_not_called()


class DemoTests(TestCase):
    def test_demo_is_repeatable_and_has_no_default_passwords(self):
        first = cargar_demo()
        second = cargar_demo()
        self.assertEqual(first, second)
        self.assertEqual(Torneo.objects.filter(estado='ACTIVO').count(), 2)
        self.assertEqual(Torneo.objects.filter(estado='FINALIZADO').count(), 1)
        self.assertEqual(Usuario.objects.filter(es_demo=True).count(), 4)
        self.assertEqual(Usuario.objects.filter(es_demo=True, es_pro=True).count(), 1)
        self.assertTrue(all(not u.has_usable_password() for u in Usuario.objects.all()))
        self.assertEqual(ImagenArchivo.objects.count(), 24)

    def test_demo_admin_requires_superuser(self):
        user = Usuario.objects.create_user('staff', is_staff=True)
        self.client.force_login(user)
        self.assertEqual(self.client.post('/admin/quinielas/torneo/demo/', {'confirmar': 'si'}).status_code, 403)

