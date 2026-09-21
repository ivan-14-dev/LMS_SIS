from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("eleves", "0004_affectationmatiereindividuelle"),
        ("notes", "0002_evaluation_ponderation_alter_evaluation_type_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="evaluation",
            name="eleve_cible",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.SET_NULL,
                related_name="evaluations_individualisees",
                to="eleves.eleve",
            ),
        ),
        migrations.AddIndex(
            model_name="evaluation",
            index=models.Index(fields=["eleve_cible", "date"], name="notes_evalu_eleve_c_f95df4_idx"),
        ),
    ]
