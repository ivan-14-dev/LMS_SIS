"""App config for utilisateurs."""
from django.apps import AppConfig


class UtilisateursConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.utilisateurs"
    verbose_name = "Utilisateurs"
