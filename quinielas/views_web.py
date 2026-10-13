from io import BytesIO
from types import SimpleNamespace

from django.conf import settings
from django.contrib.auth import authenticate
from django.http import FileResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_http_methods, require_safe
from rest_framework.throttling import ScopedRateThrottle

from .accounts import eliminar_cuenta
from .errors import BusinessError
from .models import ImagenArchivo


def private_page(response):
    response['Referrer-Policy'] = 'no-referrer'
    response['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; frame-ancestors 'none'; form-action 'self'; base-uri 'none'"
    response['X-Robots-Tag'] = 'noindex, nofollow'
    return response


@require_safe
@never_cache
def recuperar_acceso(request):
    app_url = settings.PASSWORD_RESET_APP_URL
    if not app_url.startswith('streak://'):
        app_url = ''
    return private_page(render(request, 'quinielas/recuperar.html', {'app_url': app_url}))


@require_http_methods(['GET', 'POST'])
@sensitive_post_parameters('password')
@never_cache
def eliminar_cuenta_web(request):
    context = {}
    status = 200
    if request.method == 'POST':
        throttle = ScopedRateThrottle()
        if not throttle.allow_request(request, SimpleNamespace(throttle_scope='auth')):
            context['error'] = 'Demasiados intentos. Espera un momento antes de intentar nuevamente.'
            status = 429
        elif request.POST.get('confirmar') != 'si':
            context['error'] = 'Confirma que deseas eliminar tu cuenta permanentemente.'
            status = 400
        else:
            password = request.POST.get('password', '')
            user = authenticate(request, username=request.POST.get('username', ''), password=password)
            if user is None:
                context['error'] = 'No se pudo verificar el usuario y la contrasena.'
                status = 400
            else:
                try:
                    eliminar_cuenta(user, password)
                    context['eliminada'] = True
                except BusinessError as exc:
                    context['error'] = str(exc.detail)
                    status = exc.status_code
    return private_page(render(request, 'quinielas/eliminar.html', context, status=status))


@require_safe
def media_imagen(request, nombre):
    image = get_object_or_404(ImagenArchivo, nombre=nombre)
    response = FileResponse(BytesIO(bytes(image.contenido)), content_type=image.tipo)
    response['Cache-Control'] = 'no-store' if nombre.startswith('perfiles/') else 'public, max-age=3600'
    response['X-Content-Type-Options'] = 'nosniff'
    return response
