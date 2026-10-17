import json
from unittest.mock import patch

import requests
from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from quinielas.models import Usuario


@override_settings(
    EMAIL_BACKEND='anymail.backends.brevo.EmailBackend',
    ANYMAIL={'BREVO_API_KEY': 'brevo-test-key', 'REQUESTS_TIMEOUT': 10},
    DEFAULT_FROM_EMAIL='STREAK <streak@example.test>',
)
class BrevoRecoveryTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.user = Usuario.objects.create_user('ana', 'ana@example.test', 'Password-182!')

    def recover(self, email=None):
        return self.client.post('/api/auth/recuperar/', {'email': email or self.user.email})

    @patch('requests.sessions.Session.request')
    def test_https_delivery_and_temporary_password_can_be_changed(self, request):
        response = requests.Response()
        response.status_code = 201
        response._content = b'{"messageId":"<test@brevo.test>"}'
        request.return_value = response
        known = self.recover()
        self.assertEqual(known.status_code, 200)
        self.assertEqual(known.data, self.recover('unknown@example.test').data)
        request.assert_called_once()
        call = request.call_args.kwargs
        self.assertEqual(call['url'], 'https://api.brevo.com/v3/smtp/email')
        self.assertEqual(call['method'].upper(), 'POST')
        self.assertEqual(call['headers']['api-key'], 'brevo-test-key')
        self.assertEqual(call['timeout'], 10)
        payload = json.loads(call['data'])
        self.assertEqual(payload['to'], [{'email': self.user.email}])
        self.assertEqual(payload['sender'], {'name': 'STREAK', 'email': 'streak@example.test'})
        temporal = payload['textContent'].split('es: ')[1].split()[0]
        self.assertEqual(len(temporal), 10)
        self.assertIn(temporal, payload['htmlContent'])
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(temporal))
        self.assertTrue(self.user.pass_temporal_flag)
        self.assertIsNotNone(self.user.pass_temporal_expira)
        login = self.client.post('/api/auth/login/', {'username': 'ana', 'password': temporal})
        self.assertEqual(login.status_code, 200)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        changed = self.client.post('/api/auth/cambiar-password/', {
            'old_password': temporal, 'new_password': 'New-password-897!',
        })
        self.assertEqual(changed.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('New-password-897!'))
        self.assertFalse(self.user.pass_temporal_flag)
        self.assertIsNone(self.user.pass_temporal_expira)

    @patch('requests.sessions.Session.request')
    def test_missing_brevo_key_or_sender_is_unavailable_for_all_addresses(self, request):
        for values in ({'DEFAULT_FROM_EMAIL': ''}, {'ANYMAIL': {}},
                       {'ANYMAIL': {'RESEND_API_KEY': 'unrelated-key', 'BREVO_API_KEY': ''}}):
            with self.subTest(values=values), override_settings(**values):
                known = self.recover()
                self.assertEqual(known.status_code, 503)
                self.assertEqual(known.data['error']['codigo'], 'CORREO_NO_CONFIGURADO')
                self.assertEqual(known.data, self.recover('unknown@example.test').data)
        request.assert_not_called()

    @patch('requests.sessions.Session.request')
    def test_rejection_or_quota_limit_keeps_previous_password_and_hides_private_data(self, request):
        original = self.user.password
        for status in (401, 403, 429):
            with self.subTest(status=status):
                response = requests.Response()
                response.status_code = status
                response._content = b'{"code":"unauthorized","message":"private-provider-response"}'
                request.return_value = response
                with self.assertLogs('quinielas.views_auth', level='WARNING') as logs:
                    known = self.recover()
                self.assertEqual(known.status_code, 200)
                self.assertEqual(known.data, self.recover('unknown@example.test').data)
                for private in ('private-provider-response', self.user.email, 'brevo-test-key'):
                    self.assertNotIn(private, str(logs.output) + str(known.data))
                self.user.refresh_from_db()
                self.assertEqual(self.user.password, original)
                self.assertFalse(self.user.pass_temporal_flag)
                self.assertIsNone(self.user.pass_temporal_expira)

    @patch('requests.sessions.Session.request', side_effect=requests.Timeout('private-timeout'))
    def test_timeout_keeps_previous_password(self, request):
        original = self.user.password
        with self.assertLogs('quinielas.views_auth', level='WARNING') as logs:
            known = self.recover()
        self.assertEqual(known.status_code, 200)
        self.assertNotIn('private-timeout', str(logs.output))
        self.user.refresh_from_db()
        self.assertEqual(self.user.password, original)
        self.assertFalse(self.user.pass_temporal_flag)
