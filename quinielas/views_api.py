from django.db import transaction
from django.db.models import Q
from django.db.models.functions import Trim, Upper
from django.conf import settings
from datetime import timedelta
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .errors import BusinessError
from .plans import FEATURES, capacidades
from .models import Torneo, Partido, Quiniela, Participante, Pronostico, Pago, Equipo, Pais
from .serializers import (
    TorneoSerializer, PartidoSerializer, QuinielaSerializer, PronosticoSerializer,
    EquipoSerializer, FaseSerializer, ParticipanteSerializer, PagoSerializer, UnirseSerializer, PaisSerializer,
)


def torneos_visibles():
    return Torneo.objects.exclude(estado=Torneo.Estado.BORRADOR).select_related('pais')


def filtrar_pais(request, queryset):
    pais = request.query_params.get('pais')
    if pais is None:
        return queryset
    try:
        pais_id = int(pais)
        if not 0 < pais_id < 2**63:
            raise ValueError
    except ValueError:
        raise BusinessError('PAIS_INVALIDO', 'El país debe ser un identificador válido.')
    get_object_or_404(Pais, pk=pais_id)
    return queryset.filter(pais_id=pais_id)


@api_view(['GET'])
@permission_classes([AllowAny])
def pais_list(request):
    return Response(PaisSerializer(Pais.objects.all(), many=True).data)


@api_view(['GET'])
@permission_classes([AllowAny])
def equipo_list(request):
    equipos = filtrar_pais(request, Equipo.objects.select_related('pais'))
    return Response(EquipoSerializer(equipos, many=True, context={'request': request}).data)


def membresia(user, pk):
    return get_object_or_404(Participante.objects.select_related('quiniela'), quiniela_id=pk, usuario=user)


def filtrar_partidos(request, torneo):
    partidos = torneo.partidos.select_related('equipo_local__pais', 'equipo_visita__pais', 'fase').prefetch_related(
        'equipo_local__inscripciones_torneos', 'equipo_visita__inscripciones_torneos').order_by('fecha_hora', 'id')
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
    grupo = request.query_params.get('grupo')
    if grupo is not None:
        if not grupo.strip() or len(grupo) > 50:
            raise BusinessError('GRUPO_INVALIDO', 'Selecciona un grupo válido.')
        inscritos = torneo.inscripciones_equipos.annotate(grupo_normalizado=Upper(Trim('grupo'))).filter(
            grupo_normalizado=grupo.strip().upper()).values('equipo_id')
        if not inscritos.exists():
            raise BusinessError('GRUPO_INVALIDO', 'Este grupo no pertenece al torneo.')
        partidos = partidos.filter(fase__tipo='GRUPOS', equipo_local_id__in=inscritos, equipo_visita_id__in=inscritos)
    equipo = request.query_params.get('equipo')
    if equipo is not None:
        try:
            equipo_id = int(equipo)
            if not 0 < equipo_id < 2**63:
                raise ValueError
        except ValueError:
            raise BusinessError('EQUIPO_INVALIDO', 'Selecciona un equipo válido.')
        get_object_or_404(torneo.equipos, pk=equipo_id)
        partidos = partidos.filter(Q(equipo_local_id=equipo_id) | Q(equipo_visita_id=equipo_id))
    return partidos


def pronostico_visible(pronostico, partido, es_propio, ahora):
    if pronostico is None or (not es_propio and partido.fecha_hora > ahora):
        return None
    return PronosticoSerializer(pronostico).data


def estado_pronostico(pronostico, partido, es_propio, ahora):
    # Do not reveal whether a rival has entered a prediction before kickoff.
    if not es_propio and partido.fecha_hora > ahora:
        return 'OCULTO'
    return 'VISIBLE' if pronostico else 'NO_REGISTRADO'


@api_view(['GET'])
@permission_classes([AllowAny])
def torneo_list(request):
    tournaments = filtrar_pais(request, torneos_visibles())
    for field, choices in [('formato', Torneo.Formato.values), ('estado', ['ACTIVO', 'FINALIZADO'])]:
        value = request.query_params.get(field)
        if value is not None:
            if value not in choices:
                raise BusinessError('FILTRO_INVALIDO', f'El filtro {field} no es válido.')
            tournaments = tournaments.filter(**{field: value})
    if 'temporada' in request.query_params:
        tournaments = tournaments.filter(temporada=request.query_params['temporada'])
    if 'buscar' in request.query_params:
        tournaments = tournaments.filter(nombre__icontains=request.query_params['buscar'].strip())
    return Response(TorneoSerializer(tournaments.order_by('id'), many=True).data)


