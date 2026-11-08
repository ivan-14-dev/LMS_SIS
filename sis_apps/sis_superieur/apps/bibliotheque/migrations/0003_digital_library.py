from django.db import migrations, models

import sis_common.exam_files
import sis_common.library_files


class Migration(migrations.Migration):
    dependencies = [("bibliotheque", "0002_initial")]

    operations = [
        migrations.AlterModelOptions(
            name="livre",
            options={
                "ordering": ["titre"],
                "verbose_name": "Livre",
                "verbose_name_plural": "Livres",
                "permissions": [("consulter_ressource_numerique", "Consulter une ressource numérique sous licence")],
            },
        ),
        migrations.AddField(model_name="livre", name="licence_active", field=models.BooleanField(default=False)),
        migrations.AddField(
            model_name="livre", name="licence_reference", field=models.CharField(blank=True, max_length=1000)
        ),
        migrations.AddField(
            model_name="livre", name="licence_expire_le", field=models.DateField(blank=True, null=True)
        ),
        migrations.AlterField(
            model_name="livre",
            name="ressource_numerique",
            field=models.FileField(
                blank=True,
                null=True,
                max_length=255,
                storage=sis_common.library_files.PrivateLibraryStorage(),
                upload_to=sis_common.library_files.library_upload_to,
                validators=[sis_common.exam_files.validate_exam_copy],
            ),
        ),
    ]
