"""App config for memoires."""

from django.apps import AppConfig


class MemoiresConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.memoires"
    verbose_name = "Memoires"
