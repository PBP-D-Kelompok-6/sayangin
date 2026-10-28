from django.shortcuts import get_object_or_404, redirect, render
from .models import ListingPhoto, SaleListing

def _listing_values(request):
    def integer(name):
        value = request.POST.get(name, "").replace(".", "").replace(",", "").strip()
        return int(value) if value.isdigit() else None
    return {"title": request.POST.get("judul", "").strip(), "category": request.POST.get("kategori", "").strip(), "size": request.POST.get("ukuran", "").strip(), "condition": request.POST.get("kondisi", "").strip(), "condition_notes": request.POST.get("catatan", "").strip(), "price": integer("harga"), "weight": integer("berat"), "shipped_from": request.POST.get("dikirim_dari", "Alamat utama · Jakarta Selatan").strip()}


def index(request):
    return render(request, "lemari/index.html")


def kosong(request):
    return render(request, "lemari/kosong.html")


def awal(request):
    return render(request, "lemari/awal.html")


def jual(request):
    listing_id = request.POST.get("listing_id")
    listing = get_object_or_404(SaleListing, pk=listing_id) if listing_id else None
    if request.method == "POST":
        values = _listing_values(request)
        errors = {}
        if not values["title"]: errors["judul"] = "Isi judul barang."
        if not values["category"]: errors["kategori"] = "Pilih kategori."
        if not values["size"]: errors["ukuran"] = "Pilih ukuran."
        if not values["condition"]: errors["kondisi"] = "Pilih kondisi supaya pembeli tahu apa yang mereka dapat."
        if not values["price"] or values["price"] < 1000: errors["harga"] = "Isi harga minimal Rp1.000."
        if not values["weight"] or values["weight"] <= 0: errors["berat"] = "Isi berat barang."
        if errors:
            return render(request, "lemari/jual.html", {"values": values, "errors": errors, "listing": listing})
        if listing is None: listing = SaleListing()
        for field, value in values.items(): setattr(listing, field, value)
        listing.status = SaleListing.PUBLISHED
        if request.user.is_authenticated: listing.owner = request.user
        listing.save()
        for image in request.FILES.getlist("photos"): ListingPhoto.objects.create(listing=listing, image=image)
        return redirect("lemari:jual_sukses", listing_id=listing.pk)
    values = {"title": listing.title if listing else "Blazer wol abu, ukuran M", "category": listing.category if listing else "Pakaian · Luaran", "size": listing.size if listing else "M", "condition": listing.condition if listing else "terawat", "condition_notes": listing.condition_notes if listing else "Kancing kedua sedikit longgar.", "price": listing.price if listing else "", "weight": listing.weight if listing else 800, "shipped_from": listing.shipped_from if listing else "Alamat utama · Jakarta Selatan"}
    return render(request, "lemari/jual.html", {"values": values, "listing": listing})


def jual_sukses(request, listing_id=None):
    listing = get_object_or_404(SaleListing, pk=listing_id) if listing_id else None
    return render(request, "lemari/jual_sukses.html", {"listing": listing})
