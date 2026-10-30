from django.http import FileResponse, Http404
from django.db.models import Case, IntegerField, When
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from .models import ListingPhoto, SaleListing, WardrobeItem
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.urls import reverse
from django.utils.crypto import get_random_string
from datetime import datetime
from pathlib import Path

from donasi.models import Penawaran
from marketplace import views as marketplace_views
from marketplace.forms import PHOTO_TYPES
from marketplace.models import Product, ProductPhoto
from sayangin.pilihan import KATEGORI, KONDISI, UKURAN

FOTO_KOSONG = "img/logo.svg"  # Product.image wajib terisi; dipakai kalau iklan tanpa foto


def _simpan_foto(file):
    suffix = PHOTO_TYPES.get(Path(file.name).suffix.lower(), ".jpg")
    photos = marketplace_views.PHOTOS
    return photos.url(photos.save(f"{get_random_string(16)}{suffix}", file))


def _tayangkan_di_marketplace(listing, uploaded, source_item):
    """Buat/perbarui Product dari iklan Lemari supaya tampil di Marketplace dan Jualanku."""
    product = listing.product or Product(seller=listing.owner)
    product.name = listing.title[:120]
    product.description = listing.condition_notes
    product.price = listing.price
    product.category = listing.category
    product.condition = listing.condition
    product.condition_note = listing.condition_notes[:200]
    product.size = listing.size[:10]
    # "Alamat utama · Jakarta Selatan" -> "Jakarta Selatan"
    product.city = listing.shipped_from.split("·")[-1].strip()[:60]
    product.weight_grams = listing.weight
    if source_item:
        product.used_duration = source_item.last_used[:30]

    paths = [_simpan_foto(file) for file in uploaded[:4]]  # Marketplace menampung maksimal 4 foto
    if paths:
        product.image = paths[0]
    elif not product.image:
        if source_item and source_item.photo:
            with source_item.photo.open("rb") as photo:
                product.image = _simpan_foto(photo)
        else:
            product.image = FOTO_KOSONG
    product.save()
    if paths:
        product.extra_photos.all().delete()
        ProductPhoto.objects.bulk_create([ProductPhoto(product=product, image=path) for path in paths[1:]])
    listing.product = product
    listing.save(update_fields=["product"])


def _status_barang(user):
    """{id barang: status} untuk barang yang sedang dijual, terjual, atau didonasikan."""
    status = {}
    listings = SaleListing.objects.filter(
        owner=user, product__isnull=False, source_item__isnull=False
    ).select_related("product")
    for listing in listings:
        terjual = listing.product.is_sold
        status[listing.source_item_id] = {
            "jenis": "dijual",
            "label": "Terjual" if terjual else "Dijual",
            "url": reverse("marketplace:detail", args=[listing.product_id]),
            "aksi": "Lihat di Marketplace",
        }
    tawaran = Penawaran.objects.filter(
        donatur=user,
        status__in=[Penawaran.Status.MENUNGGU, Penawaran.Status.DITERIMA, Penawaran.Status.SELESAI],
    ).exclude(lemari_id="")
    for p in tawaran:
        if p.lemari_id.isdigit():
            status[int(p.lemari_id)] = {
                "jenis": "didonasikan",
                "label": "Didonasikan" if p.status == Penawaran.Status.SELESAI else p.get_status_display(),
                "url": reverse("donasi:tawaran_saya"),
                "aksi": "Lihat donasiku",
            }
    return status


@login_required(login_url="/login/")
def _listing_values(request):
    def integer(name):
        value = request.POST.get(name, "").replace(".", "").replace(",", "").strip()
        return int(value) if value.isdigit() else None

    return {
        "title": request.POST.get("judul", "").strip(),
        "category": request.POST.get("kategori", "").strip(),
        "size": request.POST.get("ukuran", "").strip(),
        "condition": request.POST.get("kondisi", "").strip(),
        "condition_notes": request.POST.get("catatan", "").strip(),
        "price": integer("harga"),
        "weight": integer("berat"),
        "shipped_from": request.POST.get("dikirim_dari", "Depok").strip(),
    }


