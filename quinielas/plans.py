"""One capability catalog for the website and mobile clients."""
FEATURES = [
    {'codigo': 'participantes', 'nombre': 'Participantes por quiniela', 'gratis': 50, 'pro': 100},
    {'codigo': 'estadisticas', 'nombre': 'Estadísticas personales y desglose por torneo', 'gratis': False, 'pro': True},
    {'codigo': 'exportar_pronosticos', 'nombre': 'Exportar tus pronósticos a CSV', 'gratis': False, 'pro': True},
    {'codigo': 'exportar_tabla', 'nombre': 'Exportar la clasificación a CSV', 'gratis': False, 'pro': True},
    {'codigo': 'calendario', 'nombre': 'Calendario de cierres para importar al teléfono', 'gratis': False, 'pro': True},
    {'codigo': 'distintivo', 'nombre': 'Distintivo PRO en la clasificación', 'gratis': False, 'pro': True},
]


def capacidades(user):
    plan = 'pro' if user.es_pro else 'gratis'
    return {feature['codigo']: feature[plan] for feature in FEATURES}
