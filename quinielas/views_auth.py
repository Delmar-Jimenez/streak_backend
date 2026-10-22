from django.utils.html import format_html
from datetime import timedelta
from smtplib import SMTPException
import logging

from anymail.exceptions import AnymailError
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone
from django.utils.http import urlsafe_base64_decode
from rest_framework import generics, views
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .errors import BusinessError
from .permissions import IsPasswordNotTemporal
from .accounts import eliminar_cuenta, generar_password_temporal
from .serializers_auth import (
    RegisterSerializer, RecuperarPasswordSerializer, CambiarPasswordSerializer,
    RestablecerPasswordSerializer, PerfilSerializer,
    SecureTokenRefreshSerializer, LoginSerializer,
)

Usuario = get_user_model()


class RegisterView(generics.CreateAPIView):
    permission_classes = (AllowAny,)
    authentication_classes = ()
    serializer_class = RegisterSerializer
    throttle_scope = 'auth'


class CustomTokenObtainPairView(TokenObtainPairView):
    throttle_scope = 'auth'
    serializer_class = LoginSerializer


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
        provider_key = {
            'anymail.backends.resend.EmailBackend': 'RESEND_API_KEY',
            'anymail.backends.brevo.EmailBackend': 'BREVO_API_KEY',
        }.get(settings.EMAIL_BACKEND)
        missing_key = provider_key and not settings.ANYMAIL.get(provider_key)
        if not settings.DEFAULT_FROM_EMAIL or missing_key:
            raise BusinessError('CORREO_NO_CONFIGURADO', 'La recuperacion no esta disponible.', 503)
        # RN-06: se genera una contrasena temporal de 10 caracteres, se envia al correo registrado,
        # se marca pass_temporal_flag y vence a las 24 horas. La respuesta no revela si el correo existe.
        for user in Usuario.objects.filter(email__iexact=serializer.validated_data['email'], is_active=True):
            if not user.has_usable_password():
                continue
            temporal = generar_password_temporal()
            try:
                # Si el correo no sale, se revierte el cambio: la contrasena anterior sigue sirviendo.
                with transaction.atomic():
                    user = Usuario.objects.select_for_update().get(pk=user.pk)
                    user.set_password(temporal)
                    user.pass_temporal_flag = True
                    user.pass_temporal_expira = timezone.now() + timedelta(hours=24)
                    user.save(update_fields=['password', 'pass_temporal_flag', 'pass_temporal_expira'])
                    send_mail(
                        'Tu contrasena temporal de STREAK',
                        f'Tu contrasena temporal es: {temporal}\n'
                        'Vence en 24 horas. Al iniciar sesion, la app te pedira crear una contrasena nueva.\n'
                        'Si no solicitaste este cambio, entra con esta contrasena y cambiala.',
                        settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=False,
                        html_message=format_html(
                            '<p>Tu contrasena temporal de STREAK es: <strong>{}</strong></p>'
                            '<p>Vence en 24 horas. Al iniciar sesion, la app te pedira crear una contrasena nueva.</p>'
                            '<p>Si no solicitaste este cambio, entra con esta contrasena y cambiala.</p>', temporal),
                    )
            except (SMTPException, OSError, AnymailError):
                # No se registran el correo ni la contrasena temporal (RN-02).
                logging.getLogger(__name__).warning('No se pudo entregar un correo de recuperacion.')
        return Response({'detail': 'Si el correo esta registrado, recibiras una contrasena temporal.'})


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
        user.pass_temporal_expira = None
        user.save(update_fields=['password', 'pass_temporal_flag', 'pass_temporal_expira'])
        return Response({'detail': 'Contrasena actualizada. Inicia sesion nuevamente.'})


class CambiarPasswordView(views.APIView):
    permission_classes = (IsAuthenticated,)
    throttle_scope = 'auth'

    @transaction.atomic
    def post(self, request):
        serializer = CambiarPasswordSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        user = Usuario.objects.select_for_update().get(pk=request.user.pk)
        if user.pass_temporal_vencida():
            raise BusinessError('PASSWORD_TEMPORAL_VENCIDA', 'Tu contrasena temporal vencio. Solicita una nueva desde Recuperar contrasena.')
        if not user.check_password(serializer.validated_data['old_password']):
            raise ValidationError({'old_password': ['La contrasena actual no es correcta.']})
        user.set_password(serializer.validated_data['new_password'])
        user.pass_temporal_flag = False
        user.pass_temporal_expira = None
        user.save(update_fields=['password', 'pass_temporal_flag', 'pass_temporal_expira'])
        return Response({'detail': 'Contrasena actualizada. Inicia sesion nuevamente.'})
