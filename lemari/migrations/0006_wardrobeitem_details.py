from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("lemari", "0005_salelisting_source_item")]

    operations = [
        migrations.AddField(
            model_name="wardrobeitem",
            name="size",
            field=models.CharField(blank=True, max_length=40),
        ),
        migrations.AddField(
            model_name="wardrobeitem",
            name="color",
            field=models.CharField(blank=True, max_length=80),
        ),
        migrations.AddField(
            model_name="wardrobeitem",
            name="purchased_at",
            field=models.CharField(blank=True, max_length=40),
        ),
        migrations.AddField(
            model_name="wardrobeitem",
            name="notes",
            field=models.TextField(blank=True),
        ),
    ]
