"""PRO tools share authentication and permissions with the existing mobile API."""
import csv
from datetime import timedelta, timezone as datetime_timezone
from io import StringIO

from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .errors import BusinessError
from .models import Participante, Partido, Pronostico
from .scoring import puntos_pronostico


def participaciones_pro(request):
    if not request.user.es_pro:
        raise BusinessError('PRO_REQUERIDO', 'Esta herramienta requiere el plan PRO.', 403)
    entries = Participante.objects.filter(usuario=request.user).exclude(
        quiniela__torneo__estado='BORRADOR').select_related('quiniela__torneo')
    torneo = request.query_params.get('torneo')
    if torneo is not None:
        try:
            torneo = int(torneo)
            if not 0 < torneo < 2**63:
                raise ValueError
        except ValueError:
            raise BusinessError('TORNEO_INVALIDO', 'Selecciona un torneo válido.')
        entries = entries.filter(quiniela__torneo_id=torneo)
        if not entries.exists():
            raise BusinessError('NO_ENCONTRADO', 'No participas en ese torneo.', 404)
    return entries


def private(response):
    response['Cache-Control'] = 'private, no-store'
    return response


def own_predictions(entries):
    return Pronostico.objects.filter(participante__in=entries).select_related(
        'partido__equipo_local', 'partido__equipo_visita', 'partido__fase',
        'partido__torneo', 'participante__quiniela').order_by('partido__fecha_hora', 'id')


def summary(predictions):
    counts = {'evaluados': 0, 'exactos': 0, 'resultado_y_diferencia': 0,
              'resultado_correcto': 0, 'sin_acierto': 0, 'puntos': 0}
    labels = {5: 'exactos', 4: 'resultado_y_diferencia', 3: 'resultado_correcto', 0: 'sin_acierto'}
    for prediction in predictions:
        match = prediction.partido
        if match.estado != 'FINALIZADO' or match.goles_local is None or match.goles_visita is None:
            continue
        points = puntos_pronostico(prediction)
        counts['evaluados'] += 1
        counts[labels[points]] += 1
        counts['puntos'] += points
    counts['porcentaje_acierto'] = round(100 * (counts['evaluados'] - counts['sin_acierto']) / counts['evaluados'], 1) if counts['evaluados'] else 0
    return counts


@api_view(['GET'])
def estadisticas(request):
    entries = list(participaciones_pro(request))
    predictions = list(own_predictions(entries))
    tournaments = {p.quiniela.torneo_id: p.quiniela.torneo for p in entries}
    return private(Response({
        'resumen': summary(predictions),
        'torneos': [{'id': t.pk, 'nombre': t.nombre, 'temporada': t.temporada,
                    **summary([p for p in predictions if p.partido.torneo_id == t.pk])}
                   for t in tournaments.values()],
        'unidad': 'pronostico_por_quiniela',
        'nota': 'Solo cuentan pronósticos propios en partidos finalizados con marcador. Un mismo partido en dos quinielas cuenta dos veces.',
    }))


def safe_cell(value):
    # CSV quoting alone does not prevent spreadsheet formula execution.
    value = str(value if value is not None else '')
    return "'" + value if value.lstrip().startswith(('=', '+', '-', '@')) or value.startswith(('\t', '\r', '\n')) else value


def csv_response(name, headings, rows):
    output = StringIO(newline='')
    output.write('\ufeff')
    writer = csv.writer(output)
    writer.writerow(headings)
    for row in rows:
        writer.writerow([safe_cell(cell) for cell in row])
    response = HttpResponse(output.getvalue(), content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="{name}.csv"'
    return private(response)


@api_view(['GET'])
def exportar_pronosticos(request):
    entries = participaciones_pro(request)
    return csv_response('streak-mis-pronosticos',
        ['Quiniela', 'Torneo', 'Fase', 'Fecha UTC', 'Local', 'Visitante', 'Mi local', 'Mi visitante', 'Estado', 'Puntos'],
        ([p.participante.quiniela.nombre, p.partido.torneo.nombre, p.partido.fase.nombre,
          p.partido.fecha_hora.isoformat(), p.partido.equipo_local.nombre, p.partido.equipo_visita.nombre,
          p.goles_local_pred, p.goles_visita_pred, p.partido.estado, puntos_pronostico(p)]
         for p in own_predictions(entries)))


@api_view(['GET'])
def exportar_tabla(request, pk):
    entry = get_object_or_404(participaciones_pro(request), quiniela_id=pk)
    players = entry.quiniela.participantes.select_related('usuario').order_by('-puntos_totales', 'fecha_union', 'id')
    rows, previous, rank = [], None, 0
    for index, player in enumerate(players, 1):
        if player.puntos_totales != previous:
            rank = index
        previous = player.puntos_totales
        rows.append([rank, player.usuario.username, player.puntos_totales])
    return csv_response('streak-clasificacion', ['Posición', 'Jugador', 'Puntos'], rows)


def ics_text(value):
    return str(value).replace('\\', '\\\\').replace('\r\n', '\n').replace('\r', '\n').replace('\n', '\\n').replace(';', '\\;').replace(',', '\\,')


def fold_line(line):
    chunks, current = [], ''
    for char in line:
        if len((current + char).encode('utf-8')) > 75:
            chunks.append(current)
            current = ' '
        current += char
    return '\r\n'.join(chunks + [current])


@api_view(['GET'])
def calendario(request):
    entries = participaciones_pro(request)
    now = timezone.now()
    matches = Partido.objects.filter(torneo_id__in=entries.values('quiniela__torneo_id'),
        torneo__estado='ACTIVO', estado='PROGRAMADO', fecha_hora__gt=now + timedelta(minutes=5)
    ).select_related('equipo_local', 'equipo_visita', 'torneo').order_by('fecha_hora', 'pk')
    stamp = lambda date: date.astimezone(datetime_timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    lines = ['BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//STREAK//Cierres//ES', 'CALSCALE:GREGORIAN']
    for match in matches:
        lines += ['BEGIN:VEVENT', f'UID:partido-{match.pk}-cierre@streak', f'DTSTAMP:{stamp(now)}',
            f'DTSTART:{stamp(match.cierre_pronosticos)}', f'DTEND:{stamp(match.fecha_hora)}',
            'SUMMARY:' + ics_text(f'Cierre STREAK: {match.equipo_local.nombre} vs {match.equipo_visita.nombre}'),
            'DESCRIPTION:' + ics_text(f'{match.torneo.nombre}. Guarda tu pronóstico antes del cierre. Reimporta el calendario si cambia el horario.'),
            'BEGIN:VALARM', 'TRIGGER:-PT30M', 'ACTION:DISPLAY', 'DESCRIPTION:Tu pronóstico STREAK cierra en 30 minutos',
            'END:VALARM', 'END:VEVENT']
    lines.append('END:VCALENDAR')
    response = HttpResponse('\r\n'.join(fold_line(line) for line in lines) + '\r\n', content_type='text/calendar; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="streak-cierres.ics"'
    return private(response)
