"""App config for enseignants."""
from django.apps import AppConfig


class EnseignantsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.enseignants"
    verbose_name = "Enseignants"
