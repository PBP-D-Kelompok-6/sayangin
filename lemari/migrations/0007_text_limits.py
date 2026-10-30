from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("lemari", "0006_wardrobeitem_details")]

    operations = [
        migrations.AlterField(
            model_name="wardrobeitem",
            name="notes",
            field=models.TextField(blank=True, max_length=2000),
        ),
        migrations.AlterField(
            model_name="salelisting",
            name="condition_notes",
            field=models.TextField(blank=True, max_length=2000),
        ),
    ]
