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

routes = [
    
    ('auth/register/', RegisterView.as_view(), 'auth_register'),
    ('auth/login/', CustomTokenObtainPairView.as_view(), 'auth_login'),
    ('auth/login/refresh/', CustomTokenRefreshView.as_view(), 'auth_login_refresh'),
    ('auth/recuperar/', RecuperarPasswordView.as_view(), 'auth_recuperar'),
    ('auth/cambiar-password/', CambiarPasswordView.as_view(), 'auth_cambiar_password'),
    ('auth/restablecer/', RestablecerPasswordView.as_view(), 'auth_restablecer'),
    ('usuarios/me/', PerfilView.as_view(), 'usuario_me'),


    ('torneos/', views_api.torneo_list, 'torneo_list'),
    ('torneos/<int:pk>/', views_api.torneo_detail, 'torneo_detail'),
    ('torneos/<int:pk>/equipos/', views_api.torneo_equipos, 'torneo_equipos'),
    ('torneos/<int:pk>/fases/', views_api.torneo_fases, 'torneo_fases'),
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
    ('quinielas/<int:pk>/pronosticos/', views_api.quiniela_pronosticos, 'quiniela_pronosticos'),
    ('pro/estado/', views_api.pro_estado, 'pro_estado'),
    ('pro/suscribir/', views_payments.pro_suscribir, 'pro_suscribir'),
    ('pro/pagos/', views_api.pro_pagos, 'pro_pagos'),
    ('pro/webhook/', views_payments.stripe_webhook, 'stripe_webhook'),
]

# Both forms resolve directly so POST bodies never depend on redirect behavior.
urlpatterns = [
    entry
    for route, view, name in routes
    for entry in (path(route, view, name=name), path(route.rstrip('/'), view))
]