def _length_error(value, limit, label):
    return f"{label} maksimal {limit} karakter." if len(value) > limit else ""


@login_required(login_url="/login/")
def index(request):
    wardrobe_items = WardrobeItem.objects.filter(owner=request.user)
    if not wardrobe_items.exists():
        return render(request, "lemari/kosong.html")
    status = _status_barang(request.user)
    # Barang yang sudah dijual/didonasikan tidak perlu diingatkan lagi.
    reminder_items = WardrobeItem.objects.filter(owner=request.user, reminder_enabled=True).exclude(pk__in=status)
    wardrobe_count = wardrobe_items.count()
    tab = request.GET.get("tab", "")
    if tab in ("dijual", "didonasikan"):
        wardrobe_items = wardrobe_items.filter(pk__in=[pk for pk, s in status.items() if s["jenis"] == tab])
    else:
        tab = ""
    sort = request.GET.get("sort", "listed")
    usage_order = Case(
        When(last_used="Lebih dari 6 bulan", then=0),
        When(last_used="3–6 bulan lalu", then=1),
        When(last_used="1–3 bulan lalu", then=2),
        When(last_used="Kurang dari 1 bulan", then=3),
        When(last_used="Belum pernah dipakai", then=4),
        default=5,
        output_field=IntegerField(),
    )
    if sort == "usage":
        wardrobe_items = wardrobe_items.annotate(usage_rank=usage_order).order_by(
            "usage_rank", "name"
        )
    elif sort == "category":
        wardrobe_items = wardrobe_items.order_by("category", "name")
    else:
        sort = "listed"
        wardrobe_items = wardrobe_items.order_by("-created_at")
    wardrobe_items = list(wardrobe_items)
    for item in wardrobe_items:
        item.status = status.get(item.pk)
    return render(
        request,
        "lemari/index.html",
        {
            "wardrobe_items": wardrobe_items,
            "wardrobe_count": wardrobe_count,
            "dijual_count": sum(s["jenis"] == "dijual" for s in status.values()),
            "didonasikan_count": sum(s["jenis"] == "didonasikan" for s in status.values()),
            "tab": tab,
            "current_sort": sort,
            "reminder_items": [] if tab else reminder_items,  # pengingat hanya di tab Semua
        },
    )


def kosong(request):
    return render(request, "lemari/kosong.html")


@login_required(login_url="/login/")
def awal(request):
    if request.method == "POST":
        entries = []
        errors = {}
        for number in range(1, 4):
            name = request.POST.get(f"nama_{number}", "").strip()
            category = request.POST.get(f"kategori_{number}", "").strip()
            last_used = request.POST.get(f"terakhir_dipakai_{number}", "").strip()
            has_content = (
                name or category or last_used or request.FILES.get(f"foto_{number}")
            )
            if not has_content:
                continue
            if not name:
                errors[number] = "Isi nama barang."
            elif category not in dict(KATEGORI) or not last_used:
                errors[number] = "Lengkapi kategori dan terakhir dipakai."
            elif len(name) > 160:
                errors[number] = "Nama barang maksimal 160 karakter."
            entries.append((number, name, category, last_used))
        if not entries:
            errors[1] = "Tambahkan setidaknya satu barang ke lemarimu."
        if errors:
            return render(request, "lemari/awal.html", {"errors": errors})
        for number, name, category, last_used in entries:
            item = WardrobeItem(
                owner=request.user,
                name=name,
                category=category,
                last_used=last_used,
            )
            photo = request.FILES.get(f"foto_{number}")
            if photo:
                item.photo = photo
            item.save()
        return redirect("lemari:index")
    return render(request, "lemari/awal.html")


