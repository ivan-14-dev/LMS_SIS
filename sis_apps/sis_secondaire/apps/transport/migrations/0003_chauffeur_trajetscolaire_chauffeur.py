import django.db.models.deletion
from django.contrib.postgres.constraints import ExclusionConstraint
from django.contrib.postgres.fields import DateTimeRangeField, RangeOperators
from django.db import migrations, models
from django.db.models import F, Func, Q, Value


class Migration(migrations.Migration):
    dependencies = [
        ("transport", "0002_trajetscolaire"),
    ]

    operations = [
        migrations.CreateModel(
            name="Chauffeur",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nom", models.CharField(max_length=200)),
                ("telephone", models.CharField(blank=True, max_length=20)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "ordering": ["nom", "id"],
                "verbose_name": "Chauffeur",
                "verbose_name_plural": "Chauffeurs",
            },
        ),
        migrations.AddField(
            model_name="trajetscolaire",
            name="chauffeur",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="trajets",
                to="transport.chauffeur",
            ),
        ),
        migrations.AddConstraint(
            model_name="trajetscolaire",
            constraint=ExclusionConstraint(
                name="transport_trajet_driver_no_overlap",
                expressions=[
                    (
                        Func(
                            F("depart_at"),
                            F("arrivee_at"),
                            Value("[)"),
                            function="TSTZRANGE",
                            output_field=DateTimeRangeField(),
                        ),
                        RangeOperators.OVERLAPS,
                    ),
                    ("chauffeur", RangeOperators.EQUAL),
                ],
                condition=Q(chauffeur__isnull=False),
            ),
        ),
    ]
