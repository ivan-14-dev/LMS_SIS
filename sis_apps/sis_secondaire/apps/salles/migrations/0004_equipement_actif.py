from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("salles", "0003_indisponibilitesalle"),
    ]

    operations = [
        migrations.AddField(
            model_name="equipement",
            name="actif",
            field=models.BooleanField(default=True),
        ),
        migrations.AddConstraint(
            model_name="equipement",
            constraint=models.CheckConstraint(
                condition=models.Q(actif=True) | models.Q(salle__isnull=True),
                name="salles_equipement_inactif_sans_salle",
            ),
        ),
    ]
