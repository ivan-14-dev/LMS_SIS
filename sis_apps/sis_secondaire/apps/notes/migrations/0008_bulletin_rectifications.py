import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("notes", "0007_calculated_bulletins"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="bulletin",
            name="revision",
            field=models.PositiveIntegerField(default=1, editable=False),
        ),
        migrations.AddField(
            model_name="bulletin",
            name="rectifie",
            field=models.OneToOneField(
                blank=True,
                editable=False,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="rectification",
                to="notes.bulletin",
            ),
        ),
        migrations.AddField(
            model_name="bulletin",
            name="motif_rectification",
            field=models.TextField(blank=True, editable=False),
        ),
        migrations.AddField(
            model_name="bulletin",
            name="rectification_demandee_par",
            field=models.ForeignKey(
                blank=True,
                editable=False,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="rectifications_bulletins_demandees",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="bulletin",
            name="cle_rectification",
            field=models.UUIDField(blank=True, editable=False, null=True),
        ),
        migrations.AlterUniqueTogether(name="bulletin", unique_together=set()),
        migrations.AddConstraint(
            model_name="bulletin",
            constraint=models.UniqueConstraint(
                fields=("eleve", "periode", "revision"),
                name="unique_bulletin_revision",
            ),
        ),
        migrations.AddConstraint(
            model_name="bulletin",
            constraint=models.UniqueConstraint(
                fields=("eleve", "periode"),
                condition=models.Q(rectifie__isnull=True),
                name="unique_bulletin_original",
            ),
        ),
        migrations.AddConstraint(
            model_name="bulletin",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(
                        revision=1,
                        rectifie__isnull=True,
                        cle_rectification__isnull=True,
                        rectification_demandee_par__isnull=True,
                        motif_rectification="",
                    )
                    | (
                        models.Q(
                            revision__gt=1,
                            rectifie__isnull=False,
                            cle_rectification__isnull=False,
                            rectification_demandee_par__isnull=False,
                        )
                        & ~models.Q(motif_rectification="")
                    )
                ),
                name="bulletin_rectification_coherente",
            ),
        ),
        migrations.AlterModelOptions(
            name="bulletin",
            options={"ordering": ["-periode__date_fin", "-revision", "-pk"]},
        ),
    ]
