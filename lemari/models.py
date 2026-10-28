from django.db import models
from django.contrib.auth.models import User


class SaleListing(models.Model):
    PUBLISHED = "published"
    STATUS_CHOICES = ((PUBLISHED, "Tayang"),)
    owner = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    title = models.CharField(max_length=160, blank=True)
    category = models.CharField(max_length=80, blank=True)
    size = models.CharField(max_length=40, blank=True)
    condition = models.CharField(max_length=30, blank=True)
    condition_notes = models.TextField(blank=True)
    price = models.PositiveIntegerField(null=True, blank=True)
    weight = models.PositiveIntegerField(null=True, blank=True)
    shipped_from = models.CharField(
        max_length=120, blank=True, default="Alamat utama · Jakarta Selatan"
    )
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=PUBLISHED)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-updated_at",)


class ListingPhoto(models.Model):
    listing = models.ForeignKey(
        SaleListing, related_name="photos", on_delete=models.CASCADE
    )
    image = models.FileField(upload_to="lemari/listings/")
    uploaded_at = models.DateTimeField(auto_now_add=True)
