from django import forms
from main.models import UserProfile, InstitutionProfile

CITY_CHOICES = [
    ("", "Pilih kota"),
    ("Jakarta Selatan", "Jakarta Selatan"),
    ("Jakarta Pusat", "Jakarta Pusat"),
    ("Jakarta Barat", "Jakarta Barat"),
    ("Jakarta Timur", "Jakarta Timur"),
    ("Jakarta Utara", "Jakarta Utara"),
    ("Depok", "Depok"),
    ("Bogor", "Bogor"),
    ("Tangerang", "Tangerang"),
    ("Tangerang Selatan", "Tangerang Selatan"),
    ("Bekasi", "Bekasi"),
    ("Bandung", "Bandung"),
    ("Yogyakarta", "Yogyakarta"),
    ("Semarang", "Semarang"),
    ("Surabaya", "Surabaya"),
    ("Malang", "Malang"),
    ("Medan", "Medan"),
    ("Makassar", "Makassar"),
    ("Denpasar", "Denpasar"),
]

class ProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = [
            "full_name",
            "phone_number",
            "address_label",
            "address",
            "city",
            "postal_code",
            "is_primary_address",
            "preferences",
        ]
        labels = {
            "full_name": "Nama lengkap",
            "phone_number": "Nomor HP",
            "address_label": "Label alamat",
            "address": "Alamat lengkap",
            "city": "Kota / kabupaten",
            "postal_code": "Kode pos",
            "is_primary_address": "Jadikan alamat utama",
            "preferences": "Preferensi",
        }
        widgets = {
            "full_name": forms.TextInput(attrs={
                "class": "input",
                "autocomplete": "name",
                "required": True,
            }),
            "phone_number": forms.TextInput(attrs={
                "class": "input",
                "type": "tel",
                "placeholder": "08…",
                "autocomplete": "tel",
            }),
            "address_label": forms.RadioSelect(attrs={
                "class": "visually-hidden",
            }),
            "address": forms.Textarea(attrs={
                "class": "textarea",
                "rows": 2,
                "autocomplete": "street-address",
            }),
            "city": forms.Select(choices=CITY_CHOICES, attrs={
                "class": "select",
            }),
            "postal_code": forms.TextInput(attrs={
                "class": "input",
                "inputmode": "numeric",
                "autocomplete": "postal-code",
            }),
            "is_primary_address": forms.CheckboxInput(),
            "preferences": forms.Textarea(attrs={
                "class": "textarea",
                "rows": 2,
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["full_name"].required = True


class InstitutionProfileForm(forms.ModelForm):
    class Meta:
        model = InstitutionProfile
        fields = [
            "name",
            "institution_type",
            "address",
            "person_in_charge",
            "contact_phone",
            "description",
            "beneficiaries_count",
            "founded_year",
        ]

        labels = {
            "name": "Nama lembaga",
            "institution_type": "Jenis lembaga",
            "address": "Alamat lembaga",
            "person_in_charge": "Penanggung jawab",
            "contact_phone": "Nomor HP",
            "description": "Deskripsi lembaga",
            "beneficiaries_count": "Jumlah penerima manfaat",
            "founded_year": "Tahun berdiri",
        }

        widgets = {
            "name": forms.TextInput(attrs={
                "class": "input",
                "required": True,
            }),
            "institution_type": forms.Select(attrs={
                "class": "select",
            }),
            "address": forms.Textarea(attrs={
                "class": "textarea",
                "rows": 2,
            }),
            "person_in_charge": forms.TextInput(attrs={
                "class": "input",
            }),
            "contact_phone": forms.TextInput(attrs={
                "class": "input",
                "type": "tel",
            }),
            "description": forms.Textarea(attrs={
                "class": "textarea",
                "rows": 3,
            }),
            "beneficiaries_count": forms.NumberInput(attrs={
                "class": "input",
                "min": 0,
            }),
            "founded_year": forms.NumberInput(attrs={
                "class": "input",
                "min": 1800,
            }),
        }