@api_view(['GET'])
@permission_classes([AllowAny])
def torneo_filtros(request, pk):
    torneo = get_object_or_404(torneos_visibles(), pk=pk)
    groups = torneo.inscripciones_equipos.exclude(grupo__isnull=True).exclude(grupo='').values_list('grupo', flat=True)
    return Response({'torneo': torneo.pk, 'formato': torneo.formato,
        'fases': FaseSerializer(torneo.fases.all(), many=True).data,
        'grupos': sorted({g.strip().upper() for g in groups if g.strip()}),
        'equipos': list(torneo.equipos.order_by('nombre', 'id').values('id', 'nombre')),
        'estados': [{'valor': value, 'nombre': str(label)} for value, label in Partido.Estado.choices]})


@api_view(['GET'])
@permission_classes([AllowAny])
def torneo_detail(request, pk):
    return Response(TorneoSerializer(get_object_or_404(torneos_visibles(), pk=pk)).data)


@api_view(['GET'])
@permission_classes([AllowAny])
def torneo_equipos(request, pk):
    torneo = get_object_or_404(torneos_visibles(), pk=pk)
    equipos = torneo.equipos.select_related('pais').prefetch_related('inscripciones_torneos').order_by('nombre', 'id')
    return Response(EquipoSerializer(equipos, many=True, context={'request': request, 'torneo_id': torneo.pk}).data)


@api_view(['GET'])
@permission_classes([AllowAny])
def torneo_fases(request, pk):
    torneo = get_object_or_404(torneos_visibles(), pk=pk)
    return Response(FaseSerializer(torneo.fases.order_by('orden', 'id'), many=True).data)


@api_view(['GET'])
@permission_classes([AllowAny])
def torneo_partidos(request, pk):
    torneo = get_object_or_404(torneos_visibles(), pk=pk)
    return Response(PartidoSerializer(filtrar_partidos(request, torneo), many=True, context={'request': request}).data)


@api_view(['GET'])
@permission_classes([AllowAny])
def partido_detail(request, pk):
    partido = get_object_or_404(Partido.objects.exclude(torneo__estado=Torneo.Estado.BORRADOR), pk=pk)
    return Response(PartidoSerializer(partido, context={'request': request}).data)


@api_view(['POST'])
@transaction.atomic
def quiniela_create(request):
    serializer = QuinielaSerializer(data=request.data, context={'request': request})
    serializer.is_valid(raise_exception=True)
    quiniela = serializer.save(creador=request.user)
    Participante.objects.create(quiniela=quiniela, usuario=request.user)
    return Response(serializer.data, status=201)


@api_view(['GET'])
def quinielas_mias(request):
    quinielas = Quiniela.objects.filter(
        Q(participantes__usuario=request.user) | Q(creador=request.user),
    ).distinct().select_related('torneo').prefetch_related('participantes').order_by('id')
    return Response(QuinielaSerializer(quinielas, many=True, context={'request': request}).data)


@api_view(['GET'])
def quinielas_historial(request):
    quinielas = Quiniela.objects.filter(
        Q(participantes__usuario=request.user) | Q(creador=request.user),
        torneo__estado=Torneo.Estado.FINALIZADO,
    ).distinct().select_related('torneo').prefetch_related('participantes').order_by('-id')
    return Response(QuinielaSerializer(quinielas, many=True, context={'request': request}).data)


@api_view(['GET'])
def quiniela_partidos(request, pk):
    miembro = membresia(request.user, pk)
    partidos = filtrar_partidos(request, miembro.quiniela.torneo)
    propios = {p.partido_id: p for p in miembro.pronosticos.all()}
    data = PartidoSerializer(partidos, many=True, context={'request': request}).data
    for row in data:
        pred = propios.get(row['id'])
        row['mi_pronostico'] = PronosticoSerializer(pred).data if pred else None
        row['estado_pronostico'] = 'VISIBLE' if pred else 'NO_REGISTRADO'
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
        row = ParticipanteSerializer(participante, context={'request': request}).data
        row['estado_pronostico'] = estado_pronostico(predicciones.get(participante.pk), partido, participante.pk == miembro.pk, ahora)
        pred = pronostico_visible(predicciones.get(participante.pk), partido, participante.pk == miembro.pk, ahora)
        row['pronostico'] = pred
        row['puntos_obtenidos'] = pred['puntos_obtenidos'] if pred else 0
        data.append(row)
    return Response({'partido': PartidoSerializer(partido, context={'request': request}).data, 'participantes': data})


