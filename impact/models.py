from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone

# Ngaruh ke:
# 1. views.py: CRUD-nya.
# 2. admin.py.
# 3. challenge_list.html: memakai is_running dan get_kind_display.
# ! Kode kind harus sama dengan key SOURCES di sources.py.

# forms.py : form dibuat dari model ini
class Challenge(models.Model):
    # Pilihan jenis tantangan:
    KIND_CHOICES = [
        ("terjual", "Barang preloved terjual"),
        ("dibeli", "Membeli barang preloved"),
        ("donasi", "Donasi diterima lembaga"),
        ("lemari", "Barang dicatat di lemari"),
    ]

    # fields
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="impact_challenges")
    title = models.CharField(max_length=120) # Judul tantangan
    kind = models.CharField(max_length=20, choices=KIND_CHOICES) # Jenis aksi
    target = models.PositiveSmallIntegerField(default=3) # Target, dengan default 3
    start_date = models.DateField() # Mulai tantangan
    end_date = models.DateField() # Berakhirnya tantangan

    class Meta:
        ordering = ["-start_date"] 
        # urutkan dari yang terbaru tanggalnya

    def __str__(self):
        return self.title

    # challenge_list.html: memakai is_running dan get_kind_display.
    @property
    def is_running(self):
        return self.end_date >= timezone.localdate() 
        # true, jika end_date >= hari ini