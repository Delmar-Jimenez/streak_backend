from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .errors import BusinessError
from .models import Torneo, Partido, Quiniela, Participante, Pronostico, Pago
from .serializers import (
    TorneoSerializer, PartidoSerializer, QuinielaSerializer, PronosticoSerializer,
    EquipoSerializer, FaseSerializer, ParticipanteSerializer, PagoSerializer, UnirseSerializer,
)


def torneos_visibles():
    return Torneo.objects.exclude(estado=Torneo.Estado.BORRADOR)


def membresia(user, pk):
    return get_object_or_404(Participante.objects.select_related('quiniela'), quiniela_id=pk, usuario=user)


def filtrar_partidos(request, torneo):
    partidos = torneo.partidos.order_by('fecha_hora', 'id')
    estado = request.query_params.get('estado')
    if estado is not None:
        if estado not in Partido.Estado.values:
            raise BusinessError('ESTADO_INVALIDO', 'El estado del partido no es valido.')
        partidos = partidos.filter(estado=estado)
    fase = request.query_params.get('fase')
    if fase is not None:
        try:
            fase_id = int(fase)
            if not 0 < fase_id < 2**63:
                raise ValueError
        except ValueError:
            raise BusinessError('FASE_INVALIDA', 'La fase debe ser un identificador valido.')
        get_object_or_404(torneo.fases, pk=fase_id)
        partidos = partidos.filter(fase_id=fase_id)
    return partidos


def pronostico_visible(pronostico, partido, es_propio, ahora):
    if pronostico is None or (not es_propio and partido.fecha_hora > ahora):
        return None
    return PronosticoSerializer(pronostico).data


@api_view(['GET'])
@permission_classes([AllowAny])
def torneo_list(request):
    return Response(TorneoSerializer(torneos_visibles().order_by('id'), many=True).data)


@api_view(['GET'])
@permission_classes([AllowAny])
def torneo_detail(request, pk):
    return Response(TorneoSerializer(get_object_or_404(torneos_visibles(), pk=pk)).data)


@api_view(['GET'])
@permission_classes([AllowAny])
def torneo_equipos(request, pk):
    torneo = get_object_or_404(torneos_visibles(), pk=pk)
    return Response(EquipoSerializer(torneo.equipos.order_by('nombre', 'id'), many=True, context={'request': request}).data)


@api_view(['GET'])
@permission_classes([AllowAny])
def torneo_fases(request, pk):
    torneo = get_object_or_404(torneos_visibles(), pk=pk)
    return Response(FaseSerializer(torneo.fases.order_by('orden', 'id'), many=True).data)


@api_view(['GET'])
@permission_classes([AllowAny])
def torneo_partidos(request, pk):
    torneo = get_object_or_404(torneos_visibles(), pk=pk)
    return Response(PartidoSerializer(filtrar_partidos(request, torneo), many=True).data)


@api_view(['GET'])
@permission_classes([AllowAny])
def partido_detail(request, pk):
    partido = get_object_or_404(Partido.objects.exclude(torneo__estado=Torneo.Estado.BORRADOR), pk=pk)
    return Response(PartidoSerializer(partido).data)


@api_view(['POST'])
@transaction.atomic
def quiniela_create(request):
    serializer = QuinielaSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    quiniela = serializer.save(creador=request.user)
    Participante.objects.create(quiniela=quiniela, usuario=request.user)
    return Response(serializer.data, status=201)


@api_view(['GET'])
def quinielas_mias(request):
    quinielas = Quiniela.objects.filter(
        Q(participantes__usuario=request.user) | Q(creador=request.user),
    ).distinct().order_by('id')
    return Response(QuinielaSerializer(quinielas, many=True).data)


@api_view(['GET'])
def quinielas_historial(request):
    quinielas = Quiniela.objects.filter(
        Q(participantes__usuario=request.user) | Q(creador=request.user),
        torneo__estado=Torneo.Estado.FINALIZADO,
    ).distinct().order_by('-id')
    return Response(QuinielaSerializer(quinielas, many=True).data)


@api_view(['GET'])
def quiniela_partidos(request, pk):
    miembro = membresia(request.user, pk)
    partidos = filtrar_partidos(request, miembro.quiniela.torneo)
    propios = {p.partido_id: p for p in miembro.pronosticos.all()}
    data = PartidoSerializer(partidos, many=True).data
    for row in data:
        pred = propios.get(row['id'])
        row['mi_pronostico'] = PronosticoSerializer(pred).data if pred else None
        row['mis_puntos'] = pred.puntos_obtenidos if pred else 0
    return Response(data)


@api_view(['GET'])
def quiniela_partido_detalle(request, pk, pid):
    miembro = membresia(request.user, pk)
    partido = get_object_or_404(Partido, pk=pid, torneo=miembro.quiniela.torneo)
    predicciones = {p.participante_id: p for p in Pronostico.objects.filter(partido=partido, participante__quiniela_id=pk)}
    data = []
    ahora = timezone.now()
    for participante in miembro.quiniela.participantes.select_related('usuario').order_by('id'):
        row = ParticipanteSerializer(participante).data
        pred = pronostico_visible(predicciones.get(participante.pk), partido, participante.pk == miembro.pk, ahora)
        row['pronostico'] = pred
        row['puntos_obtenidos'] = pred['puntos_obtenidos'] if pred else 0
        data.append(row)
    return Response({'partido': PartidoSerializer(partido).data, 'participantes': data})


