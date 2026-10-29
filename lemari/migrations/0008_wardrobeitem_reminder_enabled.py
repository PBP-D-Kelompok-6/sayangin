from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("lemari", "0007_text_limits")]

    operations = [
        migrations.AddField(
            model_name="wardrobeitem",
            name="reminder_enabled",
            field=models.BooleanField(default=True),
        ),
    ]
