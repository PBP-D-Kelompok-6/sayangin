from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

class UserProfile(models.Model):
    ROLE_CHOICE = (
        ('PERSONAL', 'Personal User'),
        ('LEMBAGA', 'Lembaga/Panti'),
    )

    ADDRESS_LABEL_CHOICES = (
        ('RUMAH', 'Rumah'),
        ('KOS', 'Kos'),
        ('KANTOR', 'Kantor'),
    )

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=10, choices=ROLE_CHOICE, default='PERSONAL')
    full_name = models.CharField(max_length=255, blank=True)
    address_label = models.CharField(max_length=20, choices=ADDRESS_LABEL_CHOICES, default='RUMAH', blank=True)
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=10, blank=True)
    is_primary_address = models.BooleanField(default=True)
    phone_number = models.CharField(max_length=20, blank=True)
    preferences = models.TextField(blank=True, help_text="Simpan preferensi gaya atau ukuran di sini.")

    def __str__(self) -> str:
        return f"{self.user.username} - {self.role}" # type: ignore

class InstitutionProfile(models.Model):
    class InstitutionType(models.TextChoices):
        PANTI_ASUHAN = 'PANTI_ASUHAN', 'Panti Asuhan'
        PANTI_WERDHA = 'PANTI_WERDHA', 'Panti Werdha'
        SEKOLAH = 'SEKOLAH', 'Sekolah'
        KOMUNITAS = 'KOMUNITAS', 'Komunitas'
        YAYASAN = 'YAYASAN', 'Yayasan'
        LAINNYA = 'LAINNYA', 'Lainnya'

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='institution_profile')
    name = models.CharField(max_length=255)
    institution_type = models.CharField(
        max_length=20,
        choices=InstitutionType.choices,
        default=InstitutionType.PANTI_ASUHAN,
    )
    description = models.TextField(blank=True)
    address = models.TextField()
    person_in_charge = models.CharField(max_length=255, blank=True)
    contact_phone = models.CharField(max_length=20, blank=True)
    legal_document_name = models.CharField(max_length=255, blank=True)

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