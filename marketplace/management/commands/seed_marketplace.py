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

    # Tambahan supaya katalog ~100 barang dan semua kategori terisi (foto dibuat dengan Figma AI).
    # Luaran
    ('nadia.r', 'Jaket denim navy', 95000, 'luaran', 'terawat', 'M', 'Jakarta', 'jaket-denim-navy', ''),
    ('sekar.w', 'Trench coat krem', 175000, 'luaran', 'terawat', 'L', 'Bandung', 'trench-coat-krem', ''),
    ('bimapras', 'Hoodie abu polos', 60000, 'luaran', 'seperti_baru', 'XL', 'Depok', 'hoodie-abu', ''),
    ('dimas.k', 'Jaket bomber hijau army', 110000, 'luaran', 'terawat', 'L', 'Bogor', 'bomber-hijau-army', ''),
    ('tiara.n', 'Kardigan rajut krem', 55000, 'luaran', 'seperti_baru', 'M', 'Yogyakarta', 'kardigan-krem-rajut', ''),
    ('fajar.d', 'Jaket puffer hitam', 140000, 'luaran', 'terawat', 'M', 'Malang', 'puffer-hitam', ''),
    ('ayu.p', 'Blazer kotak-kotak cokelat', 90000, 'luaran', 'terawat', 'M', 'Surabaya', 'blazer-kotak', ''),
    ('raka.s', 'Parka hijau bertudung', 130000, 'luaran', 'cacat', 'L', 'Medan', 'parka-hijau', 'Resleting agak seret.'),
    ('maya.s', 'Rompi rajut argyle', 40000, 'luaran', 'seperti_baru', 'S', 'Solo', 'rompi-rajut', ''),
    ('yoga.p', 'Windbreaker biru', 70000, 'luaran', 'terawat', 'L', 'Bekasi', 'windbreaker-biru', ''),
    ('lestari.k', 'Jaket jeans anak', 45000, 'luaran', 'terawat', '8 th', 'Tangerang', 'jaket-jeans-anak', ''),
    ('maya.s', 'Outer kimono batik', 65000, 'luaran', 'seperti_baru', 'All size', 'Solo', 'kimono-outer-batik', ''),
    # Atasan
    ('bimapras', 'Kaos putih polos', 25000, 'atasan', 'seperti_baru', 'M', 'Depok', 'kaos-putih-polos', ''),
    ('dimas.k', 'Kemeja flanel merah', 50000, 'atasan', 'terawat', 'L', 'Bogor', 'kemeja-flanel-merah', ''),
    ('nadia.r', 'Blus polkadot hitam', 45000, 'atasan', 'seperti_baru', 'S', 'Jakarta', 'blus-polkadot', ''),
    ('gilang.m', 'Kaus polo hijau tua', 35000, 'atasan', 'terawat', 'L', 'Makassar', 'polo-hijau', ''),
    ('sekar.w', 'Sweter turtleneck hitam', 55000, 'atasan', 'seperti_baru', 'M', 'Bandung', 'sweater-turtleneck', ''),
    ('tiara.n', 'Kemeja batik parang', 80000, 'atasan', 'terawat', 'L', 'Yogyakarta', 'kemeja-batik', ''),
    ('putri.a', 'Crop top rajut lilac', 35000, 'atasan', 'seperti_baru', 'S', 'Denpasar', 'crop-top-rajut', ''),
    ('rina.h', 'Kemeja oxford biru muda', 45000, 'atasan', 'terawat', 'M', 'Jakarta', 'kemeja-oxford-biru', ''),
    ('fajar.d', 'Kaos grafis vintage', 60000, 'atasan', 'cacat', 'L', 'Malang', 'kaos-grafis-vintage', 'Sablon mulai retak.'),
    ('lestari.k', 'Tunik linen hijau sage', 50000, 'atasan', 'seperti_baru', 'All size', 'Tangerang', 'tunik-linen', ''),
    # Bawahan
    ('yoga.p', 'Celana chino krem', 55000, 'bawahan', 'terawat', 'L', 'Bekasi', 'celana-chino-krem', ''),
    ('putri.a', 'Rok denim mini', 40000, 'bawahan', 'seperti_baru', 'S', 'Denpasar', 'rok-denim-mini', ''),
    ('ayu.p', 'Celana kulot hitam', 45000, 'bawahan', 'seperti_baru', 'M', 'Surabaya', 'celana-kulot-hitam', ''),
    ('rina.h', 'Rok midi satin hijau', 60000, 'bawahan', 'terawat', 'M', 'Jakarta', 'rok-midi-satin', ''),
    ('yoga.p', 'Celana cargo abu', 65000, 'bawahan', 'terawat', 'L', 'Bekasi', 'celana-cargo', ''),
    ('raka.s', 'Celana jogger hitam', 40000, 'bawahan', 'seperti_baru', 'M', 'Medan', 'jogger-hitam', ''),
    ('maya.s', 'Rok lilit batik', 50000, 'bawahan', 'terawat', 'All size', 'Solo', 'rok-batik-lilit', ''),
    ('gilang.m', 'Celana pendek denim', 35000, 'bawahan', 'cacat', 'M', 'Makassar', 'celana-pendek-denim', 'Ujung bawah berserabut.'),
    # Sepatu
    ('nadia.r', 'Sneakers putih kanvas', 70000, 'sepatu', 'terawat', '39', 'Jakarta', 'sneakers-putih', ''),
    ('sekar.w', 'Boots kulit hitam', 160000, 'sepatu', 'terawat', '40', 'Bandung', 'boots-kulit-hitam', ''),
    ('fajar.d', 'Sandal gunung', 60000, 'sepatu', 'seperti_baru', '42', 'Malang', 'sandal-gunung', ''),
    ('tiara.n', 'Flat shoes krem', 50000, 'sepatu', 'seperti_baru', '37', 'Yogyakarta', 'flat-shoes-krem', ''),
    ('yoga.p', 'Sepatu lari biru', 120000, 'sepatu', 'terawat', '43', 'Bekasi', 'sepatu-lari-biru', ''),
    ('putri.a', 'Sepatu Mary Jane hitam', 75000, 'sepatu', 'seperti_baru', '38', 'Denpasar', 'mary-jane-hitam', ''),
    ('bimapras', 'Slip-on kotak-kotak', 45000, 'sepatu', 'cacat', '41', 'Depok', 'slip-on-kotak', 'Ada noda di ujung sepatu kiri.'),
    ('lestari.k', 'Sepatu anak pink', 35000, 'sepatu', 'terawat', '', 'Tangerang', 'sepatu-anak-pink', ''),
    # Tas
    ('dimas.k', 'Ransel kanvas cokelat', 85000, 'tas', 'terawat', '', 'Bogor', 'ransel-kanvas', ''),
    ('rina.h', 'Tas selempang mini hitam', 50000, 'tas', 'seperti_baru', '', 'Jakarta', 'tas-selempang-mini', ''),
    ('tiara.n', 'Tote kanvas putih', 30000, 'tas', 'terawat', '', 'Yogyakarta', 'tote-kanvas-putih', ''),
    ('putri.a', 'Tas rotan bulat', 70000, 'tas', 'seperti_baru', '', 'Denpasar', 'tas-rotan', ''),
    ('ayu.p', 'Clutch satin emas', 55000, 'tas', 'seperti_baru', '', 'Surabaya', 'clutch-satin', ''),
    ('yoga.p', 'Tas laptop abu', 75000, 'tas', 'terawat', '', 'Bekasi', 'tas-laptop', ''),
    ('raka.s', 'Waist bag hitam', 40000, 'tas', 'cacat', '', 'Medan', 'waist-bag', 'Gesper sedikit retak.'),
    ('sekar.w', 'Tas bahu kulit cokelat', 95000, 'tas', 'terawat', '', 'Bandung', 'tas-bahu-cokelat', ''),
    # Aksesori
    ('bimapras', 'Topi bucket krem', 30000, 'aksesori', 'seperti_baru', '', 'Depok', 'topi-bucket', ''),
    ('nadia.r', 'Kalung mutiara', 65000, 'aksesori', 'terawat', '', 'Jakarta', 'kalung-mutiara', ''),
    ('gilang.m', 'Jam tangan kulit cokelat', 110000, 'aksesori', 'terawat', '', 'Makassar', 'jam-tangan-kulit', ''),
    ('fajar.d', 'Kacamata hitam kotak', 45000, 'aksesori', 'seperti_baru', '', 'Malang', 'kacamata-hitam-kotak', ''),
    ('raka.s', 'Ikat pinggang kulit hitam', 35000, 'aksesori', 'terawat', '', 'Medan', 'ikat-pinggang-hitam', ''),
    ('putri.a', 'Set jepit rambut mutiara', 20000, 'aksesori', 'seperti_baru', '', 'Denpasar', 'jepit-rambut-mutiara', ''),
    ('tiara.n', 'Gelang rantai perak', 50000, 'aksesori', 'terawat', '', 'Yogyakarta', 'gelang-perak', ''),
    ('maya.s', 'Syal rajut marun', 30000, 'aksesori', 'seperti_baru', '', 'Solo', 'syal-rajut-marun', ''),
    # Buku
    ('rina.h', 'Set novel klasik, 4 buku', 60000, 'buku', 'terawat', '', 'Jakarta', 'novel-klasik', ''),
    ('ayu.p', 'Buku resep masakan rumahan', 35000, 'buku', 'seperti_baru', '', 'Surabaya', 'buku-resep', ''),
    ('yoga.p', 'Set komik, 5 jilid', 50000, 'buku', 'terawat', '', 'Bekasi', 'komik-set', ''),
    ('lestari.k', 'Buku cerita anak bergambar', 25000, 'buku', 'terawat', '', 'Tangerang', 'buku-anak-bergambar', ''),
    ('raka.s', 'Kamus Inggris–Indonesia', 30000, 'buku', 'cacat', '', 'Medan', 'kamus-inggris', 'Sudut sampul sedikit sobek.'),
    ('sekar.w', 'Jurnal sampul kulit', 40000, 'buku', 'seperti_baru', '', 'Bandung', 'jurnal-kulit', ''),
    # Mainan
    ('lestari.k', 'Boneka beruang cokelat', 45000, 'mainan', 'terawat', '', 'Tangerang', 'boneka-beruang', ''),
    ('rina.h', 'Balok susun warna-warni', 55000, 'mainan', 'terawat', '', 'Jakarta', 'balok-susun', ''),
    ('tiara.n', 'Mobil-mobilan kayu', 35000, 'mainan', 'seperti_baru', '', 'Yogyakarta', 'mobil-mainan-kayu', ''),
    ('maya.s', 'Puzzle kayu hewan', 30000, 'mainan', 'seperti_baru', '', 'Solo', 'puzzle-kayu', ''),
    ('fajar.d', 'Kubus puzzle 3x3', 25000, 'mainan', 'terawat', '', 'Malang', 'kubus-puzzle', ''),
    # Rumah & dekor
    ('sekar.w', 'Vas keramik putih', 45000, 'rumah', 'seperti_baru', '', 'Bandung', 'vas-keramik', ''),
    ('putri.a', 'Lampu meja rotan', 85000, 'rumah', 'terawat', '', 'Denpasar', 'lampu-meja-rotan', ''),
    ('tiara.n', 'Bantal tenun', 30000, 'rumah', 'seperti_baru', '', 'Yogyakarta', 'bantal-tenun', ''),
    ('ayu.p', 'Cermin dinding bulat', 70000, 'rumah', 'terawat', '', 'Surabaya', 'cermin-bulat', ''),
    # Lainnya
    ('nadia.r', 'Tumbler stainless hijau', 40000, 'lainnya', 'seperti_baru', '', 'Jakarta', 'tumbler-hijau', ''),
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
