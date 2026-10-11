from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('quinielas.urls')),
    path('', include(('quinielas.urls', 'quinielas'), namespace='api_root')),
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

handler400 = 'quinielas.errors.bad_request'
handler403 = 'quinielas.errors.permission_denied'
handler404 = 'quinielas.errors.not_found'
handler500 = 'quinielas.errors.server_error'
