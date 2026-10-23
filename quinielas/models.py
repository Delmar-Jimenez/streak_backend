from django.db import models, transaction
from django.core.exceptions import ValidationError
from django.db.models.functions import Lower
from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _
from datetime import timedelta
from django.utils import timezone

class Usuario(AbstractUser):
    telefono = models.CharField(max_length=20, blank=True, null=True)
    foto = models.ImageField(upload_to='perfiles/', blank=True, null=True)
    es_pro = models.BooleanField(default=False)
    pass_temporal_flag = models.BooleanField(default=False)
    # RN-06: la contrasena temporal enviada por correo vence a las 24 horas.
    pass_temporal_expira = models.DateTimeField(null=True, blank=True)
    es_demo = models.BooleanField(default=False, editable=False)
    fecha_nacimiento = models.DateField(null=True, blank=True)

    class Meta(AbstractUser.Meta):
        constraints = [
            models.UniqueConstraint(Lower('email'), condition=~models.Q(email=''), name='usuario_email_ci_unico'),
        ]

    def __str__(self):
        return self.username

    def pass_temporal_vencida(self):
        return bool(self.pass_temporal_flag and self.pass_temporal_expira and timezone.now() >= self.pass_temporal_expira)

class Pais(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    codigo = models.CharField(max_length=2, unique=True, help_text='Código ISO de dos letras, por ejemplo GT o ES.')

    class Meta:
        verbose_name = 'país'
        verbose_name_plural = 'países'
        ordering = ['nombre']

    def clean(self):
        self.codigo = self.codigo.strip().upper()
        if len(self.codigo) != 2 or not self.codigo.isascii() or not self.codigo.isalpha():
            raise ValidationError({'codigo': 'Usa dos letras, por ejemplo GT o ES.'})

    def save(self, *args, **kwargs):
        self.codigo = self.codigo.strip().upper()
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.nombre


class Torneo(models.Model):
    class Formato(models.TextChoices):
        LIGA = 'LIGA', _('Liga')
        GRUPOS_ELIMINATORIA = 'GRUPOS_ELIMINATORIA', _('Grupos y Eliminatoria')

    class Estado(models.TextChoices):
        BORRADOR = 'BORRADOR', _('Borrador')
        ACTIVO = 'ACTIVO', _('Activo')
        FINALIZADO = 'FINALIZADO', _('Finalizado')

    nombre = models.CharField(max_length=255)
    pais = models.ForeignKey(Pais, on_delete=models.PROTECT, related_name='torneos', null=True, blank=True,
                             help_text='Déjalo vacío para torneos internacionales o pendientes de clasificar.')
    equipos = models.ManyToManyField('Equipo', through='EquipoTorneo', related_name='torneos', blank=True)
    formato = models.CharField(max_length=50, choices=Formato.choices, default=Formato.LIGA)
    temporada = models.CharField(max_length=50)
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.BORRADOR)
    demo_clave = models.CharField(max_length=50, unique=True, null=True, blank=True, editable=False)

    def clean(self):
        if self.pk and self.pais_id and self.equipos.exclude(pais_id=self.pais_id).exists():
            raise ValidationError({'pais': 'Todos los equipos inscritos deben tener el país del torneo. Clasifica primero los equipos o deja el torneo sin país si es internacional.'})

    def __str__(self):
        return f"{self.nombre} - {self.temporada}"

class Equipo(models.Model):
    nombre = models.CharField(max_length=255)
    pais = models.ForeignKey(Pais, on_delete=models.PROTECT, related_name='equipos', null=True, blank=True)
    escudo = models.ImageField(upload_to='escudos/', blank=True, null=True)

    class Meta:
        ordering = ['nombre', 'id']

    def clean(self):
        if self.pk and self.torneos.filter(pais__isnull=False).exclude(pais_id=self.pais_id).exists():
            raise ValidationError({'pais': 'El país debe coincidir con los torneos nacionales donde está inscrito.'})

    def __str__(self):
        return self.nombre


