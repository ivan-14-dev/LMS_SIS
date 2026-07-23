"""App config for bourses."""
from django.apps import AppConfig


class BoursesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.bourses"
    verbose_name = "Bourses"
