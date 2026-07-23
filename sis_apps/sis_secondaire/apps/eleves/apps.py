"""App config for eleves."""
from django.apps import AppConfig


class ElevesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.eleves"
    verbose_name = "Eleves"
