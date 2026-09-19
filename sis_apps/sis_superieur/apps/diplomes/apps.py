"""App config for diplomes."""

from django.apps import AppConfig


class DiplomesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.diplomes"
    verbose_name = "Diplomes"
