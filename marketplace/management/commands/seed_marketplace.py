from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from marketplace.models import Product

# (penjual, nama, harga, kategori, kondisi, ukuran, kota, gambar, catatan)
PRODUCTS = [
    ('nadia.r', 'Blazer wol abu', 185000, 'atasan', 'terawat', 'M', 'Jakarta', 'blazer-abu', 'Kancing kedua sedikit longgar.'),
    ('nadia.r', 'Blus organza', 95000, 'atasan', 'seperti_baru', 'S', 'Jakarta', 'blus-organza', ''),
    ('nadia.r', 'Tas mesh', 120000, 'tas', 'terawat', '', 'Jakarta', 'tas-mesh', ''),
    ('bimapras', 'Set novel vintage, 3 buku', 60000, 'buku', 'seperti_baru', '', 'Depok', 'buku-vintage', ''),
    ('bimapras', 'Sweter bintang', 110000, 'atasan', 'seperti_baru', 'L', 'Depok', 'sweter-bintang', ''),
    ('bimapras', 'Kamera film', 450000, 'aksesori', 'terawat', '', 'Depok', 'kamera-film', 'Lensa ada goresan halus.'),
    ('sekar.w', 'Rok tulle', 130000, 'bawahan', 'terawat', 'M', 'Bandung', 'rok-tulle', ''),
    ('sekar.w', 'Heels chrome', 210000, 'sepatu', 'seperti_baru', '38', 'Bandung', 'heels-chrome', ''),
    ('sekar.w', 'Kardigan rajut marun', 90000, 'atasan', 'terawat', 'M', 'Bandung', 'kardigan-marun', ''),
    ('sekar.w', 'Mantel camel', 320000, 'atasan', 'terawat', 'L', 'Bandung', 'mantel-camel', ''),
    ('dimas.k', 'Jaket track suede', 175000, 'atasan', 'terawat', 'M', 'Bogor', 'jaket-track-zaitun', ''),
    ('dimas.k', 'Jaket kulit cokelat', 380000, 'atasan', 'cacat', 'L', 'Bogor', 'jaket-kulit', 'Ada lecet kecil di siku kiri.'),
    ('dimas.k', 'Henley sage', 75000, 'atasan', 'seperti_baru', 'M', 'Bogor', 'henley-sage', ''),
    ('ayu.p', 'Kacamata ring', 85000, 'aksesori', 'seperti_baru', '', 'Surabaya', 'kacamata-ring', ''),
    ('ayu.p', 'Atasan kerah bulu', 140000, 'atasan', 'terawat', 'S', 'Surabaya', 'atasan-bulu', ''),
    ('ayu.p', 'Tote metalik', 160000, 'tas', 'seperti_baru', '', 'Surabaya', 'tas-tote-metalik', ''),
]


class Command(BaseCommand):
    help = 'Isi marketplace dengan penjual dan barang contoh (aman dijalankan berulang).'

    def handle(self, *args, **options):
        created = 0
        for seller, name, price, category, condition, size, city, img, note in PRODUCTS:
            user, new = User.objects.get_or_create(username=seller)
            if new:
                user.set_unusable_password()
                user.save()
            _, new = Product.objects.get_or_create(seller=user, name=name, defaults={
                'price': price, 'category': category, 'condition': condition, 'size': size,
                'city': city, 'image': f'marketplace/img/{img}.jpg', 'condition_note': note,
            })
            created += new
        self.stdout.write(self.style.SUCCESS(f'{created} barang baru ditambahkan.'))
