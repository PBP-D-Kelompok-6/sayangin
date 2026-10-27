from django import forms

from .models import Product


class ProductForm(forms.ModelForm):
    """Form penjual untuk menambah/mengedit barang preloved (dipakai di halaman Jual barang)."""
    image = forms.URLField(
        label='Link foto barang', max_length=500, assume_scheme='https',
        help_text='Tempel link foto (misalnya dari Google Drive publik atau Imgur).',
    )

    class Meta:
        model = Product
        fields = ['name', 'price', 'category', 'condition', 'condition_note', 'size', 'city',
                  'weight_grams', 'used_duration', 'description', 'image']
        labels = {
            'name': 'Nama barang', 'price': 'Harga (Rp)', 'category': 'Kategori', 'condition': 'Kondisi',
            'condition_note': 'Catatan kondisi', 'size': 'Ukuran', 'city': 'Kota',
            'weight_grams': 'Berat (gram)', 'used_duration': 'Dipakai sekitar', 'description': 'Deskripsi',
        }
        help_texts = {
            'condition_note': 'Jujur soal cacat kecil membuat pembeli lebih percaya.',
            'used_duration': 'Misalnya "2 tahun".',
        }
        widgets = {'description': forms.Textarea(attrs={'rows': 3})}

    def clean_price(self):
        price = self.cleaned_data['price']
        if price < 1000:
            raise forms.ValidationError('Harga minimal Rp1.000.')
        return price

    def clean(self):
        data = super().clean()
        if data.get('condition') == 'cacat' and not data.get('condition_note'):
            self.add_error('condition_note', 'Jelaskan cacatnya supaya pembeli tidak kecewa.')
        return data
