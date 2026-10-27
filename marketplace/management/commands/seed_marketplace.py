from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from marketplace.models import Product

# (penjual, nama, harga, kategori, kondisi, ukuran, kota, gambar, catatan)
PRODUCTS = [
    ('nadia.r', 'Blazer wol abu', 85000, 'atasan', 'terawat', 'M', 'Jakarta', 'blazer-abu', 'Kancing kedua sedikit longgar.'),
    ('nadia.r', 'Blus organza', 45000, 'atasan', 'seperti_baru', 'S', 'Jakarta', 'blus-organza', ''),
    ('nadia.r', 'Tas mesh', 55000, 'tas', 'terawat', '', 'Jakarta', 'tas-mesh', ''),
    ('bimapras', 'Set novel vintage, 3 buku', 35000, 'buku', 'seperti_baru', '', 'Depok', 'buku-vintage', ''),
    ('bimapras', 'Sweter bintang', 50000, 'atasan', 'seperti_baru', 'L', 'Depok', 'sweter-bintang', ''),
    ('bimapras', 'Kamera film', 250000, 'aksesori', 'terawat', '', 'Depok', 'kamera-film', 'Lensa ada goresan halus.'),
    ('sekar.w', 'Rok tulle', 50000, 'bawahan', 'terawat', 'M', 'Bandung', 'rok-tulle', ''),
    ('sekar.w', 'Heels chrome', 90000, 'sepatu', 'seperti_baru', '38', 'Bandung', 'heels-chrome', ''),
    ('sekar.w', 'Kardigan rajut marun', 45000, 'atasan', 'terawat', 'M', 'Bandung', 'kardigan-marun', ''),
    ('sekar.w', 'Mantel camel', 120000, 'atasan', 'terawat', 'L', 'Bandung', 'mantel-camel', ''),
    ('dimas.k', 'Jaket track suede', 75000, 'atasan', 'terawat', 'M', 'Bogor', 'jaket-track-zaitun', ''),
    ('dimas.k', 'Jaket kulit cokelat', 150000, 'atasan', 'cacat', 'L', 'Bogor', 'jaket-kulit', 'Ada lecet kecil di siku kiri.'),
    ('dimas.k', 'Henley sage', 35000, 'atasan', 'seperti_baru', 'M', 'Bogor', 'henley-sage', ''),
    ('ayu.p', 'Kacamata ring', 30000, 'aksesori', 'seperti_baru', '', 'Surabaya', 'kacamata-ring', ''),
    ('ayu.p', 'Atasan kerah bulu', 55000, 'atasan', 'terawat', 'S', 'Surabaya', 'atasan-bulu', ''),
    ('ayu.p', 'Tote metalik', 65000, 'tas', 'seperti_baru', '', 'Surabaya', 'tas-tote-metalik', ''),
    ('nadia.r', 'Jeans lukis', 70000, 'bawahan', 'seperti_baru', '30', 'Jakarta', 'jeans-lukis', ''),
    ('ayu.p', 'Loafer kulit marun', 85000, 'sepatu', 'terawat', '40', 'Surabaya', 'loafer-marun', 'Sol bawah sedikit aus.'),
    ('raka.s', 'Tas kulit hitam', 110000, 'tas', 'terawat', '', 'Medan', 'tas-kulit', ''),
    ('raka.s', 'Headphone kulit', 95000, 'aksesori', 'seperti_baru', '', 'Bekasi', 'headphone-kulit', ''),
    ('tiara.n', 'Kemeja linen', 40000, 'atasan', 'seperti_baru', 'M', 'Yogyakarta', 'kemeja-linen', ''),
    ('dimas.k', 'Sneakers suede', 80000, 'sepatu', 'terawat', '41', 'Malang', 'sneakers-suede', ''),
    ('putri.a', 'Dress garis', 60000, 'atasan', 'seperti_baru', 'S', 'Denpasar', 'dress-garis', ''),
    ('sekar.w', 'Celana korduroi', 50000, 'bawahan', 'terawat', '29', 'Bandung', 'celana-korduroi', ''),
    ('ayu.p', 'Rok plisket', 45000, 'bawahan', 'seperti_baru', 'M', 'Tangerang', 'rok-plisket', ''),
    ('bimapras', 'Kemeja kuning', 35000, 'atasan', 'terawat', 'L', 'Depok', 'kemeja-kuning', ''),
    ('nadia.r', 'Halter rajut', 40000, 'atasan', 'seperti_baru', 'S', 'Jakarta', 'halter-rajut', ''),
    ('tiara.n', 'Syal sutra', 30000, 'aksesori', 'seperti_baru', '', 'Solo', 'syal-sutra', ''),
    ('gilang.m', 'Jam tangan batu', 120000, 'aksesori', 'terawat', '', 'Makassar', 'jam-batu', 'Tali perlu diganti.'),
    ('dimas.k', 'Anting matahari', 25000, 'aksesori', 'seperti_baru', '', 'Bogor', 'anting-matahari', ''),
]


USED = {'Blazer wol abu': '2 tahun', 'Jaket kulit cokelat': '3 tahun', 'Kamera film': '5 tahun', 'Mantel camel': '1 tahun'}


class Command(BaseCommand):
    help = 'Isi marketplace dengan penjual dan barang contoh (aman dijalankan berulang).'

    def handle(self, *args, **options):
        created = 0
        for seller, name, price, category, condition, size, city, img, note in PRODUCTS:
            user, new = User.objects.get_or_create(username=seller)
            if new:
                user.set_unusable_password()
                user.save()
            _, new = Product.objects.update_or_create(seller=user, name=name, defaults={
                'price': price, 'category': category, 'condition': condition, 'size': size,
                'city': city, 'image': f'marketplace/img/{img}.jpg', 'condition_note': note,
                'used_duration': USED.get(name, ''),
            })
            created += new
        self.stdout.write(self.style.SUCCESS(f'{created} barang baru ditambahkan.'))
