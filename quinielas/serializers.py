from rest_framework import serializers
from .models import Torneo, Quiniela, Partido, Pronostico, Participante
import random

class TorneoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Torneo
        fields = '__all__'

class PartidoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Partido
        fields = '__all__'

class QuinielaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Quiniela
        fields = '__all__'
        read_only_fields = ('codigo_unico', 'creador')

    def create(self, validated_data):
      
        caracteres_validos = "ABCDEFGHJKMNPQRSTUVWXYZ123456789"
        while True:
            codigo = ''.join(random.choices(caracteres_validos, k=6))
            if not Quiniela.objects.filter(codigo_unico=codigo).exists():
                break
        validated_data['codigo_unico'] = codigo
        return super().create(validated_data)

class PronosticoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Pronostico
        fields = '__all__'
        read_only_fields = ('participante', 'puntos_obtenidos')
