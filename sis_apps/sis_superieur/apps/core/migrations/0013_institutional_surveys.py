import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0012_project_competencies"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="InstitutionalSurvey",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("titre", models.CharField(max_length=200)),
                ("description", models.TextField(blank=True)),
                (
                    "politique",
                    models.CharField(choices=[("nominative", "Nominative")], default="nominative", max_length=12),
                ),
                ("questionnaire", models.JSONField()),
                (
                    "statut",
                    models.CharField(
                        choices=[("brouillon", "Brouillon"), ("publiee", "Publiée"), ("fermee", "Fermée")],
                        default="brouillon",
                        max_length=10,
                    ),
                ),
                ("version", models.PositiveIntegerField(default=1)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "cree_par",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT, related_name="+", to=settings.AUTH_USER_MODEL
                    ),
                ),
                (
                    "etablissement",
                    models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="etablissement.universite"),
                ),
            ],
            options={
                "ordering": ["-created_at", "id"],
                "abstract": False,
                "default_permissions": (),
                "permissions": [
                    (
                        "gerer_enquete_institutionnelle",
                        "Gérer les enquêtes institutionnelles nominatives et leurs résultats",
                    )
                ],
                "constraints": [
                    models.CheckConstraint(condition=models.Q(politique="nominative"), name="survey_nominative"),
                    models.CheckConstraint(
                        condition=models.Q(statut__in=["brouillon", "publiee", "fermee"]), name="survey_status"
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="SurveyRecipient",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("revoked_at", models.DateTimeField(blank=True, null=True)),
                (
                    "enquete",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="destinataires",
                        to="core.institutionalsurvey",
                    ),
                ),
                (
                    "utilisateur",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT, related_name="+", to=settings.AUTH_USER_MODEL
                    ),
                ),
            ],
            options={
                "ordering": ["id"],
                "abstract": False,
                "default_permissions": (),
                "constraints": [
                    models.UniqueConstraint(fields=("enquete", "utilisateur"), name="survey_unique_recipient")
                ],
            },
        ),
        migrations.CreateModel(
            name="SurveyResponse",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("reponses", models.JSONField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "destinataire",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.PROTECT, related_name="reponse", to="core.surveyrecipient"
                    ),
                ),
            ],
            options={"ordering": ["created_at", "id"], "abstract": False, "default_permissions": ()},
        ),
    ]