@login_required(login_url="/login/")
def tambah_barang(request):
    edit_id = request.POST.get("edit_item") or request.GET.get("edit")
    item = get_object_or_404(WardrobeItem, pk=edit_id, owner=request.user) if edit_id else None
    if request.method == "POST":
        name = request.POST.get("nama", "").strip()
        category = request.POST.get("kategori", "").strip()
        size = request.POST.get("ukuran", "").strip()
        last_used = request.POST.get("terakhir_dipakai", "").strip()
        color = request.POST.get("warna", "").strip()
        purchased_at = request.POST.get("kapan_dibeli", "").strip()
        notes = request.POST.get("catatan", "").strip()
        photo = request.FILES.get("foto")
        text_limits = ((name, 160, "Nama barang"), (category, 80, "Kategori"), (size, 40, "Ukuran"), (last_used, 40, "Terakhir dipakai"), (color, 80, "Warna"), (purchased_at, 40, "Kapan dibeli"), (notes, 2000, "Catatan"))
        too_long = next((f"{label} maksimal {limit} karakter." for value, limit, label in text_limits if len(value) > limit), "")
        if too_long or not name or category not in dict(KATEGORI) or not last_used or (not item and not photo):
            return render(
                request,
                "lemari/tambah_barang.html",
                {
                    "errors": too_long or "Lengkapi foto, nama barang, kategori, dan terakhir dipakai.",
                    "values": {"name": name, "category": category, "size": size, "last_used": last_used, "color": color, "purchased_at": purchased_at, "notes": notes},
                    "item": item,
                },
            )
        if item:
            item.name, item.category, item.size = name, category, size
            item.last_used, item.color = last_used, color
            item.purchased_at, item.notes = purchased_at, notes
            if photo:
                item.photo = photo
            item.save()
        else:
            item = WardrobeItem.objects.create(owner=request.user, name=name, category=category, size=size, last_used=last_used, color=color, purchased_at=purchased_at, notes=notes, photo=photo)
        if edit_id:
            return redirect("lemari:detail_barang", item_id=item.pk)
        if request.POST.get("action") == "save_add":
            messages.success(request, f"{name} berhasil ditambahkan ke lemarimu.")
            return redirect("lemari:tambah_barang")
        return redirect("lemari:index")
    values = {
        "name": item.name if item else "",
        "category": item.category if item else "",
        "size": item.size if item else "",
        "last_used": item.last_used if item else "",
        "color": item.color if item else "",
        "purchased_at": item.purchased_at if item else "",
        "notes": item.notes if item else "",
    }
    return render(request, "lemari/tambah_barang.html", {"item": item, "values": values})


@login_required(login_url="/login/")
def detail_barang(request, item_id):
    item = get_object_or_404(WardrobeItem, pk=item_id, owner=request.user)
    month_name = ""
    if item.purchased_at:
        try:
            purchased_date = datetime.strptime(item.purchased_at, "%Y-%m")
            months = ("Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September", "Oktober", "November", "Desember")
            month_name = f"{months[purchased_date.month - 1]} {purchased_date.year}"
        except ValueError:
            month_name = item.purchased_at
    return render(request, "lemari/detail_barang.html", {
        "item": item,
        "purchased_label": month_name,
        "item_status": _status_barang(request.user).get(item.pk),
    })


@login_required(login_url="/login/")
def wardrobe_photo(request, item_id):
    item = get_object_or_404(WardrobeItem, pk=item_id, owner=request.user)
    if not item.photo:
        raise Http404
    return FileResponse(item.photo.open("rb"), content_type="image/*")


@login_required(login_url="/login/")
def hapus_item(request, item_id):
    if request.method == "POST":
        get_object_or_404(WardrobeItem, pk=item_id, owner=request.user).delete()
    return redirect("lemari:index")


@login_required(login_url="/login/")
def toggle_reminder(request, item_id):
    if request.method == "POST":
        item = get_object_or_404(WardrobeItem, pk=item_id, owner=request.user)
        item.reminder_enabled = not item.reminder_enabled
        item.save(update_fields=["reminder_enabled"])
    return redirect("lemari:index")


