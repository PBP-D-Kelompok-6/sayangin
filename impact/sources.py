# File ini satu-satunya tempat Modul E membaca tabel modul teman.
from django.apps import apps

# jenis aksi: model ("app.Model"), kolom pemilik, kolom tanggal, syarat "sudah selesai"
SOURCES = {
    # terjual dihitung saat barang sudah sampai di tangan pembeli
    "terjual": {"model": "marketplace.Order", "user": "seller", "date": "updated_at", "filter": {"status": "selesai"}},
    # dibeli dihitung saat pesanan user (sebagai pembeli) sudah berstatus selesai
    "dibeli": {"model": "marketplace.Order", "user": "buyer", "date": "updated_at", "filter": {"status": "selesai"}},
    # donasi dihitung saat lembaga sudah menerima barangnya
    "donasi": {"model": "donasi.Penawaran", "user": "donatur", "date": "diterima_pada", "filter": {"status": "selesai"}},
    # lemari dihitung setiap kali user mencatat barang baru (tanpa syarat status)
    "lemari": {"model": "lemari.WardrobeItem", "user": "owner", "date": "created_at", "filter": {}},
}

# Nama yang tampil di kartu angka dashboard (summary.html)
LABELS = {
    "terjual": "Barang terjual",
    "dibeli": "Beli preloved",
    "donasi": "Donasi diterima",
    "lemari": "Barang di lemari",
}

# POIN / aksi
# donasi paling besar karena dampaknya paling nyata; lemari kecil karena paling mudah dilakukan
POINTS = {"terjual": 10, "dibeli": 5, "donasi": 20, "lemari": 2}


# Dipanggil get_counts dan challenges_progress (progress tantangan)
# Tiap labels -> udah berapa || Tiap challenges -> udah terachive berapa 
def count_for_user(key, user, since=None, until=None):
    source = SOURCES[key] # pengaturan jenis aksi yang diminta, mis. SOURCES["donasi"]
    try:
        model = apps.get_model(source["model"]) # ambil model teman dari namanya, mis. "marketplace.Order"
    except LookupError:
        return 0 
    rows = model.objects.filter(**source["filter"]).filter(**{source["user"]: user})
    if since:
        rows = rows.filter(**{source["date"] + "__gte": since}) # batas awal tantangan. __gte : >=
    if until:
        rows = rows.filter(**{source["date"] + "__lt": until}) # periode tantangan (tanggal < until)
    return rows.count() # cukup jumlah barisnya, isi datanya tidak dipakai