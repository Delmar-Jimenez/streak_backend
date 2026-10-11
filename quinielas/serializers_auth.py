from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.db import IntegrityError, transaction
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.utils import get_md5_hash_password

Usuario = get_user_model()


class RegisterSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(required=True)
    password = serializers.CharField(write_only=True, trim_whitespace=False)

    class Meta:
        model = Usuario
        fields = ('id', 'username', 'email', 'password', 'telefono', 'first_name', 'last_name')
        read_only_fields = ('id',)

    def validate_email(self, value):
        value = value.strip().lower()
        if Usuario.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError('Este correo ya esta registrado.')
        return value

    def validate(self, attrs):
        validate_password(attrs['password'], Usuario(**{k: v for k, v in attrs.items() if k != 'password'}))
        return attrs

    def create(self, validated_data):
        try:
            with transaction.atomic():
                return Usuario.objects.create_user(**validated_data)
        except IntegrityError:
            raise serializers.ValidationError('El usuario o correo ya esta registrado.')


class PerfilSerializer(serializers.ModelSerializer):
    class Meta:
        model = Usuario
        fields = ('id', 'username', 'email', 'first_name', 'last_name', 'telefono', 'foto', 'es_pro', 'pass_temporal_flag')
        read_only_fields = ('id', 'username', 'email', 'es_pro', 'pass_temporal_flag')


class RecuperarPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()


class CambiarPasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(trim_whitespace=False)
    new_password = serializers.CharField(trim_whitespace=False)

    def validate_new_password(self, value):
        validate_password(value, self.context['request'].user)
        return value


class RestablecerPasswordSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(trim_whitespace=False)


class SecureTokenRefreshSerializer(TokenRefreshSerializer):
    def validate(self, attrs):
        token = self.token_class(attrs['refresh'])
        user = Usuario.objects.filter(pk=token.get(api_settings.USER_ID_CLAIM)).first()
        if user is None or not user.is_active:
            raise AuthenticationFailed('La sesion ya no es valida.')
        if token.get(api_settings.REVOKE_TOKEN_CLAIM) != get_md5_hash_password(user.password):
            raise AuthenticationFailed('La contrasena cambio. Inicia sesion nuevamente.')
        return super().validate(attrs)
