import django.db.models.deletion
from django.contrib.postgres.constraints import ExclusionConstraint
from django.contrib.postgres.fields import DateTimeRangeField, RangeOperators
from django.db import migrations, models
from django.db.models import F, Func, Q, Value


class Migration(migrations.Migration):
    dependencies = [
        ("transport", "0001_initial"),
    ]

    operations = [
        migrations.RunSQL(
            "CREATE EXTENSION IF NOT EXISTS btree_gist WITH SCHEMA public;",
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.CreateModel(
            name="TrajetScolaire",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("depart_at", models.DateTimeField()),
                ("arrivee_at", models.DateTimeField()),
                (
                    "ligne",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="trajets",
                        to="transport.lignetransport",
                    ),
                ),
                (
                    "vehicule",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="trajets",
                        to="transport.vehicule",
                    ),
                ),
            ],
            options={
                "ordering": ["depart_at", "id"],
                "constraints": [
                    models.CheckConstraint(
                        condition=Q(arrivee_at__gt=F("depart_at")),
                        name="transport_trajet_positive_duration",
                    ),
                    ExclusionConstraint(
                        name="transport_trajet_vehicle_no_overlap",
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
                            ("vehicule", RangeOperators.EQUAL),
                        ],
                    ),
                ],
            },
        ),
    ]
