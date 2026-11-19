from django.db import migrations

KATEGORI = {
    "Pakaian": "atasan",
    "Pakaian · Atasan": "atasan",
    "Pakaian · Luaran": "luaran",
    "Pakaian · Bawahan": "bawahan",
    "Sepatu": "sepatu",
    "Tas": "tas",
    "Aksesori": "aksesori",
    "Buku": "buku",
    "Elektronik": "lainnya",
    "Lainnya": "lainnya",
}


def samakan_pilihan(apps, schema_editor):
    """Ubah teks kategori & kondisi lama ke pilihan bersama (sayangin/pilihan.py)."""
    WardrobeItem = apps.get_model("lemari", "WardrobeItem")
    SaleListing = apps.get_model("lemari", "SaleListing")
    for lama, baru in KATEGORI.items():
        WardrobeItem.objects.filter(category=lama).update(category=baru)
        SaleListing.objects.filter(category=lama).update(category=baru)
    SaleListing.objects.filter(condition="baru").update(condition="seperti_baru")


class Migration(migrations.Migration):

    dependencies = [("lemari", "0011_pilihan_bersama")]

    operations = [migrations.RunPython(samakan_pilihan, migrations.RunPython.noop)]
