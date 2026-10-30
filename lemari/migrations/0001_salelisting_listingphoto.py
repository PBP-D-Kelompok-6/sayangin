from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True
    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(
            name="SaleListing",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(blank=True, max_length=160)),
                ("category", models.CharField(blank=True, max_length=80)),
                ("size", models.CharField(blank=True, max_length=40)),
                ("condition", models.CharField(blank=True, max_length=30)),
                ("condition_notes", models.TextField(blank=True)),
                ("price", models.PositiveIntegerField(blank=True, null=True)),
                ("weight", models.PositiveIntegerField(blank=True, null=True)),
                ("shipped_from", models.CharField(default="Alamat utama · Jakarta Selatan", max_length=120)),
                ("status", models.CharField(choices=[("draft", "Draf"), ("published", "Tayang")], default="draft", max_length=12)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("owner", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ("-updated_at",)},
        ),
        migrations.CreateModel(
            name="ListingPhoto",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("image", models.FileField(upload_to="lemari/listings/")),
                ("uploaded_at", models.DateTimeField(auto_now_add=True)),
                ("listing", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="photos", to="lemari.salelisting")),
            ],
        ),
    ]
