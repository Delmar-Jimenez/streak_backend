from django import forms

from .models import Equipo, EquipoTorneo, Fase, Partido, Torneo


def torneo_seleccionado(form):
    value = form.data.get('torneo') if form.is_bound else form.initial.get('torneo')
    if isinstance(value, Torneo):
        return value
    try:
        return Torneo.objects.filter(pk=int(value)).first() if value else None
    except (ValueError, TypeError, OverflowError):
        return None


class PartidoAdminForm(forms.ModelForm):
    class Meta:
        model = Partido
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        torneo = torneo_seleccionado(self)
        self.fields['fase'].queryset = torneo.fases.all() if torneo else Fase.objects.none()
        equipos = torneo.equipos.all() if torneo else Equipo.objects.none()
        for field in ('equipo_local', 'equipo_visita'):
            self.fields[field].queryset = equipos
            self.fields[field].help_text = 'Selecciona primero el torneo. Solo aparecen sus equipos inscritos.'
        self.fields['fase'].help_text = 'Solo aparecen las fases del torneo seleccionado.'


class EquipoTorneoAdminForm(forms.ModelForm):
    class Meta:
        model = EquipoTorneo
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        torneo = torneo_seleccionado(self)
        equipos = Equipo.objects.all() if torneo else Equipo.objects.none()
        if torneo and torneo.pais_id:
            equipos = equipos.filter(pais_id=torneo.pais_id)
        self.fields['equipo'].queryset = equipos
        self.fields['equipo'].help_text = 'Elige primero el torneo y reutiliza un equipo existente. En torneos nacionales solo aparecen equipos de ese país.'