@api_view(['GET'])
def quiniela_usuario_detalle(request, pk, uid):
    miembro = membresia(request.user, pk)
    participante = get_object_or_404(Participante.objects.select_related('usuario'), quiniela_id=pk, usuario_id=uid)
    predicciones = {p.partido_id: p for p in participante.pronosticos.all()}
    data = []
    ahora = timezone.now()
    for partido in filtrar_partidos(request, miembro.quiniela.torneo):
        row = PartidoSerializer(partido).data
        pred = pronostico_visible(predicciones.get(partido.pk), partido, participante.pk == miembro.pk, ahora)
        row['pronostico'] = pred
        row['puntos_obtenidos'] = pred['puntos_obtenidos'] if pred else 0
        data.append(row)
    return Response({'participante': ParticipanteSerializer(participante).data, 'partidos': data})


@api_view(['GET'])
def quiniela_detail(request, pk):
    return Response(QuinielaSerializer(membresia(request.user, pk).quiniela).data)


@api_view(['POST'])
@transaction.atomic
def quiniela_unirse(request):
    serializer = UnirseSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    quiniela = get_object_or_404(
        Quiniela.objects.select_for_update(), codigo_unico=serializer.validated_data['codigo_unico'],
    )
    if quiniela.torneo.estado != Torneo.Estado.ACTIVO:
        raise BusinessError('TORNEO_NO_ACTIVO', 'El torneo no permite nuevas inscripciones.')
    if Participante.objects.filter(quiniela=quiniela, usuario=request.user).exists():
        raise BusinessError('YA_PARTICIPA', 'Ya eres participante de esta quiniela.')
    if quiniela.participantes.count() >= quiniela.max_participantes:
        raise BusinessError('QUINIELA_LLENA', 'La quiniela esta llena.')
    participante = Participante.objects.create(quiniela=quiniela, usuario=request.user)
    return Response(ParticipanteSerializer(participante).data, status=201)


@api_view(['GET'])
def quiniela_participantes(request, pk):
    miembro = membresia(request.user, pk)
    participantes = miembro.quiniela.participantes.select_related('usuario').order_by('fecha_union', 'id')
    return Response(ParticipanteSerializer(participantes, many=True).data)


@api_view(['GET'])
def quiniela_tabla(request, pk):
    miembro = membresia(request.user, pk)
    participantes = miembro.quiniela.participantes.select_related('usuario').order_by('-puntos_totales', 'fecha_union', 'id')
    data = ParticipanteSerializer(participantes, many=True).data
    previous = None
    rank = 0
    for index, row in enumerate(data, start=1):
        if row['puntos_totales'] != previous:
            rank = index
        row['posicion'] = rank
        previous = row['puntos_totales']
    return Response(data)


@api_view(['GET', 'POST'])
@transaction.atomic
def quiniela_pronosticos(request, pk):
    participante = membresia(request.user, pk)
    if request.method == 'GET':
        return Response(PronosticoSerializer(participante.pronosticos.order_by('partido__fecha_hora', 'id'), many=True).data)
    # Validate foreign keys and scores before using client input in ORM lookups.
    payload = PronosticoSerializer(data=request.data)
    payload.is_valid(raise_exception=True)
    partido = get_object_or_404(
        Partido.objects.select_for_update(), pk=payload.validated_data['partido'].pk,
        torneo=participante.quiniela.torneo,
    )
    if participante.quiniela.torneo.estado != Torneo.Estado.ACTIVO:
        raise BusinessError('TORNEO_NO_ACTIVO', 'El torneo no admite pronosticos.')
    if partido.estado != Partido.Estado.PROGRAMADO or partido.fecha_hora <= timezone.now():
        raise BusinessError('PRONOSTICOS_CERRADOS', 'El plazo para pronosticar este partido ha terminado.')
    # Lock before changing predictions, matching the scoring service lock order.
    Participante.objects.select_for_update().get(pk=participante.pk)
    pronostico, created = Pronostico.objects.update_or_create(
        participante=participante, partido=partido,
        defaults={
            'goles_local_pred': payload.validated_data['goles_local_pred'],
            'goles_visita_pred': payload.validated_data['goles_visita_pred'],
        },
    )
    pronostico.refresh_from_db()
    return Response(PronosticoSerializer(pronostico).data, status=201 if created else 200)


@api_view(['GET'])
def quiniela_rival_pronosticos(request, pk, participante_id):
    miembro = membresia(request.user, pk)
    rival = get_object_or_404(Participante, pk=participante_id, quiniela=miembro.quiniela)
    pronosticos = rival.pronosticos.order_by('partido__fecha_hora', 'id')
    if rival.pk != miembro.pk:
        pronosticos = pronosticos.filter(partido__fecha_hora__lte=timezone.now())
    return Response(PronosticoSerializer(pronosticos, many=True).data)


@api_view(['GET'])
def pro_estado(request):
    return Response({'es_pro': request.user.es_pro})


@api_view(['GET'])
def pro_pagos(request):
    return Response(PagoSerializer(request.user.pagos.order_by('-fecha', '-id'), many=True).data)
