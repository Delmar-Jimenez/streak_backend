from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import (
    Usuario, Torneo, Equipo, Fase, Partido,
    Quiniela, Participante, Pronostico, Pago
)

@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ('Datos Adicionales', {'fields': ('telefono', 'foto', 'es_pro', 'pass_temporal_flag')}),
    )
    list_display = UserAdmin.list_display + ('telefono', 'es_pro', 'pass_temporal_flag')

@admin.register(Torneo)
class TorneoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'formato', 'temporada', 'estado')
    list_filter = ('estado', 'formato', 'temporada')
    search_fields = ('nombre', 'temporada')

@admin.register(Equipo)
class EquipoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'torneo', 'grupo')
    list_filter = ('torneo', 'grupo')
    search_fields = ('nombre', 'torneo__nombre')

@admin.register(Fase)
class FaseAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'torneo', 'orden', 'tipo')
    list_filter = ('torneo', 'tipo')
    search_fields = ('nombre',)
    ordering = ('torneo', 'orden')

@admin.register(Partido)
class PartidoAdmin(admin.ModelAdmin):
    list_display = ('equipo_local', 'equipo_visita', 'torneo', 'fase', 'fecha_hora', 'estado')
    list_filter = ('estado', 'torneo', 'fase')
    search_fields = ('equipo_local__nombre', 'equipo_visita__nombre')
    date_hierarchy = 'fecha_hora'

@admin.register(Quiniela)
class QuinielaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'torneo', 'creador', 'codigo_unico', 'max_participantes')
    list_filter = ('torneo',)
    search_fields = ('nombre', 'codigo_unico', 'creador__username')

@admin.register(Participante)
class ParticipanteAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'quiniela', 'puntos_totales', 'fecha_union')
    list_filter = ('quiniela',)
    search_fields = ('usuario__username', 'quiniela__nombre')
    date_hierarchy = 'fecha_union'

@admin.register(Pronostico)
class PronosticoAdmin(admin.ModelAdmin):
    list_display = ('participante', 'partido', 'goles_local_pred', 'goles_visita_pred', 'puntos_obtenidos')
    list_filter = ('participante__quiniela', 'partido__torneo')
    search_fields = ('participante__usuario__username', 'partido__equipo_local__nombre', 'partido__equipo_visita__nombre')

@admin.register(Pago)
class PagoAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'monto', 'estado', 'referencia', 'fecha')
    list_filter = ('estado', 'fecha')
    search_fields = ('usuario__username', 'referencia')
    date_hierarchy = 'fecha'
