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
    solo_tiempo_reglamentario = serializers.SerializerMethodField()

    def get_solo_tiempo_reglamentario(self, obj):
        return True
    class Meta:
        model = Fase
        fields = '__all__'


class PartidoSerializer(serializers.ModelSerializer):
    equipo_local_detalle = EquipoSerializer(source='equipo_local', read_only=True)
    equipo_visita_detalle = EquipoSerializer(source='equipo_visita', read_only=True)
    fase_tipo = serializers.CharField(source='fase.tipo', read_only=True)
    cierre_pronosticos = serializers.DateTimeField(read_only=True)
    pronosticos_abiertos = serializers.BooleanField(read_only=True)
    class Meta:
        model = Partido
        fields = '__all__'


class QuinielaSerializer(serializers.ModelSerializer):
    max_participantes = serializers.IntegerField(min_value=2, max_value=100)
    torneo_nombre = serializers.CharField(source='torneo.nombre', read_only=True)
    cantidad_inscritos = serializers.SerializerMethodField()
    mis_puntos = serializers.SerializerMethodField()
    mi_posicion = serializers.SerializerMethodField()

    def get_cantidad_inscritos(self, obj):
        return len(obj.participantes.all())

    def _miembro(self, obj):
        request = self.context.get('request')
        if not request:
            return None
        return next((p for p in obj.participantes.all() if p.usuario_id == request.user.pk), None)

    def get_mis_puntos(self, obj):
        miembro = self._miembro(obj)
        return miembro.puntos_totales if miembro else None

    def get_mi_posicion(self, obj):
        miembro = self._miembro(obj)
        return 1 + sum(p.puntos_totales > miembro.puntos_totales for p in obj.participantes.all()) if miembro else None

    def validate_max_participantes(self, value):
        limite = 100 if self.context['request'].user.es_pro else 50
        if value > limite:
            raise serializers.ValidationError(f'El limite de tu plan es de {limite} participantes.')
        return value

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
            codigo = ''.join(secrets.choice('ABCDEFGHJKMNPQRSTUVWXYZ23456789') for _ in range(6))
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
    foto = serializers.ImageField(source='usuario.foto', read_only=True)
    es_pro = serializers.BooleanField(source='usuario.es_pro', read_only=True)

    class Meta:
        model = Participante
        fields = ('id', 'usuario', 'username', 'foto', 'es_pro', 'puntos_totales', 'fecha_union')


class PagoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Pago
        fields = ('id', 'monto', 'moneda', 'estado', 'referencia', 'fecha')


class UnirseSerializer(serializers.Serializer):
    codigo = serializers.CharField(min_length=6, max_length=6, required=False)
    codigo_unico = serializers.CharField(min_length=6, max_length=6, required=False)
    aceptar_ingreso_tardio = serializers.BooleanField(default=False)

    def validate(self, attrs):
        codigo = attrs.get('codigo', '').upper()
        legacy = attrs.get('codigo_unico', '').upper()
        if not codigo and not legacy:
            raise serializers.ValidationError({'codigo': 'Este campo es requerido.'})
        if codigo and legacy and codigo != legacy:
            raise serializers.ValidationError('codigo y codigo_unico deben coincidir.')
        return {'codigo_unico': codigo or legacy, 'aceptar_ingreso_tardio': attrs['aceptar_ingreso_tardio']}
