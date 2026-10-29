from django.db import models
from django.contrib.auth.models import User


class SaleListing(models.Model):
    PUBLISHED = "published"
    STATUS_CHOICES = ((PUBLISHED, "Tayang"),)
    owner = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    source_item = models.ForeignKey(
        "WardrobeItem",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="sale_listings",
    )
    title = models.CharField(max_length=160, blank=True)
    category = models.CharField(max_length=80, blank=True)
    size = models.CharField(max_length=40, blank=True)
    condition = models.CharField(max_length=30, blank=True)
    condition_notes = models.TextField(blank=True, max_length=2000)
    price = models.PositiveIntegerField(null=True, blank=True)
    weight = models.PositiveIntegerField(null=True, blank=True)
    shipped_from = models.CharField(max_length=120, blank=True, default="Depok")
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


class WardrobeItem(models.Model):
    owner = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    name = models.CharField(max_length=160)
    category = models.CharField(max_length=80)
    size = models.CharField(max_length=40, blank=True)
    last_used = models.CharField(max_length=40)
    color = models.CharField(max_length=80, blank=True)
    purchased_at = models.CharField(max_length=40, blank=True)
    notes = models.TextField(blank=True, max_length=2000)
    photo = models.FileField(upload_to="lemari/wardrobe/", blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
