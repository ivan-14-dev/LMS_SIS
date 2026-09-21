from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="WorkflowEvent",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("tenant_id", models.PositiveIntegerField(blank=True, null=True)),
                ("request_id", models.CharField(blank=True, max_length=64)),
                ("app_label", models.CharField(max_length=64)),
                ("model", models.CharField(max_length=64)),
                ("object_id", models.CharField(max_length=64)),
                ("object_repr", models.CharField(max_length=255)),
                ("action", models.CharField(max_length=64)),
                ("title", models.CharField(max_length=255)),
                ("message", models.TextField(blank=True)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "actor",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="workflow_events_created",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="WorkflowNotification",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("category", models.CharField(max_length=64)),
                ("title", models.CharField(max_length=255)),
                ("message", models.TextField()),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("is_read", models.BooleanField(default=False)),
                ("read_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "event",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="notifications",
                        to="core.workflowevent",
                    ),
                ),
                (
                    "recipient",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="workflow_notifications",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.AddIndex(
            model_name="workflowevent",
            index=models.Index(
                fields=["app_label", "model", "object_id"],
                name="core_workfl_app_lab_59e6ad_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="workflowevent",
            index=models.Index(
                fields=["action", "created_at"],
                name="core_workfl_action_6b80c1_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="workflownotification",
            index=models.Index(
                fields=["recipient", "is_read", "created_at"],
                name="core_workfl_recipie_4eb2b3_idx",
            ),
        ),
    ]
