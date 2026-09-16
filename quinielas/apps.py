from django.apps import AppConfig

class QuinielasConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'quinielas'

    def ready(self):
        import quinielas.signals
