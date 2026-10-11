from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from django.utils import timezone


class LegacyMigrationTests(TransactionTestCase):
    def test_upgrade_repairs_existing_scores_membership_and_payment_state(self):
        executor = MigrationExecutor(connection)
        latest = executor.loader.graph.leaf_nodes()
        old_target = [('quinielas', '0001_initial')]
        executor.migrate(old_target)
        try:
            apps = executor.loader.project_state(old_target).apps
            User = apps.get_model('quinielas', 'Usuario')
            Torneo = apps.get_model('quinielas', 'Torneo')
            Equipo = apps.get_model('quinielas', 'Equipo')
            Fase = apps.get_model('quinielas', 'Fase')
            Partido = apps.get_model('quinielas', 'Partido')
            Quiniela = apps.get_model('quinielas', 'Quiniela')
            Participante = apps.get_model('quinielas', 'Participante')
            Pronostico = apps.get_model('quinielas', 'Pronostico')
            Pago = apps.get_model('quinielas', 'Pago')
            owner = User.objects.create(username='owner')
            rival = User.objects.create(username='rival')
            torneo = Torneo.objects.create(nombre='Legacy', temporada='2026')
            fase = Fase.objects.create(torneo=torneo, nombre='Fase', orden=1, tipo='LIGA')
            local = Equipo.objects.create(torneo=torneo, nombre='A')
            visita = Equipo.objects.create(torneo=torneo, nombre='B')
            partido = Partido.objects.create(torneo=torneo, fase=fase, equipo_local=local, equipo_visita=visita,
                fecha_hora=timezone.now(), estado='FINALIZADO', goles_local=2, goles_visita=1)
            quiniela = Quiniela.objects.create(torneo=torneo, creador=owner, nombre='Legacy', codigo_unico='OLD123', max_participantes=1)
            member = Participante.objects.create(quiniela=quiniela, usuario=rival, puntos_totales=0)
            pred = Pronostico.objects.create(participante=member, partido=partido, goles_local_pred=2, goles_visita_pred=1, puntos_obtenidos=0)
            pago = Pago.objects.create(usuario=owner, monto='5.00', estado='APROBADO', referencia='ch_legacy')
            executor = MigrationExecutor(connection)
            executor.migrate(latest)
            new_apps = executor.loader.project_state(latest).apps
            self.assertEqual(new_apps.get_model('quinielas', 'Participante').objects.get(pk=member.pk).puntos_totales, 5)
            self.assertEqual(new_apps.get_model('quinielas', 'Pronostico').objects.get(pk=pred.pk).puntos_obtenidos, 5)
            self.assertTrue(new_apps.get_model('quinielas', 'Participante').objects.filter(quiniela_id=quiniela.pk, usuario_id=owner.pk).exists())
            self.assertEqual(new_apps.get_model('quinielas', 'Quiniela').objects.get(pk=quiniela.pk).max_participantes, 2)
            self.assertEqual(new_apps.get_model('quinielas', 'Pago').objects.get(pk=pago.pk).estado, 'COMPLETADO')
        finally:
            MigrationExecutor(connection).migrate(latest)
