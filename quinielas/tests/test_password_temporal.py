from django.test import SimpleTestCase

from quinielas.accounts import ALFABETO_TEMPORAL, generar_password_temporal


class PasswordTemporalTests(SimpleTestCase):
    def test_diez_caracteres_con_letra_y_numero_sin_ambiguos(self):
        for _ in range(500):
            clave = generar_password_temporal()
            self.assertEqual(len(clave), 10)
            self.assertTrue(any(c.isalpha() for c in clave))
            self.assertTrue(any(c.isdigit() for c in clave))
            self.assertTrue(set(clave) <= set(ALFABETO_TEMPORAL))
        self.assertFalse(set('0O1lI') & set(ALFABETO_TEMPORAL))
