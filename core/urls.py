from django.contrib import admin
from django.urls import include, path
from quinielas import views_web

urlpatterns = [
    path('eliminar-cuenta/', views_web.eliminar_cuenta_web, name='eliminar_cuenta_web'),
    path('recuperar-acceso/', views_web.recuperar_acceso, name='recuperar_acceso'),
    path('media/<path:nombre>', views_web.media_imagen, name='media_imagen'),
    path('admin/', admin.site.urls),
    path('api/', include('quinielas.urls')),
    path('', include(('quinielas.urls', 'quinielas'), namespace='api_root')),
]

handler400 = 'quinielas.errors.bad_request'
handler403 = 'quinielas.errors.permission_denied'
handler404 = 'quinielas.errors.not_found'
handler500 = 'quinielas.errors.server_error'
