import secrets
import string

from django.db import transaction
from django.contrib.auth import get_user_model
from django.contrib.admin.models import LogEntry

from .errors import BusinessError
from .models import Pago


# Sin caracteres que se confunden al leerlos (0/O, 1/l/I).
ALFABETO_TEMPORAL = ''.join(c for c in string.ascii_letters + string.digits if c not in '0O1lI')


def generar_password_temporal(longitud=10):
    """Contrasena temporal aleatoria (RN-06) con al menos una letra y un numero (RN-03)."""
    while True:
        clave = ''.join(secrets.choice(ALFABETO_TEMPORAL) for _ in range(longitud))
        if any(c.isalpha() for c in clave) and any(c.isdigit() for c in clave):
            return clave


@transaction.atomic
def eliminar_cuenta(user, password):
    user = get_user_model().objects.select_for_update().get(pk=user.pk)
    if not user.check_password(password):
        raise BusinessError('CREDENCIALES_INVALIDAS', 'La contrasena no es correcta.', 400)
    # Keep groups belonging to other people and financial reconciliation records.
    # Removing the FK prevents subsequent webhook events from granting access.
    LogEntry.objects.filter(user_id=user.pk).delete()
    # Clear user identifiers in audit entries written by other administrators.
    LogEntry.objects.filter(content_type__app_label='quinielas',
        content_type__model='usuario', object_id=str(user.pk)).delete()
    Pago.objects.filter(usuario=user).update(clave_idempotencia=None)
    user.delete()
