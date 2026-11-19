# Satu sumber pilihan untuk Lemari, Marketplace, dan Donasi.
# Barang yang sama harus punya kategori, ukuran, dan kondisi yang sama di semua modul,
# supaya barang di lemari bisa langsung dijual dan dicocokkan dengan kebutuhan lembaga.

KATEGORI = [
    ("atasan", "Atasan"),
    ("luaran", "Luaran"),
    ("bawahan", "Bawahan"),
    ("sepatu", "Sepatu"),
    ("tas", "Tas"),
    ("aksesori", "Aksesori"),
    ("buku", "Buku"),
    ("mainan", "Mainan"),
    ("rumah", "Rumah & dekor"),
    ("lainnya", "Lainnya"),
]

KONDISI = [
    ("seperti_baru", "Seperti baru"),
    ("terawat", "Bekas, terawat"),
    ("cacat", "Ada cacat"),
]

UKURAN_BAJU = ["XS", "S", "M", "L", "XL", "XXL", "All size"]
UKURAN_ANAK = ["6 th", "8 th", "10 th", "12 th"]
UKURAN_SEPATU = [str(n) for n in range(36, 46)]
UKURAN = UKURAN_BAJU + UKURAN_ANAK + UKURAN_SEPATU


def opsi_form(request):
    """Context processor: daftar pilihan untuk form yang ditulis langsung di template."""
    return {"kategori_opsi": KATEGORI, "ukuran_opsi": UKURAN}
