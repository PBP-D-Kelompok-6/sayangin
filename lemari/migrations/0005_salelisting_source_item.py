from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("lemari", "0004_merge_0002_branches")]

    operations = [
        migrations.AddField(
            model_name="salelisting",
            name="source_item",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="sale_listings", to="lemari.wardrobeitem"),
        ),
    ]
