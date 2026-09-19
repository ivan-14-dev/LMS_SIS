"""App config for bibliotheque."""

from django.apps import AppConfig


class BibliothequeConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.bibliotheque"
    verbose_name = "Bibliotheque"