@login_required(login_url="/login/")
def jual(request):
    listing_id = request.POST.get("listing_id") or request.GET.get("listing")
    listing = (
        get_object_or_404(SaleListing, pk=listing_id, owner=request.user)
        if listing_id
        else None
    )
    source_id = (
        request.POST.get("source_item")
        or request.GET.get("item")
        or (listing.source_item_id if listing else None)
    )
    source_item = (
        get_object_or_404(WardrobeItem, pk=source_id, owner=request.user)
        if source_id
        else None
    )
    # Barang yang masih tayang cukup diubah iklannya, jangan sampai tayang dua kali.
    if listing is None and source_item:
        listing = SaleListing.objects.filter(
            owner=request.user, source_item=source_item, product__isnull=False, product__is_sold=False
        ).first()
    if listing and listing.product and listing.product.is_sold:
        messages.error(request, "Barang ini sudah terjual, iklannya tidak bisa diubah.")
        return redirect("lemari:jual_sukses", listing_id=listing.pk)
    if request.method == "POST":
        values = _listing_values(request)
        errors = {}
        text_limits = {
            "title": (160, "Judul"),
            "category": (80, "Kategori"),
            "size": (40, "Ukuran"),
            "condition": (30, "Kondisi"),
            "condition_notes": (2000, "Catatan kondisi"),
            "shipped_from": (120, "Alamat pengiriman"),
        }
        for field, (limit, label) in text_limits.items():
            if values[field]:
                message = _length_error(values[field], limit, label)
                if message:
                    errors[field] = message
        if not values["title"]:
            errors["judul"] = "Isi judul barang."
        if values["category"] not in dict(KATEGORI):
            errors["kategori"] = "Pilih kategori."
        if values["size"] not in UKURAN:
            errors["ukuran"] = "Pilih ukuran."
        if values["condition"] not in dict(KONDISI):
            errors["kondisi"] = (
                "Pilih kondisi supaya pembeli tahu apa yang mereka dapat."
            )
        if not values["price"] or values["price"] < 1000:
            errors["harga"] = "Isi harga minimal Rp1.000."
        if not values["weight"] or values["weight"] <= 0:
            errors["berat"] = "Isi berat barang."
        if errors:
            return render(
                request,
                "lemari/jual.html",
                {
                    "values": values,
                    "errors": errors,
                    "listing": listing,
                    "source_item": source_item,
                },
            )
        if listing is None:
            listing = SaleListing()
        for field, value in values.items():
            setattr(listing, field, value)
        listing.status = SaleListing.PUBLISHED
        listing.source_item = source_item
        if request.user.is_authenticated:
            listing.owner = request.user
        listing.save()
        for image in request.FILES.getlist("photos"):
            ListingPhoto.objects.create(listing=listing, image=image)
        if (
            source_item
            and source_item.photo
            and not request.FILES.getlist("photos")
            and not listing.photos.exists()
        ):
            ListingPhoto.objects.create(listing=listing, image=source_item.photo.name)
        _tayangkan_di_marketplace(listing, request.FILES.getlist("photos"), source_item)
        return redirect("lemari:jual_sukses", listing_id=listing.pk)
    values = {
        "title": (
            listing.title
            if listing
            else (source_item.name if source_item else "Blazer wol abu, ukuran M")
        ),
        "category": (
            listing.category
            if listing
            else (source_item.category if source_item else "")
        ),
        "size": listing.size if listing else (source_item.size if source_item else ""),
        "condition": listing.condition if listing else "terawat",
        "condition_notes": (
            listing.condition_notes
            if listing
            else (source_item.notes if source_item and source_item.notes else "")
        ),
        "price": listing.price if listing else "",
        "weight": listing.weight if listing else 800,
        "shipped_from": (
            listing.shipped_from if listing else "Alamat utama · Jakarta Selatan"
        ),
    }
    return render(
        request,
        "lemari/jual.html",
        {
            "values": values,
            "errors": {},
            "listing": listing,
            "source_item": source_item,
        },
    )


@login_required(login_url="/login/")
def jual_sukses(request, listing_id=None):
    listing = (
        get_object_or_404(SaleListing, pk=listing_id, owner=request.user)
        if listing_id
        else None
    )
    return render(
        request,
        "lemari/jual_sukses.html",
        {"listing": listing, "source_item": listing.source_item if listing else None},
    )
