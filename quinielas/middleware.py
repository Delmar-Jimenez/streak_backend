from zoneinfo import ZoneInfo

from django.conf import settings
from django.utils import timezone


class ZonaHorariaAdminMiddleware:
    """Muestra y captura las fechas del admin en la hora local del administrador.

    La base de datos y la API siguen en UTC (RN-70); solo cambia la zona horaria activa
    mientras se atiende una petición de /admin/.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.zona = ZoneInfo(settings.ADMIN_TIME_ZONE)

    def __call__(self, request):
        if request.path.startswith('/admin/'):
            timezone.activate(self.zona)
            try:
                return self.get_response(request)
            finally:
                timezone.deactivate()
        return self.get_response(request)
