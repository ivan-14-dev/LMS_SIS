"""App config for cantine."""

from django.apps import AppConfig


class CantineConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.cantine"
    verbose_name = "Cantine"
