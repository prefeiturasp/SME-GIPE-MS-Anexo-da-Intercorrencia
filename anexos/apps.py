from django.apps import AppConfig


class AnexosConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'anexos'
    
    def ready(self):
        # importa a extensão para registrá-la no ciclo de vida do Django
        import anexos.spectacular_ext  # noqa: F401