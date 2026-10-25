from django.urls import path
from .views_auth import (
    RegisterView,
    CustomTokenObtainPairView,
    RecuperarPasswordView,
    CambiarPasswordView,
    RestablecerPasswordView,
    CustomTokenRefreshView,
    PerfilView,
)
from . import views_api 
from . import views_payments
from . import views_insights

routes = [
    
    ('auth/register/', RegisterView.as_view(), 'auth_register'),
    ('auth/login/', CustomTokenObtainPairView.as_view(), 'auth_login'),
    ('auth/login/refresh/', CustomTokenRefreshView.as_view(), 'auth_login_refresh'),
    ('auth/recuperar/', RecuperarPasswordView.as_view(), 'auth_recuperar'),
    ('auth/cambiar-password/', CambiarPasswordView.as_view(), 'auth_cambiar_password'),
    ('auth/restablecer/', RestablecerPasswordView.as_view(), 'auth_restablecer'),
    ('usuarios/me/', PerfilView.as_view(), 'usuario_me'),


    ('paises/', views_api.pais_list, 'pais_list'),
    ('equipos/', views_api.equipo_list, 'equipo_list'),
    ('torneos/', views_api.torneo_list, 'torneo_list'),
    ('torneos/<int:pk>/', views_api.torneo_detail, 'torneo_detail'),
    ('torneos/<int:pk>/equipos/', views_api.torneo_equipos, 'torneo_equipos'),
    ('torneos/<int:pk>/fases/', views_api.torneo_fases, 'torneo_fases'),
    ('torneos/<int:pk>/filtros/', views_api.torneo_filtros, 'torneo_filtros'),
    ('partidos/<int:pk>/', views_api.partido_detail, 'partido_detail'),
    ('torneos/<int:pk>/partidos/', views_api.torneo_partidos, 'torneo_partidos'),
    
    ('quinielas/', views_api.quiniela_create, 'quiniela_create'),
    ('quinielas/historial/', views_api.quinielas_historial, 'quinielas_historial'),
    ('quinielas/<int:pk>/partidos/', views_api.quiniela_partidos, 'quiniela_partidos'),
    ('quinielas/<int:pk>/partidos/<int:pid>/detalle/', views_api.quiniela_partido_detalle, 'quiniela_partido_detalle'),
    ('quinielas/<int:pk>/participantes/<int:uid>/detalle/', views_api.quiniela_usuario_detalle, 'quiniela_usuario_detalle'),
    ('quinielas/mias/', views_api.quinielas_mias, 'quinielas_mias'),
    ('quinielas/<int:pk>/', views_api.quiniela_detail, 'quiniela_detail'),
    ('quinielas/<int:pk>/participantes/', views_api.quiniela_participantes, 'quiniela_participantes'),
    ('quinielas/<int:pk>/tabla/', views_api.quiniela_tabla, 'quiniela_tabla'),
    ('quinielas/<int:pk>/participantes/<int:participante_id>/pronosticos/', views_api.quiniela_rival_pronosticos, 'quiniela_rival_pronosticos'),
    ('quinielas/unirse/', views_api.quiniela_unirse, 'quiniela_unirse'),
    ('quinielas/validar-codigo/', views_api.quiniela_validar_codigo, 'quiniela_validar_codigo'),
    ('quinielas/<int:pk>/pronosticos/', views_api.quiniela_pronosticos, 'quiniela_pronosticos'),
    ('pro/estado/', views_api.pro_estado, 'pro_estado'),
    ('pro/estadisticas/', views_insights.estadisticas, 'pro_estadisticas'),
    ('pro/pronosticos/exportar/', views_insights.exportar_pronosticos, 'pro_exportar_pronosticos'),
    ('quinielas/<int:pk>/tabla/exportar/', views_insights.exportar_tabla, 'pro_exportar_tabla'),
    ('pro/calendario/', views_insights.calendario, 'pro_calendario'),
    ('pro/suscribir/', views_payments.pro_suscribir, 'pro_suscribir'),
    ('pro/pagos/', views_api.pro_pagos, 'pro_pagos'),
    ('pro/pago-pendiente/', views_payments.pro_pago_pendiente, 'pro_pago_pendiente'),
    ('pro/pagos/<int:pk>/cancelar/', views_payments.pro_cancelar_pago, 'pro_cancelar_pago'),
    ('pro/webhook/', views_payments.stripe_webhook, 'stripe_webhook'),
]

# Both forms resolve directly so POST bodies never depend on redirect behavior.
urlpatterns = [
    entry
    for route, view, name in routes
    for entry in (path(route, view, name=name), path(route.rstrip('/'), view))
]
