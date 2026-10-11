from django.db import models, transaction
from django.core.exceptions import ValidationError
from django.db.models.functions import Lower
from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _

class Usuario(AbstractUser):
    telefono = models.CharField(max_length=20, blank=True, null=True)
    foto = models.ImageField(upload_to='perfiles/', blank=True, null=True)
    es_pro = models.BooleanField(default=False)
    pass_temporal_flag = models.BooleanField(default=False)

    class Meta(AbstractUser.Meta):
        constraints = [
            models.UniqueConstraint(Lower('email'), condition=~models.Q(email=''), name='usuario_email_ci_unico'),
        ]

    def __str__(self):
        return self.username

class Torneo(models.Model):
    class Formato(models.TextChoices):
        LIGA = 'LIGA', _('Liga')
        GRUPOS_ELIMINATORIA = 'GRUPOS_ELIMINATORIA', _('Grupos y Eliminatoria')

    class Estado(models.TextChoices):
        BORRADOR = 'BORRADOR', _('Borrador')
        ACTIVO = 'ACTIVO', _('Activo')
        FINALIZADO = 'FINALIZADO', _('Finalizado')

    nombre = models.CharField(max_length=255)
    formato = models.CharField(max_length=50, choices=Formato.choices, default=Formato.LIGA)
    temporada = models.CharField(max_length=50)
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.BORRADOR)

    def __str__(self):
        return f"{self.nombre} - {self.temporada}"

class Equipo(models.Model):
    torneo = models.ForeignKey(Torneo, on_delete=models.CASCADE, related_name='equipos')
    nombre = models.CharField(max_length=255)
    escudo = models.ImageField(upload_to='escudos/', blank=True, null=True)
    grupo = models.CharField(max_length=50, blank=True, null=True)

    def __str__(self):
        return self.nombre

class Fase(models.Model):
    torneo = models.ForeignKey(Torneo, on_delete=models.CASCADE, related_name='fases')
    nombre = models.CharField(max_length=100)
    orden = models.IntegerField()
    tipo = models.CharField(max_length=50)

    class Meta:
        ordering = ['orden']

    def __str__(self):
        return f"{self.torneo.nombre} - {self.nombre}"

class Partido(models.Model):
    class Estado(models.TextChoices):
        PROGRAMADO = 'PROGRAMADO', _('Programado')
        EN_JUEGO = 'EN_JUEGO', _('En Juego')
        FINALIZADO = 'FINALIZADO', _('Finalizado')
        SUSPENDIDO = 'SUSPENDIDO', _('Suspendido')
        CANCELADO = 'CANCELADO', _('Cancelado')

    torneo = models.ForeignKey(Torneo, on_delete=models.CASCADE, related_name='partidos')
    fase = models.ForeignKey(Fase, on_delete=models.CASCADE, related_name='partidos')
    equipo_local = models.ForeignKey(Equipo, on_delete=models.CASCADE, related_name='partidos_local')
    equipo_visita = models.ForeignKey(Equipo, on_delete=models.CASCADE, related_name='partidos_visita')
    fecha_hora = models.DateTimeField()
    goles_local = models.IntegerField(null=True, blank=True)
    goles_visita = models.IntegerField(null=True, blank=True)
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.PROGRAMADO)

    def clean(self):
        errors = {}
        if self.equipo_local_id == self.equipo_visita_id:
            errors['equipo_visita'] = 'Los equipos deben ser diferentes.'
        for field in ('equipo_local', 'equipo_visita', 'fase'):
            if getattr(self, f'{field}_id') and getattr(self, field).torneo_id != self.torneo_id:
                errors[field] = 'Debe pertenecer al mismo torneo.'
        for field in ('goles_local', 'goles_visita'):
            value = getattr(self, field)
            if value is not None and value < 0:
                errors[field] = 'Los goles no pueden ser negativos.'
            if self.estado == self.Estado.FINALIZADO and value is None:
                errors[field] = 'Un partido finalizado requiere marcador.'
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        with transaction.atomic():
            return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.equipo_local} vs {self.equipo_visita} ({self.fecha_hora.strftime('%Y-%m-%d %H:%M')})"

class Quiniela(models.Model):
    nombre = models.CharField(max_length=255)
    torneo = models.ForeignKey(Torneo, on_delete=models.CASCADE, related_name='quinielas')
    creador = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='quinielas_creadas')
    codigo_unico = models.CharField(max_length=6, unique=True)
    max_participantes = models.IntegerField()

    def __str__(self):
        return self.nombre

class Participante(models.Model):
    quiniela = models.ForeignKey(Quiniela, on_delete=models.CASCADE, related_name='participantes')
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='participaciones')
    puntos_totales = models.IntegerField(default=0)
    fecha_union = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('quiniela', 'usuario')

    def __str__(self):
        return f"{self.usuario.username} en {self.quiniela.nombre}"

class Pronostico(models.Model):
    participante = models.ForeignKey(Participante, on_delete=models.CASCADE, related_name='pronosticos')
    partido = models.ForeignKey(Partido, on_delete=models.CASCADE, related_name='pronosticos')
    goles_local_pred = models.IntegerField()
    goles_visita_pred = models.IntegerField()
    puntos_obtenidos = models.IntegerField(default=0)

    def clean(self):
        if self.participante_id and self.partido_id:
            if self.participante.quiniela.torneo_id != self.partido.torneo_id:
                raise ValidationError('El partido debe pertenecer al torneo de la quiniela.')
        if any(value is not None and value < 0 for value in (self.goles_local_pred, self.goles_visita_pred)):
            raise ValidationError('Los goles no pueden ser negativos.')

    def save(self, *args, **kwargs):
        with transaction.atomic():
            Participante.objects.select_for_update().get(pk=self.participante_id)
            return super().save(*args, **kwargs)

    class Meta:
        unique_together = ('participante', 'partido')

    def __str__(self):
        return f"{self.participante.usuario.username} - {self.partido}"

class Pago(models.Model):
    class Estado(models.TextChoices):
        PENDIENTE = 'PENDIENTE', _('Pendiente')
        COMPLETADO = 'COMPLETADO', _('Completado')
        FALLIDO = 'FALLIDO', _('Fallido')
        CANCELADO = 'CANCELADO', _('Cancelado')
        REEMBOLSADO = 'REEMBOLSADO', _('Reembolsado')

    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='pagos')
    monto = models.DecimalField(max_digits=10, decimal_places=2)
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.PENDIENTE)
    referencia = models.CharField(max_length=255)
    moneda = models.CharField(max_length=3, default='usd')
    clave_idempotencia = models.CharField(max_length=128, null=True, blank=True)
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['usuario', 'clave_idempotencia'], name='pago_usuario_idempotencia'),
        ]

    def __str__(self):
        return f"Pago {self.id} - {self.usuario.username} - {self.monto}"
