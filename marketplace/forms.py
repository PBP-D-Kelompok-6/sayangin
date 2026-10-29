from pathlib import Path

from django import forms

from .models import Product

MAX_PHOTOS = 4
MAX_PHOTO_MB = 5
PHOTO_TYPES = {'.jpg', '.jpeg', '.png', '.webp', '.gif'}  # hanya gambar: file lain (mis. .html) bisa berbahaya kalau disajikan
SIZES = ['XS', 'S', 'M', 'L', 'XL', 'XXL', 'All size'] + [str(n) for n in range(36, 46)]  # baju + sepatu


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultiplePhotoField(forms.FileField):
    """Beberapa foto dari satu <input type="file" multiple> (pola dari dokumentasi Django)."""
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('widget', MultipleFileInput(attrs={'accept': 'image/*'}))
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        files = data if isinstance(data, (list, tuple)) else [data]
        return [super(MultiplePhotoField, self).clean(f, initial) for f in files if f]


class ProductForm(forms.ModelForm):
    """Form "Jual barang" (desain Figma B4): dipakai untuk menambah dan mengubah barang."""
    photos = MultiplePhotoField(label='Foto', required=False)
    field_order = ['photos']  # urutan sama dengan halaman: foto dulu, lalu isian di kanan

    class Meta:
        model = Product
        fields = ['name', 'category', 'size', 'condition', 'condition_note', 'price', 'weight_grams', 'city']
        labels = {
            'name': 'Judul', 'category': 'Kategori', 'size': 'Ukuran', 'condition': 'Kondisi',
            'condition_note': 'Catatan kondisi', 'price': 'Harga', 'weight_grams': 'Berat (gram)', 'city': 'Dikirim dari',
        }
        help_texts = {'weight_grams': 'Dipakai untuk menghitung ongkir'}
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'Contoh: Blazer wol abu, ukuran M'}),
            'condition': forms.RadioSelect,
            'condition_note': forms.Textarea(attrs={'rows': 2, 'placeholder': 'Contoh: kancing kedua sedikit longgar'}),
            'price': forms.NumberInput(attrs={'placeholder': 'Rp', 'min': 1000, 'step': 500}),
            'weight_grams': forms.NumberInput(attrs={'placeholder': 'Contoh: 800', 'min': 1}),
            'city': forms.TextInput(attrs={'placeholder': 'Contoh: Jakarta Selatan'}),
        }
        error_messages = {
            'name': {'required': 'Isi judul barang.'},
            'category': {'required': 'Pilih kategori.'},
            'condition': {'required': 'Pilih kondisi supaya pembeli tahu apa yang mereka dapat.'},
            'price': {'required': 'Isi harga, minimal Rp1.000.'},
            'weight_grams': {'required': 'Isi berat barang.'},
            'city': {'required': 'Isi kota asal pengiriman.'},
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['category'].choices = [('', 'Pilih kategori')] + Product.CATEGORY_CHOICES
        self.fields['condition'].choices = Product.CONDITION_CHOICES  # tanpa pilihan kosong "---------"
        sizes = SIZES if not self.instance.size or self.instance.size in SIZES else [self.instance.size] + SIZES
        self.fields['size'].widget = forms.Select(choices=[('', 'Pilih')] + [(s, s) for s in sizes])
        self.fields['weight_grams'].initial = None  # desain: kosong dengan contoh, bukan angka bawaan 500

    def clean_price(self):
        price = self.cleaned_data['price']
        if price < 1000:
            raise forms.ValidationError('Isi harga, minimal Rp1.000.')
        return price

    def clean_photos(self):
        photos = self.cleaned_data['photos']
        if not photos and not self.instance.image:
            raise forms.ValidationError('Tambahkan minimal 1 foto barang.')
        if len(photos) > MAX_PHOTOS:
            raise forms.ValidationError(f'Maksimal {MAX_PHOTOS} foto.')
        for photo in photos:
            if Path(photo.name).suffix.lower() not in PHOTO_TYPES or not (photo.content_type or '').startswith('image/'):
                raise forms.ValidationError(f'{photo.name} bukan file gambar.')
            if photo.size > MAX_PHOTO_MB * 1024 * 1024:
                raise forms.ValidationError(f'{photo.name} lebih dari {MAX_PHOTO_MB} MB.')
        return photos

    def clean(self):
        data = super().clean()
        if data.get('condition') == 'cacat' and not data.get('condition_note'):
            self.add_error('condition_note', 'Jelaskan cacatnya supaya pembeli tidak kecewa.')
        return data
