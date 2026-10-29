from django.apps import apps

SOURCES = {
    # jenis aksi: model ("app.Model"), kolom pemilik, kolom tanggal, syarat "sudah selesai"
    "terjual": {"model": "marketplace.Order", "user": "seller", "date": "updated_at", "filter": {"status": "selesai"}},
    "dibeli": {"model": "marketplace.Order", "user": "buyer", "date": "updated_at", "filter": {"status": "selesai"}},
    "donasi": {"model": "donasi.DonationOffer", "user": "donor", "date": "accepted_at", "filter": {"status": "DITERIMA"}},
    "lemari": {"model": "lemari.WardrobeItem", "user": "owner", "date": "created_at", "filter": {}},
}

LABELS = {
    "terjual": "Barang terjual",
    "dibeli": "Beli preloved",
    "donasi": "Donasi diterima",
    "lemari": "Barang di lemari",
}

# POIN / aksi
POINTS = {"terjual": 10, "dibeli": 5, "donasi": 20, "lemari": 2}


# Dipanggil get_counts dan challenges_progress (progress tantangan)
# Tiap labels -> udah berapa || Tiap challenges -> udah terachive berapa 
def count_for_user(key, user, since=None, until=None):
    source = SOURCES[key]
    try:
        model = apps.get_model(source["model"])
    except LookupError:
        return 0 
    rows = model.objects.filter(**source["filter"]).filter(**{source["user"]: user})
    if since:
        rows = rows.filter(**{source["date"] + "__gte": since}) # batas awal tantangan. __gte : >=
    if until:
        rows = rows.filter(**{source["date"] + "__lt": until}) # periode tantangan (tanggal < until)
    return rows.count()