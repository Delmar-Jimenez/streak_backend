import secrets

from django.db import IntegrityError, transaction
from rest_framework import serializers
from .models import Torneo, Equipo, Fase, Quiniela, Partido, Pronostico, Participante, Pago


class TorneoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Torneo
        fields = '__all__'


class EquipoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Equipo
        fields = '__all__'


class FaseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Fase
        fields = '__all__'


class PartidoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Partido
        fields = '__all__'


class QuinielaSerializer(serializers.ModelSerializer):
    max_participantes = serializers.IntegerField(min_value=1)

    class Meta:
        model = Quiniela
        fields = '__all__'
        read_only_fields = ('codigo_unico', 'creador')

    def validate_torneo(self, value):
        if value.estado != Torneo.Estado.ACTIVO:
            raise serializers.ValidationError('El torneo debe estar activo.')
        return value

    def create(self, validated_data):
        for attempt in range(10):
            codigo = ''.join(secrets.choice('ABCDEFGHJKMNPQRSTUVWXYZ123456789') for _ in range(6))
            try:
                with transaction.atomic():
                    return Quiniela.objects.create(codigo_unico=codigo, **validated_data)
            except IntegrityError:
                if not Quiniela.objects.filter(codigo_unico=codigo).exists():
                    raise
        raise serializers.ValidationError('No se pudo generar un codigo. Intenta nuevamente.')


class PronosticoSerializer(serializers.ModelSerializer):
    goles_local_pred = serializers.IntegerField(min_value=0)
    goles_visita_pred = serializers.IntegerField(min_value=0)

    class Meta:
        model = Pronostico
        fields = '__all__'
        read_only_fields = ('participante', 'puntos_obtenidos')


class ParticipanteSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='usuario.username', read_only=True)

    class Meta:
        model = Participante
        fields = ('id', 'usuario', 'username', 'puntos_totales', 'fecha_union')


class PagoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Pago
        fields = ('id', 'monto', 'moneda', 'estado', 'referencia', 'fecha')


class UnirseSerializer(serializers.Serializer):
    codigo = serializers.CharField(min_length=6, max_length=6, required=False)
    codigo_unico = serializers.CharField(min_length=6, max_length=6, required=False)

    def validate(self, attrs):
        codigo = attrs.get('codigo', '').upper()
        legacy = attrs.get('codigo_unico', '').upper()
        if not codigo and not legacy:
            raise serializers.ValidationError({'codigo': 'Este campo es requerido.'})
        if codigo and legacy and codigo != legacy:
            raise serializers.ValidationError('codigo y codigo_unico deben coincidir.')
        return {'codigo_unico': codigo or legacy}
