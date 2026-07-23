"""App config for structure."""
from django.apps import AppConfig


class StructureConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.structure"
    verbose_name = "Structure"
