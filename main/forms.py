from django import forms
from main.models import InstitutionProfile

class InstitutionProfileForm(forms.ModelForm):
    class Meta:
        model = InstitutionProfile
        fields = [
            "name", 
            "institution_type", 
            "description", 
            "address", 
            "contact_phone", 
            "beneficiaries_count", 
            "founded_year",
        ]

        labels = {
            "name": "Nama lembaga",
            "institution_type": "Jenis lembaga",
            "description": "Deskripsi lembaga",
            "address": "Alamat lembaga",
            "contact_phone": "Nomor telepon",
            "beneficiaries_count": "Jumlah penerima manfaat",
            "founded_year": "Tahun berdiri",
        }

        widgets = {
            "name": forms.TextInput(attrs={
                "class": "field__input",
                "placeholder": "Contoh: Panti Asuhan Harapan",
            }),
            "institution_type": forms.Select(attrs={
                "class": "field__input",
            }),
            "description": forms.Textarea(attrs={
                "class": "field__input",
                "rows": 4,
                "placeholder": "Ceritakan tentang lembaga anda..."
            }),
            "address": forms.Textarea(attrs={
                "class": "field__input",
                "rows": 3,
                "placeholder": "Alamat lengkap lembaga",
            }),
            "contact_phone": forms.TextInput(attrs={
                "class": "field__input",
                "placeholder": "Contoh: 081234567890"
            }),
            "beneficiaries_count": forms.NumberInput(attrs={
                "class": "field__input",
                "min": 0,
            }),
            "founded_year": forms.NumberInput(attrs={
                "class": "field__input",
                "min": 1800,
            }),
        }
