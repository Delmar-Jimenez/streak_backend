from urllib.parse import urlencode, urlsplit, urlunsplit
from django.urls import reverse
from django.utils.html import format_html
from smtplib import SMTPException
import logging

from anymail.exceptions import AnymailError
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.db import transaction
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from rest_framework import generics, views
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .errors import BusinessError
from .permissions import IsPasswordNotTemporal
from .accounts import eliminar_cuenta
from .serializers_auth import (
    RegisterSerializer, RecuperarPasswordSerializer, CambiarPasswordSerializer,
    RestablecerPasswordSerializer, PerfilSerializer,
    SecureTokenRefreshSerializer,
)

Usuario = get_user_model()


class RegisterView(generics.CreateAPIView):
    permission_classes = (AllowAny,)
    authentication_classes = ()
    serializer_class = RegisterSerializer
    throttle_scope = 'auth'


class CustomTokenObtainPairView(TokenObtainPairView):
    throttle_scope = 'auth'


class CustomTokenRefreshView(TokenRefreshView):
    throttle_scope = 'auth'
    serializer_class = SecureTokenRefreshSerializer


class PerfilView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = PerfilSerializer
    http_method_names = ['get', 'put', 'patch', 'delete', 'head', 'options']
    throttle_scope = 'auth'

    def get_permissions(self):
        permissions = [IsAuthenticated()]
        if self.request.method not in ('GET', 'HEAD', 'OPTIONS', 'DELETE'):
            permissions.append(IsPasswordNotTemporal())
        return permissions

    def destroy(self, request, *args, **kwargs):
        if request.data.get('confirmar') is not True:
            raise BusinessError('CONFIRMACION_REQUERIDA', 'Confirma la eliminacion permanente de tu cuenta.')
        password = request.data.get('password')
        if not isinstance(password, str) or not password:
            raise BusinessError('PASSWORD_REQUERIDO', 'Ingresa tu contrasena actual.')
        eliminar_cuenta(request.user, password)
        return Response(status=204)

    def get_object(self):
        return self.request.user


class RecuperarPasswordView(views.APIView):
    permission_classes = (AllowAny,)
    authentication_classes = ()
    throttle_scope = 'password_reset'

    def post(self, request):
        serializer = RecuperarPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        resend_without_key = (
            settings.EMAIL_BACKEND == 'anymail.backends.resend.EmailBackend'
            and not settings.ANYMAIL.get('RESEND_API_KEY')
        )
        if not settings.DEFAULT_FROM_EMAIL or resend_without_key:
            raise BusinessError('CORREO_NO_CONFIGURADO', 'La recuperacion no esta disponible.', 503)
        # The response never reveals whether the address belongs to an account.
        for user in Usuario.objects.filter(email__iexact=serializer.validated_data['email'], is_active=True):
            if not user.has_usable_password():
                continue
            query = urlencode({
                'uid': urlsafe_base64_encode(force_bytes(user.pk)),
                'token': default_token_generator.make_token(user),
            })
            base = settings.PASSWORD_RESET_URL or request.build_absolute_uri(reverse('recuperar_acceso'))
            # Tokens in the fragment never reach HTTP access logs or Referer headers.
            # Older custom schemes are routed through the HTTPS page as well.
            if urlsplit(base).scheme != 'https':
                base = request.build_absolute_uri(reverse('recuperar_acceso'))
            parts = urlsplit(base)
            link = urlunsplit(('https', parts.netloc, parts.path, '', query))
            try:
                send_mail(
                    'Recuperacion de acceso STREAK',
                    f'Para cambiar tu contrasena abre este enlace (valido por una hora): {link}',
                    settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=False,
                    html_message=format_html('<p>Recuperacion de acceso STREAK</p><p><a href="{}">Restablecer contrasena</a></p><p>El enlace vence en una hora.</p>', link),
                )
            except (SMTPException, OSError, AnymailError):
                # Do not expose mailbox existence or log reset credentials on mail failure.
                logging.getLogger(__name__).warning('No se pudo entregar un correo de recuperacion.')
        return Response({'detail': 'Si el correo esta registrado, recibiras instrucciones para recuperar el acceso.'})


class RestablecerPasswordView(views.APIView):
    permission_classes = (AllowAny,)
    authentication_classes = ()
    throttle_scope = 'password_reset'

    @transaction.atomic
    def post(self, request):
        serializer = RestablecerPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            uid = urlsafe_base64_decode(data['uid']).decode()
            user = Usuario.objects.select_for_update().get(pk=uid, is_active=True)
        except (ValueError, TypeError, OverflowError, UnicodeDecodeError, Usuario.DoesNotExist):
            raise BusinessError('TOKEN_INVALIDO', 'El enlace es invalido o ha expirado.')
        if not default_token_generator.check_token(user, data['token']):
            raise BusinessError('TOKEN_INVALIDO', 'El enlace es invalido o ha expirado.')
        validate_password(data['new_password'], user)
        user.set_password(data['new_password'])
        user.pass_temporal_flag = False
        user.save(update_fields=['password', 'pass_temporal_flag'])
        return Response({'detail': 'Contrasena actualizada. Inicia sesion nuevamente.'})


class CambiarPasswordView(views.APIView):
    permission_classes = (IsAuthenticated,)
    throttle_scope = 'auth'

    @transaction.atomic
    def post(self, request):
        serializer = CambiarPasswordSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        user = Usuario.objects.select_for_update().get(pk=request.user.pk)
        if not user.check_password(serializer.validated_data['old_password']):
            raise ValidationError({'old_password': ['La contrasena actual no es correcta.']})
        user.set_password(serializer.validated_data['new_password'])
        user.pass_temporal_flag = False
        user.save(update_fields=['password', 'pass_temporal_flag'])
        return Response({'detail': 'Contrasena actualizada. Inicia sesion nuevamente.'})
