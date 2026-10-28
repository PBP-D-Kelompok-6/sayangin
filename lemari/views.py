from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from .models import ListingPhoto, SaleListing, WardrobeItem

def _listing_values(request):
    def integer(name):
        value = request.POST.get(name, "").replace(".", "").replace(",", "").strip()
        return int(value) if value.isdigit() else None
    return {"title": request.POST.get("judul", "").strip(), "category": request.POST.get("kategori", "").strip(), "size": request.POST.get("ukuran", "").strip(), "condition": request.POST.get("kondisi", "").strip(), "condition_notes": request.POST.get("catatan", "").strip(), "price": integer("harga"), "weight": integer("berat"), "shipped_from": request.POST.get("dikirim_dari", "Alamat utama · Jakarta Selatan").strip()}


def index(request):
    wardrobe_items = WardrobeItem.objects.all()
    return render(request, "lemari/index.html", {"wardrobe_items": wardrobe_items, "wardrobe_count": wardrobe_items.count()})


def kosong(request):
    return render(request, "lemari/kosong.html")


def awal(request):
    if request.method == "POST":
        entries = []
        errors = {}
        for number in range(1, 4):
            name = request.POST.get(f"nama_{number}", "").strip()
            category = request.POST.get(f"kategori_{number}", "").strip()
            last_used = request.POST.get(f"terakhir_dipakai_{number}", "").strip()
            has_content = name or category or last_used or request.FILES.get(f"foto_{number}")
            if not has_content:
                continue
            if not name: errors[number] = "Isi nama barang."
            elif not category or not last_used: errors[number] = "Lengkapi kategori dan terakhir dipakai."
            entries.append((number, name, category, last_used))
        if not entries:
            errors[1] = "Tambahkan setidaknya satu barang ke lemarimu."
        if errors:
            return render(request, "lemari/awal.html", {"errors": errors})
        for number, name, category, last_used in entries:
            item = WardrobeItem(name=name, category=category, last_used=last_used)
            if request.user.is_authenticated:
                item.owner = request.user
            photo = request.FILES.get(f"foto_{number}")
            if photo:
                item.photo = photo
            item.save()
        return redirect("lemari:index")
    return render(request, "lemari/awal.html")


def wardrobe_photo(request, item_id):
    item = get_object_or_404(WardrobeItem, pk=item_id)
    if not item.photo:
        raise Http404
    return FileResponse(item.photo.open("rb"), content_type="image/*")


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
