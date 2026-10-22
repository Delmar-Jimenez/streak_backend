from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.urls import path
from django.shortcuts import render
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from .forms_admin import PartidoAdminForm, EquipoTorneoAdminForm
from .demo import cargar_demo
from .models import (
    Usuario, Torneo, Equipo, Fase, Partido,
    Quiniela, Participante, Pronostico, Pago, Pais, EquipoTorneo
)

@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ('Datos Adicionales', {'fields': ('telefono', 'foto', 'es_pro', 'pass_temporal_flag', 'pass_temporal_expira')}),
    )
    list_display = UserAdmin.list_display + ('telefono', 'es_pro', 'pass_temporal_flag')

@admin.register(Pais)
class PaisAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'codigo')
    search_fields = ('nombre', 'codigo')


class FaseInline(admin.TabularInline):
    model = Fase
    extra = 0
    show_change_link = True


@admin.register(Torneo)
class TorneoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'pais', 'formato', 'temporada', 'estado')
    list_filter = ('pais', 'estado', 'formato', 'temporada')
    search_fields = ('nombre', 'temporada')
    inlines = (FaseInline,)

    def get_urls(self):
        return [path('demo/', self.admin_site.admin_view(self.demo), name='quinielas_torneo_demo')] + super().get_urls()

    def demo(self, request):
        if not request.user.is_superuser:
            raise PermissionDenied
        context = {**self.admin_site.each_context(request), 'title': 'Datos de demostracion STREAK'}
        if request.method == 'POST' and request.POST.get('confirmar') == 'si':
            context['resultado'] = cargar_demo()
        return render(request, 'admin/quinielas/demo.html', context)

@admin.register(Equipo)
class EquipoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'pais')
    list_filter = ('pais',)
    search_fields = ('nombre', 'pais__nombre')


class OpcionesTorneoAdminMixin:
    class Media:
        js = ('quinielas/admin_torneo.js',)

    def get_urls(self):
        return [path('opciones-torneo/', self.admin_site.admin_view(self.opciones_torneo),
                     name=f'quinielas_{self.model._meta.model_name}_opciones_torneo')] + super().get_urls()

    def opciones_torneo(self, request):
        if not (self.has_add_permission(request) or self.has_change_permission(request)):
            raise PermissionDenied
        try:
            torneo_id = int(request.GET.get('torneo', ''))
            if not 0 < torneo_id < 2**63:
                raise ValueError
        except ValueError:
            return JsonResponse({'error': 'Selecciona un torneo válido.'}, status=400)
        torneo = get_object_or_404(Torneo, pk=torneo_id)
        if self.model is Partido:
            equipos = torneo.equipos.all()
        else:
            equipos = Equipo.objects.all()
            if torneo.pais_id:
                equipos = equipos.filter(pais_id=torneo.pais_id)
        return JsonResponse({
            'equipos': list(equipos.order_by('nombre', 'id').values('id', 'nombre')),
            'fases': list(torneo.fases.order_by('orden', 'id').values('id', 'nombre')),
        })


@admin.register(EquipoTorneo)
class EquipoTorneoAdmin(OpcionesTorneoAdminMixin, admin.ModelAdmin):
    form = EquipoTorneoAdminForm
    list_display = ('equipo', 'torneo', 'grupo')
    list_filter = ('torneo__pais', 'torneo', 'grupo')
    search_fields = ('equipo__nombre', 'torneo__nombre')

    def has_delete_permission(self, request, obj=None):
        return super().has_delete_permission(request, obj) and not (obj and obj.tiene_partidos())

    def get_deleted_objects(self, objs, request):
        deleted, counts, permissions, protected = super().get_deleted_objects(objs, request)
        protected.extend(str(obj) for obj in objs if obj.tiene_partidos())
        return deleted, counts, permissions, protected

@admin.register(Fase)
class FaseAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'torneo', 'orden', 'tipo')
    list_filter = ('torneo', 'tipo')
    search_fields = ('nombre',)
    ordering = ('torneo', 'orden')

class FasesDelTorneoFilter(admin.RelatedFieldListFilter):
    def has_output(self):
        return bool(self.lookup_choices)

    def field_choices(self, field, request, model_admin):
        fases = Fase.objects.select_related('torneo')
        torneo_id = request.GET.get('torneo__id__exact')
        if torneo_id:
            try:
                value = int(torneo_id)
                fases = fases.filter(torneo_id=value) if 0 < value < 2**63 else fases.none()
            except ValueError:
                fases = fases.none()
        return [(fase.pk, str(fase)) for fase in fases]


@admin.register(Partido)
class PartidoAdmin(OpcionesTorneoAdminMixin, admin.ModelAdmin):
    form = PartidoAdminForm
    list_display = ('equipo_local', 'equipo_visita', 'torneo', 'fase', 'fecha_hora', 'estado')
    list_filter = ('estado', 'torneo', ('fase', FasesDelTorneoFilter))
    search_fields = ('equipo_local__nombre', 'equipo_visita__nombre')
    date_hierarchy = 'fecha_hora'

@admin.register(Quiniela)
class QuinielaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'torneo', 'creador', 'codigo_unico', 'max_participantes')
    list_filter = ('torneo',)
    search_fields = ('nombre', 'codigo_unico', 'creador__username')

@admin.register(Participante)
class ParticipanteAdmin(admin.ModelAdmin):
    readonly_fields = ('puntos_totales',)
    list_display = ('usuario', 'quiniela', 'puntos_totales', 'fecha_union')
    list_filter = ('quiniela',)
    search_fields = ('usuario__username', 'quiniela__nombre')
    date_hierarchy = 'fecha_union'

@admin.register(Pronostico)
class PronosticoAdmin(admin.ModelAdmin):
    readonly_fields = ('puntos_obtenidos',)

    def get_readonly_fields(self, request, obj=None):
        return self.readonly_fields + (('participante', 'partido') if obj else ())
    list_display = ('participante', 'partido', 'goles_local_pred', 'goles_visita_pred', 'puntos_obtenidos')
    list_filter = ('participante__quiniela', 'partido__torneo')
    search_fields = ('participante__usuario__username', 'partido__equipo_local__nombre', 'partido__equipo_visita__nombre')

@admin.register(Pago)
class PagoAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'monto', 'estado', 'referencia', 'fecha')
    list_filter = ('estado', 'fecha')
    search_fields = ('usuario__username', 'referencia')
    date_hierarchy = 'fecha'
