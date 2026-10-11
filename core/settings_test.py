from .settings import *  # noqa: F403

SECRET_KEY = 'test-only-key-not-for-production-' * 3
DEBUG = False
ALLOWED_HOSTS = ['testserver', 'localhost']
DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}}
if os.getenv('TEST_DATABASE_URL'):
    DATABASES = {'default': dj_database_url.parse(os.environ['TEST_DATABASE_URL'], conn_max_age=0)}
SECURE_SSL_REDIRECT = False
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
PASSWORD_RESET_URL = 'https://app.example.test/reset'
PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
REST_FRAMEWORK = {**REST_FRAMEWORK, 'DEFAULT_THROTTLE_RATES': {
    'auth': '10000/min', 'password_reset': '10000/hour',
}}
