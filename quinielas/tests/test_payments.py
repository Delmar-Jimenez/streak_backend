import hashlib
import hmac
import json
import time
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

import stripe
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from quinielas.models import Usuario, Pago


@override_settings(STRIPE_SECRET_KEY='sk_test_fake', STRIPE_WEBHOOK_SECRET='whsec_fake')
class PaymentTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = Usuario.objects.create_user('ana', 'ana@example.test', 'Password-182!')
        self.client.force_authenticate(self.user)

    def order(self):
        return Pago.objects.create(usuario=self.user, monto='5.00', moneda='usd', referencia='pi_test', clave_idempotencia='test-key-123')

    def event(self, pago, event_type='payment_intent.succeeded', **changes):
        obj = {
            'id': 'pi_test', 'object': 'payment_intent', 'currency': 'usd', 'amount': 500,
            'amount_received': 500, 'status': 'succeeded',
            'metadata': {'pago_id': str(pago.pk), 'usuario_id': str(self.user.pk)}, **changes,
        }
        return {'id': 'evt_test', 'object': 'event', 'livemode': False, 'type': event_type, 'data': {'object': obj}}

    def webhook(self, event, valid=True):
        body = json.dumps(event)
        timestamp = int(time.time())
        digest = hmac.new(b'whsec_fake', f'{timestamp}.{body}'.encode(), hashlib.sha256).hexdigest()
        return self.client.post('/api/pro/webhook/', body, content_type='application/json',
            HTTP_STRIPE_SIGNATURE=f't={timestamp},v1={digest if valid else "invalid"}')

    @patch('quinielas.views_payments.stripe.StripeClient')
    def test_payment_intent_does_not_activate_and_retries_reuse_order(self, client):
        intent = SimpleNamespace(id='pi_test', client_secret='pi_test_secret_fake', status='requires_payment_method')
        client.return_value.v1.payment_intents.create.return_value = intent
        client.return_value.v1.payment_intents.retrieve.return_value = intent
        response = self.client.post('/api/pro/suscribir/', {}, HTTP_IDEMPOTENCY_KEY='test-key-123')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response['Cache-Control'], 'no-store')
        self.user.refresh_from_db()
        self.assertFalse(self.user.es_pro)
        self.assertEqual(Pago.objects.get().estado, 'PENDIENTE')
        response = self.client.post('/api/pro/suscribir/', {}, HTTP_IDEMPOTENCY_KEY='test-key-123')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Pago.objects.count(), 1)
        client.return_value.v1.payment_intents.create.assert_called_once()
        self.assertEqual(self.client.post('/api/pro/suscribir/', {}, HTTP_IDEMPOTENCY_KEY='another-key-123').status_code, 409)

    def test_missing_idempotency_key_rejected(self):
        self.assertEqual(self.client.post('/api/pro/suscribir/', {}).status_code, 400)

    @override_settings(STRIPE_SECRET_KEY='')
    def test_missing_configuration_returns_503(self):
        self.assertEqual(self.client.post('/api/pro/suscribir/', {}, HTTP_IDEMPOTENCY_KEY='test-key-123').status_code, 503)

    @override_settings(STRIPE_SECRET_KEY='sk_live_fake')
    @patch('quinielas.views_payments.stripe.StripeClient')
    def test_test_mode_never_uses_a_live_key(self, client):
        response = self.client.post('/api/pro/suscribir/', {}, HTTP_IDEMPOTENCY_KEY='test-key-123')
        self.assertEqual(response.status_code, 503)
        client.assert_not_called()
        self.assertFalse(Pago.objects.exists())

    def test_live_or_missing_event_mode_cannot_activate_in_test(self):
        pago = self.order()
        for mode in (True, None):
            event = self.event(pago)
            event['livemode'] = mode
            response = self.webhook(event)
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.data['error']['codigo'], 'MODO_PAGO_INVALIDO')
        self.user.refresh_from_db()
        pago.refresh_from_db()
        self.assertFalse(self.user.es_pro)
        self.assertEqual(pago.estado, 'PENDIENTE')

    @override_settings(STRIPE_SECRET_KEY='sk_live_fake', STRIPE_LIVE_MODE=True)
    def test_live_mode_rejects_test_events(self):
        pago = self.order()
        self.assertEqual(self.webhook(self.event(pago)).status_code, 400)
        self.user.refresh_from_db()
        self.assertFalse(self.user.es_pro)

    def test_signed_success_and_duplicate_delivery(self):
        pago = self.order()
        self.client.force_authenticate(None)
        for _ in range(2):
            response = self.webhook(self.event(pago))
            self.assertEqual(response.status_code, 200, response.data)
        pago.refresh_from_db()
        self.user.refresh_from_db()
        self.assertEqual(pago.estado, 'COMPLETADO')
        self.assertTrue(self.user.es_pro)
        self.assertEqual(Pago.objects.count(), 1)

    def test_bad_signature_and_wrong_amount_cannot_activate(self):
        pago = self.order()
        self.assertEqual(self.webhook(self.event(pago), valid=False).status_code, 400)
        self.assertEqual(self.webhook(self.event(pago, amount=1)).status_code, 400)
        self.assertEqual(self.webhook(self.event(pago, currency='eur')).status_code, 400)
        self.assertEqual(self.webhook(self.event(pago, amount_received=1)).status_code, 400)
        self.user.refresh_from_db()
        self.assertFalse(self.user.es_pro)

    def test_webhook_can_arrive_before_create_response(self):
        pago = self.order()
        pago.referencia = ''
        pago.save()
        self.assertEqual(self.webhook(self.event(pago)).status_code, 200)
        pago.refresh_from_db()
        self.assertEqual(pago.referencia, 'pi_test')
        self.assertEqual(pago.estado, 'COMPLETADO')

    def test_late_failure_does_not_revoke_success(self):
        pago = self.order()
        self.webhook(self.event(pago))
        self.webhook(self.event(pago, 'payment_intent.payment_failed'))
        self.user.refresh_from_db()
        pago.refresh_from_db()
        self.assertTrue(self.user.es_pro)
        self.assertEqual(pago.estado, 'COMPLETADO')

    @patch('quinielas.views_payments.stripe.StripeClient')
    def test_failed_intent_must_be_reused_until_canceled(self, client):
        pago = self.order()
        self.webhook(self.event(pago, 'payment_intent.payment_failed'))
        response = self.client.post('/api/pro/suscribir/', {}, HTTP_IDEMPOTENCY_KEY='new-key-123')
        self.assertEqual(response.status_code, 409)
        client.return_value.v1.payment_intents.create.assert_not_called()
        self.webhook(self.event(pago, 'payment_intent.canceled'))
        self.webhook(self.event(pago, 'payment_intent.payment_failed'))
        pago.refresh_from_db()
        self.assertEqual(pago.estado, 'CANCELADO')
        client.return_value.v1.payment_intents.create.return_value = SimpleNamespace(id='pi_new', client_secret='fake', status='requires_payment_method')
        response = self.client.post('/api/pro/suscribir/', {}, HTTP_IDEMPOTENCY_KEY='new-key-123')
        self.assertEqual(response.status_code, 200, response.data)

    def test_full_refund_revokes_and_late_success_cannot_reactivate(self):
        pago = self.order()
        self.webhook(self.event(pago))
        refund = self.event(pago, 'charge.refunded', id='ch_test', payment_intent='pi_test', refunded=True, amount_refunded=500)
        self.assertEqual(self.webhook(refund).status_code, 200)
        self.webhook(self.event(pago))
        self.user.refresh_from_db()
        pago.refresh_from_db()
        self.assertFalse(self.user.es_pro)
        self.assertEqual(pago.estado, 'REEMBOLSADO')

    def test_partial_refund_preserves_access(self):
        pago = self.order()
        self.webhook(self.event(pago))
        self.webhook(self.event(pago, 'charge.refunded', id='ch_test', payment_intent='pi_test', refunded=False, amount_refunded=100))
        self.user.refresh_from_db()
        self.assertTrue(self.user.es_pro)

    @patch('quinielas.views_payments.stripe.StripeClient')
    def test_stripe_error_is_sanitized_and_order_remains_retryable(self, client):
        client.return_value.v1.payment_intents.create.side_effect = stripe.APIConnectionError('secret provider details')
        response = self.client.post('/api/pro/suscribir/', {}, HTTP_IDEMPOTENCY_KEY='test-key-123')
        self.assertEqual(response.status_code, 502)
        self.assertNotIn('secret provider', str(response.data))
        self.assertEqual(Pago.objects.get().estado, 'PENDIENTE')

    @patch('quinielas.views_payments.stripe.StripeClient')
    def test_expired_unresolved_order_never_creates_a_second_charge(self, client):
        pago = self.order()
        Pago.objects.filter(pk=pago.pk).update(referencia='', fecha=timezone.now() - timedelta(days=2))
        response = self.client.post('/api/pro/suscribir/', {}, HTTP_IDEMPOTENCY_KEY='test-key-123')
        self.assertEqual(response.status_code, 409)
        client.return_value.v1.payment_intents.create.assert_not_called()

    def test_payment_history_is_private(self):
        self.order()
        other = Usuario.objects.create_user('other')
        Pago.objects.create(usuario=other, monto='5.00', referencia='pi_other')
        response = self.client.get('/api/pro/pagos/')
        self.assertEqual(len(response.data), 1)
        self.assertNotIn('client_secret', response.data[0])
