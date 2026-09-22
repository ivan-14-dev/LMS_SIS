"""AppConfig for the SIS grade webhooks Django app."""
from django.apps import AppConfig


class SisGradeWebhooksConfig(AppConfig):
    name = "openedx.core.djangoapps.sis_grade_webhooks"

    def ready(self):
        from . import receivers  # pylint: disable=unused-import  # noqa: F401
