# Generated manually: the 'data' column already exists in the database
# (legacy column), but the model was missing the field definition.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("user", "0041_simplify_equipamento"),
    ]

    operations = [
        migrations.AddField(
            model_name="apontamento",
            name="data",
            field=models.DateField(verbose_name="Data"),
        ),
    ]
