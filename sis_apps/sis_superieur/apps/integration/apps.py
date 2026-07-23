"""App config for integration."""
from django.apps import AppConfig


class IntegrationConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.integration"
    verbose_name = "Integration"
