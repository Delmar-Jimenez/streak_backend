"""Same-origin website: Django sessions for browsers, existing JWT API for mobile."""
from django.contrib import admin
from django.contrib.auth import login, logout
from django.middleware.csrf import get_token
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from django.views.decorators.http import require_safe
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from .permissions import IsPasswordNotTemporal
from .serializers_auth import LoginSerializer, PerfilSerializer


@require_safe
@never_cache
@ensure_csrf_cookie
def portal(request):
    response = render(request, 'quinielas/portal.html')
    response['Content-Security-Policy'] = (
        "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
        "connect-src 'self'; font-src 'self'; object-src 'none'; base-uri 'none'; "
        "frame-ancestors 'none'; form-action 'self'"
    )
    response['Referrer-Policy'] = 'same-origin'
    return response


def session_data(request):
    user = request.user
    return {
        'usuario': PerfilSerializer(user, context={'request': request}).data if user.is_authenticated else None,
        'administrador': bool(user.is_authenticated and user.is_active and user.is_staff),
        'csrf': get_token(request),
    }


@method_decorator(never_cache, name='dispatch')
class SesionView(APIView):
    authentication_classes = (SessionAuthentication,)
    permission_classes = (AllowAny,)

    def get(self, request):
        return Response(session_data(request))


@method_decorator(csrf_protect, name='dispatch')
class EntrarView(SesionView):
    throttle_scope = 'auth'
    http_method_names = ['post', 'options']

    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        # Validate the same credentials/expiry as mobile; never expose JWTs to browser storage.
        login(request._request, serializer.user)
        request.user = serializer.user
        return Response(session_data(request))


@method_decorator(csrf_protect, name='dispatch')
class SalirView(SesionView):
    http_method_names = ['post', 'options']

    def post(self, request):
        logout(request._request)
        return Response({'detail': 'Sesión cerrada.', 'csrf': get_token(request)})


@method_decorator(never_cache, name='dispatch')
class AdministracionView(APIView):
    authentication_classes = (SessionAuthentication,)
    permission_classes = (IsAdminUser, IsPasswordNotTemporal)

    def get(self, request):
        # Django builds these links from each ModelAdmin's existing permission checks.
        apps = admin.site.get_app_list(request._request)
        return Response({'modulos': [
            {'nombre': str(model['name']), 'url': model.get('admin_url'),
             'crear_url': model.get('add_url'), 'modelo': model['object_name']}
            for app in apps for model in app['models']
        ]})
