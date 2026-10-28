from django import forms
from django.utils import timezone

from .models import UKURAN_CHOICES, Kebutuhan, Penawaran


class KebutuhanForm(forms.ModelForm):
    ukuran = forms.MultipleChoiceField(
        choices=UKURAN_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="Ukuran",
    )

    class Meta:
        model = Kebutuhan
        fields = [
            "nama_barang", "kategori", "jumlah", "ukuran",
            "kondisi_min", "tenggat", "foto_url", "cerita",
        ]
        widgets = {
            "nama_barang": forms.TextInput(attrs={"class": "input"}),
            "kategori": forms.Select(attrs={"class": "select"}),
            "jumlah": forms.NumberInput(attrs={"min": 1, "aria-label": "Jumlah"}),
            "kondisi_min": forms.RadioSelect,
            "tenggat": forms.DateInput(attrs={"type": "date", "class": "input"}, format="%Y-%m-%d"),
            "foto_url": forms.URLInput(attrs={"class": "input", "placeholder": "https://…"}),
            "cerita": forms.Textarea(attrs={"class": "textarea", "rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk and not self.is_bound:
            self.initial["ukuran"] = self.instance.ukuran_list

    def clean_ukuran(self):
        return ",".join(self.cleaned_data["ukuran"])

    def clean_tenggat(self):
        tenggat = self.cleaned_data.get("tenggat")
        if tenggat and (not self.instance.pk or "tenggat" in self.changed_data):
            if tenggat < timezone.localdate():
                raise forms.ValidationError("Tenggat tidak boleh di masa lalu.")
        return tenggat

    def clean_jumlah(self):
        jumlah = self.cleaned_data["jumlah"]
        if self.instance.pk and jumlah < self.instance.terpenuhi:
            raise forms.ValidationError(
                f"Jumlah tidak boleh kurang dari barang yang sudah terpenuhi ({self.instance.terpenuhi})."
            )
        return jumlah

class PenawaranForm(forms.ModelForm):
    bersih = forms.BooleanField(
        required=True,
        error_messages={"required": "Pastikan barang sudah bersih dan layak pakai."},
    )

    class Meta:
        model = Penawaran
        fields = ["metode", "tanggal_rencana", "jam", "pesan"]
        widgets = {
            "metode": forms.RadioSelect,
            "tanggal_rencana": forms.DateInput(
                attrs={"type": "date", "class": "input"}, format="%Y-%m-%d"),
            "jam": forms.Select(attrs={"class": "select"}),
            "pesan": forms.Textarea(attrs={
                "class": "textarea", "rows": 3,
                "placeholder": "Contoh: kancing kedua sedikit longgar, sudah dicuci.",
            }),
        }

    def __init__(self, *args, kebutuhan=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.kebutuhan = kebutuhan
        self.fields["tanggal_rencana"].required = True

    def clean_tanggal_rencana(self):
        tanggal = self.cleaned_data.get("tanggal_rencana")
        if tanggal and tanggal < timezone.localdate():
            raise forms.ValidationError("Pilih tanggal hari ini atau setelahnya.")
        return tanggal