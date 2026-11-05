from django.apps import AppConfig


class SISProvisioningConfig(AppConfig):
    name = "sis_provisioning"
    default_auto_field = "django.db.models.BigAutoField"
    plugin_app = {
        "url_config": {
            "lms.djangoapp": {
                "namespace": "sis_provisioning",
                "regex": r"^api/sis/v1/",
                "relative_path": "urls",
            },
            "cms.djangoapp": {
                "namespace": "sis_provisioning",
                "regex": r"^api/sis/v1/",
                "relative_path": "course_urls",
            },
        }
    }
