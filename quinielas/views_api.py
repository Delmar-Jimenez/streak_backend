import os
import stripe
from dotenv import load_dotenv
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from .models import Torneo, Partido, Quiniela, Participante, Pronostico, Pago
from .serializers import TorneoSerializer, PartidoSerializer, QuinielaSerializer, PronosticoSerializer

load_dotenv()

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

@api_view(['GET'])
def torneo_list(request):
    torneos = Torneo.objects.all()
    serializer = TorneoSerializer(torneos, many=True)
    return Response(serializer.data)

@api_view(['GET'])
def torneo_partidos(request, pk):
    torneo = get_object_or_404(Torneo, pk=pk)
    partidos = torneo.partidos.all()
    
    estado = request.query_params.get('estado')
    if estado in dict(Partido.Estado.choices).keys():
        partidos = partidos.filter(estado=estado)
        
    serializer = PartidoSerializer(partidos, many=True)
    return Response(serializer.data)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def quiniela_create(request):
    serializer = QuinielaSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save(creador=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def quiniela_unirse(request):
    codigo = request.data.get('codigo_unico')
    if not codigo:
        return Response({'error': 'codigo_unico es requerido'}, status=status.HTTP_400_BAD_REQUEST)
        
    quiniela = get_object_or_404(Quiniela, codigo_unico=codigo)
    
    if Participante.objects.filter(quiniela=quiniela, usuario=request.user).exists():
        return Response({'error': 'Ya eres participante de esta quiniela'}, status=status.HTTP_400_BAD_REQUEST)
        
    if quiniela.participantes.count() >= quiniela.max_participantes:
        return Response({'error': 'La quiniela está llena'}, status=status.HTTP_400_BAD_REQUEST)
        
    Participante.objects.create(quiniela=quiniela, usuario=request.user)
    return Response({'mensaje': 'Te has unido exitosamente a la quiniela'}, status=status.HTTP_201_CREATED)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def quiniela_pronosticos(request, pk):
    quiniela = get_object_or_404(Quiniela, pk=pk)
    
    try:
        participante = Participante.objects.get(quiniela=quiniela, usuario=request.user)
    except Participante.DoesNotExist:
        return Response({'error': 'No eres participante de esta quiniela'}, status=status.HTTP_403_FORBIDDEN)
        
    partido_id = request.data.get('partido')
    if not partido_id:
        return Response({'error': 'partido es requerido'}, status=status.HTTP_400_BAD_REQUEST)
        
    partido = get_object_or_404(Partido, pk=partido_id, torneo=quiniela.torneo)
    
    if partido.estado != Partido.Estado.PROGRAMADO:
        return Response({'error': 'El partido ya no está programado, no se pueden hacer pronósticos.'}, status=status.HTTP_400_BAD_REQUEST)
        
    pronostico = Pronostico.objects.filter(participante=participante, partido=partido).first()
    
    serializer = PronosticoSerializer(pronostico, data=request.data, partial=bool(pronostico))
    if serializer.is_valid():
        serializer.save(participante=participante)
        return Response(serializer.data, status=status.HTTP_201_CREATED if not pronostico else status.HTTP_200_OK)
        
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def pro_estado(request):
    return Response({'es_pro': request.user.es_pro}, status=status.HTTP_200_OK)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def pro_suscribir(request):
    token = request.data.get('token_pago', 'tok_visa')
    
    try:
        charge = stripe.Charge.create(
            amount=500,
            currency="usd",
            source=token,
            description=f"Suscripción PRO STREAK - {request.user.username}"
        )
        
        request.user.es_pro = True
        request.user.save()
        
        Pago.objects.create(
            usuario=request.user,
            monto=5.00,
            estado='APROBADO',
            referencia=charge.id
        )
        
        return Response({
            'mensaje': '¡Pago exitoso! Ahora eres usuario PRO.', 
            'es_pro': True,
            'referencia': charge.id
        }, status=status.HTTP_200_OK)
        
    except stripe.error.StripeError as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)