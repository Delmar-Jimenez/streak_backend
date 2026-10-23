from datetime import timedelta
from io import BytesIO

from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone
from PIL import Image, ImageDraw

from .models import Usuario, Torneo, Equipo, Fase, Partido, Quiniela, Participante, Pronostico


def escudo_demo(index):
    colors = ['#19715c', '#ba3b4b', '#286ac3', '#6b50a1', '#b26717', '#1d8090', '#484e59', '#a53879']
    image = Image.new('RGB', (160, 180), '#f4f6f5')
    draw = ImageDraw.Draw(image)
    draw.polygon([(16, 16), (144, 16), (136, 120), (80, 166), (24, 120)], fill=colors[index % 8])
    draw.ellipse((54, 44, 106, 96), fill='white')
    draw.text((68, 115), f'{index + 1:02}', fill='white')
    buffer = BytesIO()
    image.save(buffer, format='PNG')
    return ContentFile(buffer.getvalue(), name=f'demo-{index}.png')


@transaction.atomic
def cargar_demo():
    users = []
    for index, name in enumerate(('ana', 'bruno', 'carla', 'diego')):
        user, created = Usuario.objects.get_or_create(username=f'demo_streak_{name}', defaults={
            'first_name': f'DEMO {name.title()}', 'es_demo': True, 'es_pro': index == 0,
        })
        if not user.es_demo:
            raise ValueError('Un nombre reservado DEMO pertenece a una cuenta existente. No se modifico.')
        if created:
            user.set_unusable_password()
            user.save(update_fields=['password'])
        users.append(user)
    now = timezone.now()
    for index, title in enumerate(('Liga Aurora', 'Copa Horizonte', 'Liga Archivo')):
        finished = index == 2
        torneo, _ = Torneo.objects.get_or_create(demo_clave=f'streak-demo-{index}', defaults={
            'nombre': f'DEMO - {title}', 'temporada': 'Demostracion',
            'estado': 'FINALIZADO' if finished else 'ACTIVO',
            'formato': 'LIGA' if index != 1 else 'GRUPOS_ELIMINATORIA',
        })
        # Serialize repeated admin requests for the same demo tournament.
        Torneo.objects.select_for_update().get(pk=torneo.pk)
        teams = []
        for team_index, name in enumerate(('Aurora', 'Volcan', 'Costa', 'Altiplano', 'Bosque', 'Lago', 'Estrella', 'Valle')):
            # Reuse already enrolled legacy demo teams; new demos share the global team.
            team = torneo.equipos.filter(nombre=f'DEMO {name}').first()
            created = False
            if team is None:
                team = Equipo.objects.filter(nombre=f'DEMO {name}', torneos__demo_clave__startswith='streak-demo-').first()
                if team is None:
                    team = Equipo.objects.create(nombre=f'DEMO {name}')
                    created = True
                torneo.equipos.add(team)
            if created or not team.escudo:
                team.escudo.save(f'demo-{team_index}.png', escudo_demo(team_index))
            teams.append(team)
        phases = []
        for phase_index, tipo in enumerate(('LIGA', 'GRUPOS', 'ELIMINATORIA')):
            phase, _ = Fase.objects.get_or_create(torneo=torneo, orden=phase_index + 1,
                defaults={'nombre': ('Jornada inicial', 'Grupos', 'Final')[phase_index], 'tipo': tipo})
            phases.append(phase)
        quiniela, _ = Quiniela.objects.get_or_create(torneo=torneo, nombre=f'DEMO {title}', defaults={
            'creador': users[0], 'codigo_unico': ('DMALFA', 'DMBETA', 'DMGAMA')[index], 'max_participantes': 50,
        })
        members = [Participante.objects.get_or_create(quiniela=quiniela, usuario=user)[0] for user in users]
        for match_index in range(8):
            past = finished or match_index < 3
            match, _ = Partido.objects.get_or_create(torneo=torneo, fase=phases[match_index % 3],
                equipo_local=teams[match_index], equipo_visita=teams[(match_index + 1) % 8], defaults={
                    'fecha_hora': now + timedelta(days=-(match_index + 1) if past else match_index + 1),
                    'estado': 'FINALIZADO' if past else 'PROGRAMADO',
                    'goles_local': 2 if past else None, 'goles_visita': 1 if past else None,
                })
            if past:
                for player_index, member in enumerate(members):
                    Pronostico.objects.get_or_create(participante=member, partido=match, defaults={
                        'goles_local_pred': (2, 3, 1, 0)[player_index], 'goles_visita_pred': 1,
                    })
    return {'torneos': 3, 'equipos': Equipo.objects.filter(torneos__demo_clave__startswith='streak-demo-').distinct().count(),
            'partidos': 24, 'usuarios': [user.username for user in users]}
