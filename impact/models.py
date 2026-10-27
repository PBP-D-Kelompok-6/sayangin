from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


class Challenge(models.Model):
    KIND_CHOICES = [
        ("terjual", "Barang preloved terjual"),
        ("dibeli", "Membeli barang preloved"),
        ("donasi", "Donasi diterima lembaga"),
        ("lemari", "Barang dicatat di lemari"),
    ]

    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="impact_challenges")
    title = models.CharField(max_length=120)
    kind = models.CharField(max_length=20, choices=KIND_CHOICES)
    target = models.PositiveSmallIntegerField(default=3)
    start_date = models.DateField()
    end_date = models.DateField()

    class Meta:
        ordering = ["-start_date"]

    def __str__(self):
        return self.title

    @property
    def is_running(self):
        return self.end_date >= timezone.localdate()