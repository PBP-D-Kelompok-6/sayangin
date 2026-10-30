import json
from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver


RAJAONGKIR_CITY_MAP = {
    'jakarta selatan': ('153', '6', 'DKI Jakarta'),
    'jakarta pusat': ('152', '6', 'DKI Jakarta'),
    'jakarta barat': ('151', '6', 'DKI Jakarta'),
    'jakarta timur': ('154', '6', 'DKI Jakarta'),
    'jakarta utara': ('155', '6', 'DKI Jakarta'),
    'depok': ('115', '9', 'Jawa Barat'),
    'bogor': ('79', '9', 'Jawa Barat'),
    'bekasi': ('55', '9', 'Jawa Barat'),
    'bandung': ('23', '9', 'Jawa Barat'),
    'tangerang': ('456', '3', 'Banten'),
    'tangerang selatan': ('457', '3', 'Banten'),
    'surabaya': ('444', '11', 'Jawa Timur'),
    'malang': ('256', '11', 'Jawa Timur'),
    'yogyakarta': ('501', '5', 'DI Yogyakarta'),
    'semarang': ('399', '10', 'Jawa Tengah'),
    'surakarta': ('445', '10', 'Jawa Tengah'),
    'medan': ('278', '34', 'Sumatera Utara'),
    'denpasar': ('114', '1', 'Bali'),
    'makassar': ('254', '28', 'Sulawesi Selatan'),
}


def resolve_rajaongkir_city(city_name: str):
    if not city_name:
        return ('', '', '')
    key = city_name.strip().lower()
    if key in RAJAONGKIR_CITY_MAP:
        return RAJAONGKIR_CITY_MAP[key]
    for map_key, val in RAJAONGKIR_CITY_MAP.items():
        if map_key in key or key in map_key:
            return val
    return ('', '', '')


class UserProfile(models.Model):
    ROLE_CHOICE = (
        ('PERSONAL', 'Personal User'),
        ('LEMBAGA', 'Lembaga/Panti'),
    )

    ADDRESS_LABEL_CHOICES = (
        ('RUMAH', 'Rumah'),
        ('KOS', 'Kos'),
        ('APARTEMEN', 'Apartemen'),
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
    google_connected = models.BooleanField(default=False)
    google_email = models.EmailField(blank=True)
    password_updated_at = models.DateTimeField(null=True, blank=True)

    def get_preferences_dict(self) -> dict:
        default_prefs = {
            'sizes': ['M'],
            'categories': ['Atasan', 'Tas'],
            'reminder': True,
            'email_newsletter': False,
            'reminder_enabled': True,
            'email_news_enabled': False,
        }
        if not self.preferences:
            return default_prefs
        try:
            data = json.loads(self.preferences)
            if isinstance(data, dict):
                rem = bool(data.get('reminder', data.get('reminder_enabled', True)))
                em = bool(data.get('email_newsletter', data.get('email_news_enabled', False)))
                return {
                    'sizes': data.get('sizes', default_prefs['sizes']),
                    'categories': data.get('categories', default_prefs['categories']),
                    'reminder': rem,
                    'email_newsletter': em,
                    'reminder_enabled': rem,
                    'email_news_enabled': em,
                }
        except (ValueError, TypeError):
            pass
        return default_prefs

    def __str__(self) -> str:
        return f"{self.user.username} - {self.role}" # type: ignore


class UserAddress(models.Model):
    ADDRESS_LABEL_CHOICES = UserProfile.ADDRESS_LABEL_CHOICES

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='addresses')
    label = models.CharField(max_length=20, choices=ADDRESS_LABEL_CHOICES, default='RUMAH')
    recipient_name = models.CharField(max_length=255, blank=True)
    phone_number = models.CharField(max_length=20, blank=True)
    address = models.TextField()
    city = models.CharField(max_length=100)
    province = models.CharField(max_length=100, blank=True)
    rajaongkir_city_id = models.CharField(
        max_length=20,
        blank=True,
        help_text="ID kota RajaOngkir untuk kalkulasi ongkir otomatis.",
    )
    rajaongkir_province_id = models.CharField(max_length=20, blank=True)
    postal_code = models.CharField(max_length=10, blank=True)
    is_primary = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-is_primary', '-updated_at', '-id']

    @property
    def formatted_address(self) -> str:
        parts = [p for p in [self.address, self.city] if p]
        joined = ", ".join(parts)
        if self.postal_code:
            joined = f"{joined} {self.postal_code}".strip()
        return joined

    def to_dict(self) -> dict:
        return {
            'id': self.pk,
            'label': self.label,
            'label_display': self.get_label_display(), # type: ignore
            'recipient_name': self.recipient_name,
            'phone_number': self.phone_number,
            'address': self.address,
            'city': self.city,
            'province': self.province,
            'rajaongkir_city_id': self.rajaongkir_city_id,
            'rajaongkir_province_id': self.rajaongkir_province_id,
            'postal_code': self.postal_code,
            'is_primary': self.is_primary,
            'formatted_address': self.formatted_address,
        }

    def save(self, *args, **kwargs):
        city_id, prov_id, prov_name = resolve_rajaongkir_city(self.city)
        if city_id:
            self.rajaongkir_city_id = city_id
            self.rajaongkir_province_id = prov_id
            if not self.province:
                self.province = prov_name

        if not self.pk and not UserAddress.objects.filter(user=self.user).exists():
            self.is_primary = True

        super().save(*args, **kwargs)

        if self.is_primary:
            UserAddress.objects.filter(user=self.user).exclude(pk=self.pk).update(is_primary=False)
            UserProfile.objects.filter(user=self.user).update(
                address_label=self.label,
                address=self.address,
                city=self.city,
                postal_code=self.postal_code,
                is_primary_address=True,
            )

    def __str__(self) -> str:
        return f"{self.user.username} - {self.get_label_display()} ({self.city})" # type: ignore


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
    city = models.CharField(max_length=100, blank=True)
    rajaongkir_city_id = models.CharField(max_length=20, blank=True)
    person_in_charge = models.CharField(max_length=255, blank=True)
    contact_phone = models.CharField(max_length=20, blank=True)
    legal_document_name = models.CharField(max_length=255, blank=True)

    beneficiaries_count = models.PositiveIntegerField(null=True, blank=True)
    founded_year = models.PositiveSmallIntegerField(null=True, blank=True)

    is_verified = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if self.city:
            city_id, _, _ = resolve_rajaongkir_city(self.city)
            if city_id:
                self.rajaongkir_city_id = city_id
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.name


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.get_or_create(user=instance)