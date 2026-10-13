import json
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

import requests
from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from quinielas.models import Usuario


@override_settings(
    EMAIL_BACKEND='anymail.backends.resend.EmailBackend',
    ANYMAIL={'RESEND_API_KEY': 're_test_not_a_real_key', 'REQUESTS_TIMEOUT': 10},
    DEFAULT_FROM_EMAIL='STREAK <soporte@example.test>',
    PASSWORD_RESET_URL='streak://reset-password',
)
class ResendTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.user = Usuario.objects.create_user('ana', 'ana@example.test', 'Password-182!')

    def recover(self, email=None):
        return self.client.post('/api/auth/recuperar', {'email': email or self.user.email})

    @patch('requests.sessions.Session.request')
    def test_reset_uses_resend_https_and_link_can_reset_password(self, request):
        response = requests.Response()
        response.status_code = 200
        response._content = b'{"id":"email_test"}'
        request.return_value = response
        original = self.user.password
        with patch('builtins.print') as printed:
            known = self.recover()
            unknown = self.recover('unknown@example.test')
        printed.assert_not_called()
        self.assertEqual(known.status_code, 200)
        self.assertEqual(known.data, unknown.data)
        request.assert_called_once()
        call = request.call_args.kwargs
        self.assertEqual(call['url'], 'https://api.resend.com/emails')
        self.assertEqual(call['method'].upper(), 'POST')
        self.assertEqual(call['timeout'], 10)
        self.assertEqual(call['headers']['Authorization'], 'Bearer re_test_not_a_real_key')
        payload = json.loads(call['data'])
        self.assertEqual(payload['to'], [self.user.email])
        self.assertEqual(payload['from'], 'STREAK <soporte@example.test>')
        link = payload['text'].split()[-1]
        self.assertTrue(link.startswith('https://testserver/recuperar-acceso/#'))
        self.assertIn('href=', payload['html'])
        self.user.refresh_from_db()
        self.assertEqual(self.user.password, original)
        query = parse_qs(urlsplit(link).fragment)
        reset = {'uid': query['uid'][0], 'token': query['token'][0], 'new_password': 'New-password-897!'}
        self.assertEqual(self.client.post('/api/auth/restablecer', reset).status_code, 200)
        self.assertEqual(self.client.post('/api/auth/restablecer', reset).status_code, 400)

    @patch('requests.sessions.Session.request')
    def test_missing_configuration_is_unavailable_for_every_address(self, request):
        for setting in ({'DEFAULT_FROM_EMAIL': ''},
                        {'ANYMAIL': {'RESEND_API_KEY': ''}}):
            with self.subTest(setting=setting), override_settings(**setting):
                known = self.recover()
                unknown = self.recover('unknown@example.test')
                self.assertEqual(known.status_code, 503)
                self.assertEqual(known.data, unknown.data)
                self.assertEqual(known.data['error']['codigo'], 'CORREO_NO_CONFIGURADO')
        request.assert_not_called()

    @patch('requests.sessions.Session.request')
    def test_provider_rejection_does_not_leak_response_or_change_password(self, request):
        response = requests.Response()
        response.status_code = 403
        response._content = b'{"message":"private-provider-response"}'
        request.return_value = response
        original = self.user.password
        with self.assertLogs('quinielas.views_auth', level='WARNING') as logs:
            known = self.recover()
        unknown = self.recover('unknown@example.test')
        self.assertEqual(known.status_code, 200)
        self.assertEqual(known.data, unknown.data)
        self.assertNotIn('private-provider-response', str(logs.output) + str(known.data))
        self.assertNotIn(self.user.email, str(logs.output))
        self.assertNotIn('token=', str(logs.output))
        self.user.refresh_from_db()
        self.assertEqual(self.user.password, original)

    @patch('requests.sessions.Session.request', side_effect=requests.Timeout('private-timeout'))
    def test_timeout_returns_generic_response_without_logging_credentials(self, request):
        with self.assertLogs('quinielas.views_auth', level='WARNING') as logs:
            known = self.recover()
        self.assertEqual(known.status_code, 200)
        self.assertEqual(known.data, self.recover('unknown@example.test').data)
        self.assertNotIn('private-timeout', str(logs.output))
