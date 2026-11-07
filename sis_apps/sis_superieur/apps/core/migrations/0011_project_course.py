import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0010_pedagogical_projects"),
        ("integration", "0007_grade_review"),
    ]

    operations = [
        migrations.AddField(
            model_name="pedagogicalproject",
            name="cours",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="projets",
                to="integration.edxcoursemapping",
            ),
        ),
    ]