class EquipoTorneo(models.Model):
    torneo = models.ForeignKey(Torneo, on_delete=models.CASCADE, related_name='inscripciones_equipos')
    equipo = models.ForeignKey(Equipo, on_delete=models.PROTECT, related_name='inscripciones_torneos')
    grupo = models.CharField(max_length=50, blank=True, null=True)

    class Meta:
        verbose_name = 'equipo por torneo'
        verbose_name_plural = 'equipos por torneo'
        constraints = [models.UniqueConstraint(fields=['torneo', 'equipo'], name='equipo_torneo_unico')]

    def clean(self):
        if self.torneo_id and self.equipo_id:
            if self.torneo.pais_id and self.equipo.pais_id != self.torneo.pais_id:
                raise ValidationError({'equipo': 'Selecciona un equipo del país del torneo.'})
        if self.pk:
            original = type(self).objects.get(pk=self.pk)
            if (original.torneo_id, original.equipo_id) != (self.torneo_id, self.equipo_id) and original.tiene_partidos():
                raise ValidationError('Esta inscripción tiene partidos. Crea otra inscripción sin modificar la existente.')

    def tiene_partidos(self):
        return Partido.objects.filter(torneo_id=self.torneo_id).filter(
            models.Q(equipo_local_id=self.equipo_id) | models.Q(equipo_visita_id=self.equipo_id)
        ).exists()

    def __str__(self):
        return f'{self.equipo} — {self.torneo}'

class Fase(models.Model):
    class Tipo(models.TextChoices):
        LIGA = 'LIGA', _('Liga')
        GRUPOS = 'GRUPOS', _('Grupos')
        ELIMINATORIA = 'ELIMINATORIA', _('Eliminatoria')

    torneo = models.ForeignKey(Torneo, on_delete=models.CASCADE, related_name='fases')
    nombre = models.CharField(max_length=100)
    orden = models.IntegerField()
    tipo = models.CharField(max_length=50, choices=Tipo.choices)

    def clean(self):
        if self.pk and self.partidos.exclude(torneo_id=self.torneo_id).exists():
            raise ValidationError({'torneo': 'Esta fase tiene partidos en otro torneo. No se puede mover.'})

    def save(self, *args, **kwargs):
        if self.tipo not in self.Tipo.values:
            raise ValidationError({'tipo': 'Selecciona LIGA, GRUPOS o ELIMINATORIA.'})
        return super().save(*args, **kwargs)

    class Meta:
        ordering = ['orden']
        constraints = [models.CheckConstraint(condition=models.Q(tipo__in=['LIGA', 'GRUPOS', 'ELIMINATORIA']), name='fase_tipo_valido')]

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
    equipo_local = models.ForeignKey(Equipo, on_delete=models.PROTECT, related_name='partidos_local')
    equipo_visita = models.ForeignKey(Equipo, on_delete=models.PROTECT, related_name='partidos_visita')
    fecha_hora = models.DateTimeField()
    goles_local = models.IntegerField(null=True, blank=True)
    goles_visita = models.IntegerField(null=True, blank=True)
    # The scoring fields above always represent regulation time, not extra time/penalties.
    goles_local_prorroga = models.PositiveSmallIntegerField(null=True, blank=True)
    goles_visita_prorroga = models.PositiveSmallIntegerField(null=True, blank=True)
    penales_local = models.PositiveSmallIntegerField(null=True, blank=True)
    penales_visita = models.PositiveSmallIntegerField(null=True, blank=True)
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.PROGRAMADO)

    @property
    def cierre_pronosticos(self):
        return self.fecha_hora - timedelta(minutes=5)

    @property
    def pronosticos_abiertos(self):
        return self.estado == self.Estado.PROGRAMADO and timezone.now() < self.cierre_pronosticos

    def clean(self):
        errors = {}
        if self.equipo_local_id == self.equipo_visita_id:
            errors['equipo_visita'] = 'Los equipos deben ser diferentes.'
        if self.fase_id and self.fase.torneo_id != self.torneo_id:
            errors['fase'] = 'Debe pertenecer al mismo torneo.'
        for field in ('equipo_local', 'equipo_visita'):
            equipo_id = getattr(self, f'{field}_id')
            if equipo_id and self.torneo_id and not EquipoTorneo.objects.filter(torneo_id=self.torneo_id, equipo_id=equipo_id).exists():
                errors[field] = 'El equipo debe estar inscrito en este torneo.'
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
    creador = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True, related_name='quinielas_creadas')
    codigo_unico = models.CharField(max_length=6, unique=True)
    max_participantes = models.IntegerField()

    def clean(self):
        limite = 100 if self.creador_id and self.creador.es_pro else 50
        if self.max_participantes is not None and not 2 <= self.max_participantes <= limite:
            raise ValidationError({'max_participantes': f'El limite permitido es de 2 a {limite}.'})

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

    usuario = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True, related_name='pagos')
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
        return f"Pago {self.id} - {self.usuario_id or 'cuenta eliminada'} - {self.monto}"


class ImagenArchivo(models.Model):
    nombre = models.CharField(max_length=255, primary_key=True)
    contenido = models.BinaryField()
    tipo = models.CharField(max_length=50, default='image/webp')
    creado = models.DateTimeField(auto_now_add=True)