@api_view(['GET'])
def quiniela_usuario_detalle(request, pk, uid):
    miembro = membresia(request.user, pk)
    participante = get_object_or_404(Participante.objects.select_related('usuario'), quiniela_id=pk, usuario_id=uid)
    predicciones = {p.partido_id: p for p in participante.pronosticos.all()}
    data = []
    ahora = timezone.now()
    for partido in filtrar_partidos(request, miembro.quiniela.torneo):
        row = PartidoSerializer(partido, context={'request': request}).data
        row['estado_pronostico'] = estado_pronostico(predicciones.get(partido.pk), partido, participante.pk == miembro.pk, ahora)
        pred = pronostico_visible(predicciones.get(partido.pk), partido, participante.pk == miembro.pk, ahora)
        row['pronostico'] = pred
        row['puntos_obtenidos'] = pred['puntos_obtenidos'] if pred else 0
        data.append(row)
    return Response({'participante': ParticipanteSerializer(participante, context={'request': request}).data, 'partidos': data})


@api_view(['GET'])
def quiniela_detail(request, pk):
    return Response(QuinielaSerializer(membresia(request.user, pk).quiniela, context={'request': request}).data)


def validar_ingreso(quiniela, user):
    if quiniela.torneo.estado != Torneo.Estado.ACTIVO:
        raise BusinessError('TORNEO_NO_ACTIVO', 'El torneo no permite nuevas inscripciones.')
    if Participante.objects.filter(quiniela=quiniela, usuario=user).exists():
        raise BusinessError('YA_PARTICIPA', 'Ya eres participante de esta quiniela.')
    if quiniela.participantes.count() >= quiniela.max_participantes:
        raise BusinessError('QUINIELA_LLENA', 'La quiniela esta llena.')
    cerrados = quiniela.torneo.partidos.exclude(estado__in=['CANCELADO', 'SUSPENDIDO']).filter(
        Q(fecha_hora__lte=timezone.now() + timedelta(minutes=5)) | ~Q(estado='PROGRAMADO'),
    ).count()
    return {
        'quiniela_id': quiniela.pk, 'nombre': quiniela.nombre, 'torneo_nombre': quiniela.torneo.nombre,
        'cantidad_inscritos': quiniela.participantes.count(), 'max_participantes': quiniela.max_participantes,
        'ingreso_tardio': cerrados > 0, 'requiere_confirmacion': cerrados > 0,
        'partidos_cerrados': cerrados, 'penalizacion_puntos': 0,
        'advertencia': 'No podras pronosticar partidos cuyo plazo ya cerro.' if cerrados else '',
    }


@api_view(['POST'])
def quiniela_validar_codigo(request):
    serializer = UnirseSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    quiniela = get_object_or_404(Quiniela.objects.select_related('torneo'), codigo_unico=serializer.validated_data['codigo_unico'])
    return Response(validar_ingreso(quiniela, request.user))


@api_view(['POST'])
@transaction.atomic
def quiniela_unirse(request):
    serializer = UnirseSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    quiniela = get_object_or_404(
        Quiniela.objects.select_for_update(), codigo_unico=serializer.validated_data['codigo_unico'],
    )
    preview = validar_ingreso(quiniela, request.user)
    if preview['requiere_confirmacion'] and not serializer.validated_data['aceptar_ingreso_tardio']:
        return Response({'error': {'codigo': 'CONFIRMACION_INGRESO_TARDIO',
            'mensaje': preview['advertencia'], 'detalles': preview}}, status=409)
    participante = Participante.objects.create(quiniela=quiniela, usuario=request.user)
    data = ParticipanteSerializer(participante, context={'request': request}).data
    data['quiniela_id'] = quiniela.pk
    data['quiniela'] = QuinielaSerializer(quiniela, context={'request': request}).data
    return Response(data, status=201)


@api_view(['GET'])
def quiniela_participantes(request, pk):
    miembro = membresia(request.user, pk)
    participantes = miembro.quiniela.participantes.select_related('usuario').order_by('fecha_union', 'id')
    return Response(ParticipanteSerializer(participantes, many=True, context={'request': request}).data)


@api_view(['GET'])
def quiniela_tabla(request, pk):
    miembro = membresia(request.user, pk)
    participantes = miembro.quiniela.participantes.select_related('usuario').order_by('-puntos_totales', 'fecha_union', 'id')
    data = ParticipanteSerializer(participantes, many=True, context={'request': request}).data
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
    if not partido.pronosticos_abiertos:
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
    response = Response({'es_pro': request.user.es_pro, 'capacidades': capacidades(request.user), 'plan': {
        'monto_centavos': settings.STRIPE_PRO_AMOUNT, 'moneda': settings.STRIPE_CURRENCY,
        'tipo': 'PAGO_UNICO', 'modo_prueba': not settings.STRIPE_LIVE_MODE,
        'max_participantes': 100, 'max_participantes_gratis': 50,
        'beneficios': FEATURES,
    }})
    response['Cache-Control'] = 'private, no-store'
    return response


@api_view(['GET'])
def pro_pagos(request):
    return Response(PagoSerializer(request.user.pagos.order_by('-fecha', '-id'), many=True).data)
