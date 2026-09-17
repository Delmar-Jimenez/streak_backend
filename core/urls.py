"""
URL configuration for core project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse
from django.contrib.auth import get_user_model

# --- TRUCO PARA CREAR EL ADMIN SIN CONSOLA ---
def crear_admin_secreto(request):
    User = get_user_model()
    try:
        if not User.objects.filter(username='delmar').exists():
            User.objects.create_superuser('delmar', 'delmar@streak.com', 'Streak2026!')
            return JsonResponse({'mensaje': '¡Admin creado con éxito!', 'usuario': 'delmar', 'clave': 'Streak2026!'})
        return JsonResponse({'mensaje': 'El admin ya estaba creado. Ve a /admin/'})
    except Exception as e:
        return JsonResponse({'error_detectado': str(e)})
# ---------------------------------------------

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('quinielas.urls')), # Conecta las rutas de tu app
    path('crear-admin/', crear_admin_secreto), # Nuestra ruta secreta
]