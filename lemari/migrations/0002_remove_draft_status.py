from django.db import migrations, models


def publish_existing_drafts(apps, schema_editor):
    SaleListing = apps.get_model("lemari", "SaleListing")
    SaleListing.objects.filter(status="draft").update(status="published")


class Migration(migrations.Migration):
    dependencies = [("lemari", "0001_salelisting_listingphoto")]

    operations = [
        migrations.RunPython(publish_existing_drafts, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="salelisting",
            name="status",
            field=models.CharField(choices=[("published", "Tayang")], default="published", max_length=12),
        ),
    ]
