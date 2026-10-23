from datetime import timedelta

from django.contrib import admin
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.db.models.deletion import ProtectedError
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from quinielas.demo import cargar_demo
from quinielas.forms_admin import EquipoTorneoAdminForm, PartidoAdminForm
from quinielas.models import Equipo, EquipoTorneo, Fase, Pais, Partido, Torneo, Usuario


class EquiposReutilizablesTests(TestCase):
    def setUp(self):
        self.es = Pais.objects.create(nombre='España', codigo='ES')
        self.gt = Pais.objects.create(nombre='Guatemala', codigo='GT')
        self.liga = Torneo.objects.create(nombre='Liga', temporada='2026', estado='ACTIVO', pais=self.es)
        self.copa = Torneo.objects.create(nombre='Copa', temporada='2026', estado='ACTIVO', pais=self.es)
        self.barcelona = Equipo.objects.create(nombre='Barcelona', pais=self.es)
        self.madrid = Equipo.objects.create(nombre='Real Madrid', pais=self.es)
        self.local_gt = Equipo.objects.create(nombre='Municipal', pais=self.gt)
        self.liga.equipos.add(self.barcelona, self.madrid)
        self.copa.equipos.add(self.barcelona, self.madrid)
        self.fase = Fase.objects.create(torneo=self.liga, nombre='Liga regular', orden=1, tipo='LIGA')
        self.fase_copa = Fase.objects.create(torneo=self.copa, nombre='Final', orden=1, tipo='ELIMINATORIA')

    def partido(self, **kwargs):
        values = dict(torneo=self.liga, fase=self.fase, equipo_local=self.barcelona,
                      equipo_visita=self.madrid, fecha_hora=timezone.now() + timedelta(days=1))
        return Partido(**{**values, **kwargs})

    def test_equipo_sin_torneo_y_grupo_distinto_por_inscripcion(self):
        libre = Equipo.objects.create(nombre='Equipo libre', pais=self.gt)
        self.assertFalse(libre.torneos.exists())
        EquipoTorneo.objects.filter(torneo=self.liga, equipo=self.barcelona).update(grupo='A')
        EquipoTorneo.objects.filter(torneo=self.copa, equipo=self.barcelona).update(grupo='B')
        for torneo, grupo in ((self.liga, 'A'), (self.copa, 'B')):
            data = self.client.get(f'/api/torneos/{torneo.pk}/equipos/').json()
            row = next(row for row in data if row['id'] == self.barcelona.pk)
            self.assertEqual(row['grupo'], grupo)
            self.assertEqual(row['torneo'], torneo.pk)
        self.assertEqual(Equipo.objects.filter(nombre='Barcelona').count(), 1)
        self.partido().full_clean()
        self.partido(torneo=self.copa, fase=self.fase_copa).full_clean()

    def test_partido_rechaza_fase_y_equipo_ajenos(self):
        for overrides, field in (({'fase': self.fase_copa}, 'fase'),
                                 ({'equipo_visita': self.local_gt}, 'equipo_visita'),
                                 ({'equipo_visita': self.barcelona}, 'equipo_visita')):
            with self.assertRaises(ValidationError) as error:
                self.partido(**overrides).full_clean()
            self.assertIn(field, error.exception.message_dict)

    def test_no_se_duplica_inscripcion(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            EquipoTorneo.objects.create(torneo=self.liga, equipo=self.barcelona)

    def test_pais_nacional_e_internacional(self):
        with self.assertRaises(ValidationError):
            EquipoTorneo(torneo=self.liga, equipo=self.local_gt).full_clean()
        internacional = Torneo.objects.create(nombre='Internacional', temporada='2026')
        EquipoTorneo(torneo=internacional, equipo=self.local_gt).full_clean()
        self.barcelona.pais = self.gt
        with self.assertRaises(ValidationError):
            self.barcelona.full_clean()
        self.liga.pais = self.gt
        with self.assertRaises(ValidationError):
            self.liga.full_clean()

    def test_borrar_torneo_conserva_equipo_y_su_otro_torneo(self):
        self.liga.delete()
        self.assertTrue(Equipo.objects.filter(pk=self.barcelona.pk).exists())
        self.assertTrue(self.copa.equipos.filter(pk=self.barcelona.pk).exists())
        with self.assertRaises(ProtectedError):
            self.barcelona.delete()

    def test_api_filtra_por_pais_y_mantiene_detalle_del_partido(self):
        Torneo.objects.create(nombre='Oculto', temporada='2026', pais=self.es)
        torneos = self.client.get('/api/torneos/', {'pais': self.es.pk}).json()
        self.assertEqual({row['id'] for row in torneos}, {self.liga.pk, self.copa.pk})
        equipos = self.client.get('/api/equipos/', {'pais': self.gt.pk}).json()
        self.assertEqual([row['id'] for row in equipos], [self.local_gt.pk])
        self.assertIsNone(equipos[0]['torneo'])
        self.assertEqual(equipos[0]['pais_detalle']['codigo'], 'GT')
        self.assertEqual(len(self.client.get('/api/paises/').json()), 2)
        for endpoint in ('torneos', 'equipos'):
            self.assertEqual(self.client.get(f'/api/{endpoint}/', {'pais': 'abc'}).status_code, 400)
            self.assertEqual(self.client.get(f'/api/{endpoint}/', {'pais': 999999}).status_code, 404)
        partido = self.partido()
        partido.save()
        row = self.client.get(f'/api/partidos/{partido.pk}/').json()
        self.assertEqual(row['equipo_local_detalle']['id'], self.barcelona.pk)
        self.assertEqual(row['equipo_local_detalle']['torneo'], self.liga.pk)

    def test_formularios_filtran_y_rechazan_post_manipulado(self):
        form = PartidoAdminForm(initial={'torneo': self.liga.pk})
        self.assertEqual(list(form.fields['fase'].queryset), [self.fase])
        self.assertEqual(set(form.fields['equipo_local'].queryset), {self.barcelona, self.madrid})
        self.assertFalse(PartidoAdminForm().fields['fase'].queryset.exists())
        inscripcion = EquipoTorneoAdminForm(initial={'torneo': self.liga.pk})
        self.assertFalse(inscripcion.fields['equipo'].queryset.filter(pk=self.local_gt.pk).exists())
        form = PartidoAdminForm(data={
            'torneo': self.liga.pk, 'fase': self.fase_copa.pk, 'equipo_local': self.barcelona.pk,
            'equipo_visita': self.local_gt.pk, 'fecha_hora': timezone.now(), 'estado': 'PROGRAMADO',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('fase', form.errors)
        self.assertIn('equipo_visita', form.errors)

    def test_admin_opciones_permisos_y_eliminacion_inscripciones(self):
        url = reverse('admin:quinielas_partido_opciones_torneo')
        self.assertEqual(self.client.get(url, {'torneo': self.liga.pk}).status_code, 302)
        staff = Usuario.objects.create_user('sin_permiso', is_staff=True)
        self.client.force_login(staff)
        self.assertEqual(self.client.get(url, {'torneo': self.liga.pk}).status_code, 403)
        superuser = Usuario.objects.create_superuser('administrador', 'admin@example.test', 'test')
        self.client.force_login(superuser)
        data = self.client.get(url, {'torneo': self.liga.pk}).json()
        self.assertEqual([row['id'] for row in data['fases']], [self.fase.pk])
        self.assertEqual({row['id'] for row in data['equipos']}, {self.barcelona.pk, self.madrid.pk})
        self.assertEqual(self.client.get(url, {'torneo': 'x'}).status_code, 400)
        partido = self.partido()
        partido.save()
        entry = EquipoTorneo.objects.get(torneo=self.liga, equipo=self.barcelona)
        response = self.client.get(reverse('admin:quinielas_equipotorneo_delete', args=[entry.pk]))
        self.assertEqual(response.status_code, 403)
        response = self.client.post(reverse('admin:quinielas_equipotorneo_changelist'), {
            'action': 'delete_selected', '_selected_action': [entry.pk], 'post': 'yes',
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(EquipoTorneo.objects.filter(pk=entry.pk).exists())
        entry.torneo = self.copa
        with self.assertRaises(ValidationError):
            entry.full_clean()
        self.fase.torneo = self.copa
        with self.assertRaises(ValidationError):
            self.fase.full_clean()

    def test_torneo_admin_solo_incluye_fases(self):
        self.assertEqual([inline.model for inline in admin.site._registry[Torneo].inlines], [Fase])

    def test_filtro_admin_de_fases_respeta_torneo(self):
        superuser = Usuario.objects.create_superuser('filtros', 'filtros@example.test', 'test')
        self.client.force_login(superuser)
        response = self.client.get(reverse('admin:quinielas_partido_changelist'), {'torneo__id__exact': self.liga.pk})
        self.assertEqual(response.status_code, 200)
        fase_filter = response.context['cl'].filter_specs[-1]
        self.assertEqual([pk for pk, label in fase_filter.lookup_choices], [self.fase.pk])

    def test_demo_reutiliza_equipos_y_es_idempotente(self):
        first = cargar_demo()
        second = cargar_demo()
        self.assertEqual(first['equipos'], 8)
        self.assertEqual(second['equipos'], 8)
        self.assertEqual(EquipoTorneo.objects.filter(torneo__demo_clave__startswith='streak-demo-').count(), 24)


class MigracionEquiposTests(TransactionTestCase):
    def test_conserva_ids_escudos_grupos_partidos_y_pronosticos(self):
        executor = MigrationExecutor(connection)
        latest = executor.loader.graph.leaf_nodes()
        previous = [('quinielas', '0010_usuario_pass_temporal_expira')]
        executor.migrate(previous)
        try:
            apps = executor.loader.project_state(previous).apps
            TorneoAnterior = apps.get_model('quinielas', 'Torneo')
            EquipoAnterior = apps.get_model('quinielas', 'Equipo')
            t1 = TorneoAnterior.objects.create(nombre='Liga', temporada='2026')
            t2 = TorneoAnterior.objects.create(nombre='Copa', temporada='2026')
            e1 = EquipoAnterior.objects.create(torneo=t1, nombre='Barcelona', grupo='A', escudo='escudos/barcelona.png')
            e2 = EquipoAnterior.objects.create(torneo=t2, nombre='Barcelona', grupo='B')
            visitante = EquipoAnterior.objects.create(torneo=t1, nombre='Real Madrid')
            fase = apps.get_model('quinielas', 'Fase').objects.create(torneo=t1, nombre='Liga', orden=1, tipo='LIGA')
            partido = apps.get_model('quinielas', 'Partido').objects.create(torneo=t1, fase=fase,
                equipo_local=e1, equipo_visita=visitante, fecha_hora=timezone.now())
            usuario = apps.get_model('quinielas', 'Usuario').objects.create(username='legacy')
            quiniela = apps.get_model('quinielas', 'Quiniela').objects.create(torneo=t1, nombre='Amigos',
                creador=usuario, codigo_unico='TEST01', max_participantes=10)
            participante = apps.get_model('quinielas', 'Participante').objects.create(quiniela=quiniela, usuario=usuario, puntos_totales=5)
            pronostico = apps.get_model('quinielas', 'Pronostico').objects.create(participante=participante,
                partido=partido, goles_local_pred=2, goles_visita_pred=1, puntos_obtenidos=5)
            MigrationExecutor(connection).migrate(latest)
            self.assertEqual(Equipo.objects.count(), 3)
            self.assertEqual(Equipo.objects.get(pk=e1.pk).escudo.name, 'escudos/barcelona.png')
            self.assertEqual(EquipoTorneo.objects.get(equipo_id=e1.pk, torneo_id=t1.pk).grupo, 'A')
            self.assertEqual(EquipoTorneo.objects.get(equipo_id=e2.pk, torneo_id=t2.pk).grupo, 'B')
            self.assertEqual(Partido.objects.get(pk=partido.pk).equipo_local_id, e1.pk)
            from quinielas.models import Pronostico, Participante
            self.assertEqual(Pronostico.objects.get(pk=pronostico.pk).puntos_obtenidos, 5)
            self.assertEqual(Participante.objects.get(pk=participante.pk).puntos_totales, 5)
            self.assertIsNone(Equipo.objects.get(pk=e1.pk).pais_id)
            # Before reuse, reversing and re-applying preserves the original relation.
            MigrationExecutor(connection).migrate(previous)
            self.assertEqual(EquipoAnterior.objects.get(pk=e1.pk).grupo, 'A')
            self.assertEqual(EquipoAnterior.objects.get(pk=e1.pk).torneo_id, t1.pk)
        finally:
            MigrationExecutor(connection).migrate(latest)
