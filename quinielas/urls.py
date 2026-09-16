from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .views_auth import (
    RegisterView,
    CustomTokenObtainPairView,
    RecuperarPasswordView,
    CambiarPasswordView
)
from . import views_api 

urlpatterns = [
    
    path('auth/register/', RegisterView.as_view(), name='auth_register'),
    path('auth/login/', CustomTokenObtainPairView.as_view(), name='auth_login'),
    path('auth/login/refresh/', TokenRefreshView.as_view(), name='auth_login_refresh'),
    path('auth/recuperar/', RecuperarPasswordView.as_view(), name='auth_recuperar'),
    path('auth/cambiar-password/', CambiarPasswordView.as_view(), name='auth_cambiar_password'),


    path('torneos/', views_api.torneo_list, name='torneo_list'),
    path('torneos/<int:pk>/partidos/', views_api.torneo_partidos, name='torneo_partidos'),
    
    path('quinielas/', views_api.quiniela_create, name='quiniela_create'),
    path('quinielas/unirse/', views_api.quiniela_unirse, name='quiniela_unirse'),
    path('quinielas/<int:pk>/pronosticos/', views_api.quiniela_pronosticos, name='quiniela_pronosticos'),
    path('pro/estado/', views_api.pro_estado, name='pro_estado'),
    path('pro/suscribir/', views_api.pro_suscribir, name='pro_suscribir'),
]