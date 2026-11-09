"""App config for stages."""

from django.apps import AppConfig


class StagesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.stages"
    verbose_name = "Stages"

    def ready(self):
        from sis_common.practical_legacy_guards import connect_practical_guards

        connect_practical_guards()
