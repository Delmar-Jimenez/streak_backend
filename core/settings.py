import os
from datetime import timedelta
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')


def env_bool(name, default=False):
    return os.getenv(name, str(default)).lower() in ('true', '1', 'yes')


def env_list(name, default=''):
    return [value.strip() for value in os.getenv(name, default).split(',') if value.strip()]


DEBUG = env_bool('DEBUG')
TESTING = os.getenv('DJANGO_SETTINGS_MODULE') == 'core.settings_test'
SECRET_KEY = os.getenv('SECRET_KEY', '')
ALLOWED_HOSTS = env_list('ALLOWED_HOSTS', 'localhost,127.0.0.1' if DEBUG else '')
if not SECRET_KEY and not TESTING:
    raise ImproperlyConfigured('Configura SECRET_KEY en el entorno.')
if not DEBUG and not TESTING:
    if len(SECRET_KEY) < 50 or SECRET_KEY.startswith('django-insecure-'):
        raise ImproperlyConfigured('SECRET_KEY debe ser aleatoria y tener al menos 50 caracteres.')
    if not ALLOWED_HOSTS or '*' in ALLOWED_HOSTS:
        raise ImproperlyConfigured('Configura ALLOWED_HOSTS con los dominios de produccion.')
    if not os.getenv('DATABASE_URL', '').startswith(('postgres://', 'postgresql://')):
        raise ImproperlyConfigured('Produccion requiere DATABASE_URL de PostgreSQL.')

INSTALLED_APPS = [
    'django.contrib.admin', 'django.contrib.auth', 'django.contrib.contenttypes',
    'django.contrib.sessions', 'django.contrib.messages', 'django.contrib.staticfiles',
    'anymail', 'corsheaders', 'rest_framework', 'rest_framework_simplejwt', 'quinielas.apps.QuinielasConfig',
]
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'quinielas.middleware.ZonaHorariaAdminMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]
ROOT_URLCONF = 'core.urls'
TEMPLATES = [{
    'BACKEND': 'django.template.backends.django.DjangoTemplates', 'DIRS': [], 'APP_DIRS': True,
    'OPTIONS': {'context_processors': [
        'django.template.context_processors.request', 'django.contrib.auth.context_processors.auth',
        'django.contrib.messages.context_processors.messages',
    ]},
}]
WSGI_APPLICATION = 'core.wsgi.application'
DATABASES = {'default': dj_database_url.config(
    default=f'sqlite:///{BASE_DIR / "db.sqlite3"}', conn_max_age=600, conn_health_checks=True,
)}
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': f'django.contrib.auth.password_validation.{name}'} for name in (
        'UserAttributeSimilarityValidator', 'MinimumLengthValidator',
        'CommonPasswordValidator', 'NumericPasswordValidator',
    )
]
AUTH_USER_MODEL = 'quinielas.Usuario'
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.Argon2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',
]
LANGUAGE_CODE = 'es'
TIME_ZONE = 'UTC'
# Zona horaria del panel /admin/ (la API y la base de datos siguen en UTC).
ADMIN_TIME_ZONE = os.getenv('ADMIN_TIME_ZONE', 'America/Guatemala')
USE_I18N = True
USE_TZ = True
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
MEDIA_URL = '/media/'
MEDIA_ROOT = Path(os.getenv('MEDIA_ROOT', str(BASE_DIR / 'media')))
STORAGES = {
    'default': {'BACKEND': 'quinielas.storage.DatabaseImageStorage'},
    'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage'},
}
CORS_ALLOWED_ORIGINS = env_list('CORS_ALLOWED_ORIGINS')
CORS_URLS_REGEX = r'^/(api/|auth/|usuarios/|torneos/?|partidos/|quinielas/?|pro/)'
CSRF_TRUSTED_ORIGINS = env_list('CSRF_TRUSTED_ORIGINS')
SECURE_SSL_REDIRECT = env_bool('SECURE_SSL_REDIRECT', not DEBUG)
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_HSTS_SECONDS = int(os.getenv('SECURE_HSTS_SECONDS', '31536000' if not DEBUG else '0'))
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool('SECURE_HSTS_INCLUDE_SUBDOMAINS')
SECURE_HSTS_PRELOAD = env_bool('SECURE_HSTS_PRELOAD')
if env_bool('TRUST_PROXY_HTTPS'):
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

EMAIL_BACKEND = os.getenv('EMAIL_BACKEND', 'anymail.backends.resend.EmailBackend')
ANYMAIL = {
    'RESEND_API_KEY': os.getenv('RESEND_API_KEY', ''),
    'BREVO_API_KEY': os.getenv('BREVO_API_KEY', ''),
    'REQUESTS_TIMEOUT': 10,
}
EMAIL_HOST = os.getenv('EMAIL_HOST', 'localhost')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', '587'))
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')
EMAIL_USE_TLS = env_bool('EMAIL_USE_TLS', True)
EMAIL_TIMEOUT = 10
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', '')
PASSWORD_RESET_TIMEOUT = 3600
PASSWORD_RESET_URL = os.getenv('PASSWORD_RESET_URL', '')
PASSWORD_RESET_APP_URL = os.getenv('PASSWORD_RESET_APP_URL', '')
DATA_UPLOAD_MAX_MEMORY_SIZE = 6 * 1024 * 1024

STRIPE_SECRET_KEY = os.getenv('STRIPE_SECRET_KEY', '')
STRIPE_WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET', '')
STRIPE_LIVE_MODE = env_bool('STRIPE_LIVE_MODE', False)
STRIPE_PRO_AMOUNT = int(os.getenv('STRIPE_PRO_AMOUNT', '500'))
STRIPE_CURRENCY = os.getenv('STRIPE_CURRENCY', 'usd').lower()

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': ('rest_framework_simplejwt.authentication.JWTAuthentication',),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated', 'quinielas.permissions.IsPasswordNotTemporal',
    ),
    'DEFAULT_RENDERER_CLASSES': ('rest_framework.renderers.JSONRenderer',),
    'EXCEPTION_HANDLER': 'quinielas.errors.exception_handler',
    'DEFAULT_THROTTLE_CLASSES': ('rest_framework.throttling.ScopedRateThrottle',),
    'DEFAULT_THROTTLE_RATES': {'auth': '10/min', 'password_reset': '5/hour'},
}
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=15),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'CHECK_REVOKE_TOKEN': True,
}
