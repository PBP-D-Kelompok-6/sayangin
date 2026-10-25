from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

class UserProfile(models.Model):
    ROLE_CHOICE = (
        ('PERSONAL', 'Personal User'),
        ('LEMBAGA', 'Lembaga/Panti'),
    )

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=10, choices=ROLE_CHOICE, default='PERSONAL')
    full_name = models.CharField(max_length=255, blank=True)
    address = models.TextField(blank=True)
    phone_number = models.CharField(max_length=20, blank=True)
    preferences = models.TextField(blank=True, help_text="Simpan preferensi gaya atau ukuran di sini.")

    def __str__(self) -> str:
        return f"{self.user.username} - {self.role}"

class InstitutionProfile(models.Model):
    class InstitutionType(models.TextChoices):
        PANTI_ASUHAN = 'PANTI_ASUHAN', 'Panti Asuhan'
        SEKOLAH = 'SEKOLAH', "SEKOLAH"
        YAYASAN = "YAYASAN", "Yayasan"
        LAINNYA = "LAINNYA", "Lainnya"

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='institution_profile')
    name = models.CharField(max_length=255)
    institution_type = models.CharField(max_length=20, choices=InstitutionType.choices)
    description = models.TextField(blank=True)
    address = models.TextField()
    contact_phone = models.CharField(max_length=20, blank=True)

    beneficiaries_count = models.PositiveIntegerField(null=True, blank=True)
    founded_year = models.PositiveSmallIntegerField(null=True, blank=True)

    is_verified = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return self.name

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.get_or_create(user=instance)