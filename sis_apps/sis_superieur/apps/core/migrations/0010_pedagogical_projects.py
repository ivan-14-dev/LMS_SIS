import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

import sis_common.exam_files
import sis_common.project_models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0009_correspondance"),
        ("etablissement", "0003_universite_configuration_academique_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="PedagogicalProject",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("titre", models.CharField(max_length=200)),
                ("description", models.TextField(blank=True)),
                (
                    "mode",
                    models.CharField(choices=[("individuel", "Individuel"), ("collectif", "Collectif")], max_length=12),
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
                    "responsable",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="projets_pedagogiques",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "evaluateurs",
                    models.ManyToManyField(blank=True, related_name="projets_a_evaluer", to=settings.AUTH_USER_MODEL),
                ),
                (
                    "etablissement",
                    models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="etablissement.universite"),
                ),
            ],
            options={
                "abstract": False,
                "ordering": ["-updated_at", "id"],
                "permissions": [
                    ("gerer_projet_pedagogique", "Organiser les projets pédagogiques et leurs équipes"),
                    ("evaluer_projet_pedagogique", "Évaluer les projets pédagogiques explicitement confiés"),
                ],
                "constraints": [
                    models.CheckConstraint(
                        condition=models.Q(mode__in=["individuel", "collectif"]), name="project_mode"
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="ProjectTeam",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("nom", models.CharField(max_length=120)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "projet",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="equipes",
                        to="core.pedagogicalproject",
                    ),
                ),
                (
                    "cree_par",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT, related_name="+", to=settings.AUTH_USER_MODEL
                    ),
                ),
            ],
            options={
                "abstract": False,
                "ordering": ["created_at", "id"],
                "constraints": [models.UniqueConstraint(fields=("projet", "nom"), name="project_team_name")],
            },
        ),
        migrations.CreateModel(
            name="ProjectMembership",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("retired_at", models.DateTimeField(blank=True, null=True)),
                (
                    "equipe",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT, related_name="appartenances", to="core.projectteam"
                    ),
                ),
                (
                    "membre",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT, related_name="+", to=settings.AUTH_USER_MODEL
                    ),
                ),
                (
                    "ajoute_par",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT, related_name="+", to=settings.AUTH_USER_MODEL
                    ),
                ),
                (
                    "retire_par",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "abstract": False,
                "ordering": ["created_at", "id"],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("equipe", "membre"),
                        condition=models.Q(retired_at__isnull=True),
                        name="project_active_member",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(retired_at__isnull=True, retire_par__isnull=True)
                        | models.Q(retired_at__isnull=False, retire_par__isnull=False),
                        name="project_retirement_actor",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="ProjectMilestone",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("titre", models.CharField(max_length=200)),
                ("consignes", models.TextField(blank=True)),
                ("ordre", models.PositiveIntegerField()),
                ("echeance", models.DateTimeField()),
                ("bareme", models.DecimalField(decimal_places=2, max_digits=7)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "projet",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT, related_name="jalons", to="core.pedagogicalproject"
                    ),
                ),
                (
                    "cree_par",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT, related_name="+", to=settings.AUTH_USER_MODEL
                    ),
                ),
            ],
            options={
                "abstract": False,
                "ordering": ["ordre", "id"],
                "constraints": [
                    models.UniqueConstraint(fields=("projet", "ordre"), name="project_milestone_order"),
                    models.CheckConstraint(
                        condition=models.Q(bareme__gt=0, bareme__lte=10000), name="project_positive_scale"
                    ),
                    models.CheckConstraint(condition=models.Q(ordre__gte=1), name="project_positive_order"),
                ],
            },
        ),
        migrations.CreateModel(
            name="ProjectDelivery",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("revision", models.PositiveIntegerField()),
                (
                    "fichier",
                    models.FileField(
                        max_length=255,
                        storage=sis_common.exam_files.PrivateExamStorage(),
                        upload_to=sis_common.project_models.project_delivery_path,
                        validators=[sis_common.exam_files.validate_exam_copy],
                    ),
                ),
                ("nom", models.CharField(max_length=200)),
                ("taille", models.PositiveIntegerField()),
                ("sha256", models.CharField(max_length=64)),
                ("commentaire", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "equipe",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT, related_name="livrables", to="core.projectteam"
                    ),
                ),
                (
                    "jalon",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="livrables",
                        to="core.projectmilestone",
                    ),
                ),
                (
                    "depose_par",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT, related_name="+", to=settings.AUTH_USER_MODEL
                    ),
                ),
            ],
            options={
                "abstract": False,
                "ordering": ["-created_at", "id"],
                "constraints": [
                    models.UniqueConstraint(fields=("equipe", "jalon", "revision"), name="project_delivery_revision")
                ],
            },
        ),
        migrations.CreateModel(
            name="ProjectEvaluation",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("revision", models.PositiveIntegerField()),
                ("note_groupe", models.DecimalField(decimal_places=2, max_digits=7)),
                ("commentaire", models.TextField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("published_at", models.DateTimeField(blank=True, null=True)),
                (
                    "equipe",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT, related_name="evaluations", to="core.projectteam"
                    ),
                ),
                (
                    "jalon",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="evaluations",
                        to="core.projectmilestone",
                    ),
                ),
                (
                    "evalue_par",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT, related_name="+", to=settings.AUTH_USER_MODEL
                    ),
                ),
                (
                    "publie_par",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "abstract": False,
                "ordering": ["-created_at", "id"],
                "constraints": [
                    models.UniqueConstraint(fields=("equipe", "jalon", "revision"), name="project_evaluation_revision"),
                    models.CheckConstraint(
                        condition=models.Q(note_groupe__gte=0), name="project_group_score_nonnegative"
                    ),
                    models.CheckConstraint(
                        condition=models.Q(published_at__isnull=True, publie_par__isnull=True)
                        | models.Q(published_at__isnull=False, publie_par__isnull=False),
                        name="project_publication_actor",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="ProjectContribution",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("note", models.DecimalField(decimal_places=2, max_digits=7)),
                ("commentaire", models.TextField()),
                (
                    "evaluation",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="contributions",
                        to="core.projectevaluation",
                    ),
                ),
                (
                    "appartenance",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT, related_name="+", to="core.projectmembership"
                    ),
                ),
            ],
            options={
                "abstract": False,
                "ordering": ["id"],
                "constraints": [
                    models.UniqueConstraint(fields=("evaluation", "appartenance"), name="project_contribution_member"),
                    models.CheckConstraint(
                        condition=models.Q(note__gte=0), name="project_individual_score_nonnegative"
                    ),
                ],
            },
        ),
    ]
