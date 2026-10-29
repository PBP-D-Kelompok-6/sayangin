from django import forms

from impact.models import Challenge

# dipakai oleh: 
# 1. create_impact_challenge (views.py),
# 2. edit_impact_challenge (views.py), 
# lalu ditampilkan di challenge_form.html.

# Untuk tambah/ubah then save
class ChallengeForm(forms.ModelForm):
    class Meta:
        model = Challenge
        fields = ["title", "kind", "target", "start_date", "end_date"]
        labels = {"title": "Judul tantangan", "kind": "Jenis aksi", "target": "Target (jumlah)",
                  "start_date": "Mulai", "end_date": "Selesai"}
        widgets = {
            "title": forms.TextInput(attrs={"class": "input", "placeholder": "mis. Jual 3 barang minggu ini"}),
            "kind": forms.Select(attrs={"class": "select"}),
            "target": forms.NumberInput(attrs={"class": "input", "min": 1}),
            "start_date": forms.DateInput(attrs={"class": "input", "type": "date"}),
            "end_date": forms.DateInput(attrs={"class": "input", "type": "date"}),
        }

    # Validasi tambahan untuk beberapa field. Dijalankan otomatis saat views memanggil form.is.valid
    def clean(self):
        cleaned = super().clean()
        if cleaned.get("target") == 0:
            self.add_error("target", "Target minimal 1.")
        start, end = cleaned.get("start_date"), cleaned.get("end_date")
        if start and end and end < start:
            self.add_error("end_date", "Tanggal selesai tidak boleh sebelum tanggal mulai.")
        return cleaned