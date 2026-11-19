from django.db import migrations

KATEGORI = {
    "pakaian-luaran": "luaran",
    "pakaian-atasan": "atasan",
    "pakaian-bawahan": "bawahan",
    "alas-kaki": "sepatu",
    "perlengkapan-sekolah": "lainnya",
    "perabot": "rumah",
}
KONDISI = {"seperti-baru": "seperti_baru", "ada-cacat": "cacat"}


def samakan_pilihan(apps, schema_editor):
    """Ubah kategori & kondisi lama ke pilihan bersama (sayangin/pilihan.py)."""
    Kebutuhan = apps.get_model("donasi", "Kebutuhan")
    Penawaran = apps.get_model("donasi", "Penawaran")
    for lama, baru in KATEGORI.items():
        Kebutuhan.objects.filter(kategori=lama).update(kategori=baru)
    for lama, baru in KONDISI.items():
        Kebutuhan.objects.filter(kondisi_min=lama).update(kondisi_min=baru)
        Penawaran.objects.filter(kondisi=lama).update(kondisi=baru)


class Migration(migrations.Migration):

    dependencies = [("donasi", "0003_pilihan_bersama")]

    operations = [migrations.RunPython(samakan_pilihan, migrations.RunPython.noop)]
