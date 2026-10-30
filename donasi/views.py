import datetime
import re
from urllib.parse import urlencode

from django.contrib import messages
from django.db.models import Sum
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.template.loader import render_to_string 
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_POST,require_GET, require_http_methods

from .forms import KebutuhanForm, PenawaranForm
from .models import Kategori, Kebutuhan, Kondisi, Penawaran
from .permissions import lembaga_required, donatur_required, is_lembaga

URUTAN = {
    "tenggat": "Tenggat terdekat",
    "progres": "Paling sedikit terpenuhi",
    "terbaru": "Terbaru",
}
FIELD_BARANG = ("nama", "kategori", "ukuran", "kondisi", "foto", "lemari_id")

KATEGORI_LEMARI_MAP = {
    "pakaian · luaran": "pakaian-luaran",
    "pakaian-luaran": "pakaian-luaran",
    "pakaian": "pakaian-atasan",
    "pakaian · atasan": "pakaian-atasan",
    "pakaian-atasan": "pakaian-atasan",
    "pakaian · bawahan": "pakaian-bawahan",
    "pakaian-bawahan": "pakaian-bawahan",
    "sepatu": "alas-kaki",
    "alas-kaki": "alas-kaki",
    "buku": "buku",
    "perlengkapan sekolah": "perlengkapan-sekolah",
    "perlengkapan-sekolah": "perlengkapan-sekolah",
    "mainan": "mainan",
    "perabot": "perabot",
    "lainnya": "lainnya",
}


def _is_htmx(request):
    return request.headers.get("HX-Request") == "true"


def _barang_dari_request(request):
    """Data barang dari Lemari Digital yang dibawa lewat query string."""
    data = {f: request.GET.get(f, "").strip() for f in FIELD_BARANG}
    # Ubah format kategori teks menjadi slug kategori donasi
    kat_raw = data.get("kategori", "").lower()
    if kat_raw in KATEGORI_LEMARI_MAP:
        data["kategori"] = KATEGORI_LEMARI_MAP[kat_raw]
    return data


def _label_kondisi(kode):
    return Kondisi(kode).label if kode in Kondisi.values else ""


def urutkan_kebutuhan(daftar, urut):
    if urut == "progres":
        return sorted(daftar, key=lambda k: (k.persen, k.pk))
    if urut == "terbaru":
        return sorted(daftar, key=lambda k: k.dibuat, reverse=True)
    paling_jauh = datetime.date.max
    return sorted(daftar, key=lambda k: (k.tenggat or paling_jauh, k.pk))


# ---------------------------------------------------------------------------
# Sisi donatur
# ---------------------------------------------------------------------------
@donatur_required
def pilih_lembaga(request):
    barang = _barang_dari_request(request)
    urut = request.GET.get("urut", "tenggat")
    if urut not in URUTAN:
        urut = "tenggat"

    daftar = Kebutuhan.objects.cocok_dengan(
        kategori=barang["kategori"], ukuran=barang["ukuran"], kondisi=barang["kondisi"]
    )
    daftar = urutkan_kebutuhan(daftar, urut)

    konteks = {
        "barang": barang,
        "kondisi_label": _label_kondisi(barang["kondisi"]),
        "barang_query": urlencode({k: v for k, v in barang.items() if v}),
        "daftar": daftar,
        "urut": urut,
        "urutan": URUTAN,
    }
    if _is_htmx(request):
        return render(request, "donasi/_org_list.html", konteks)
    return render(request, "donasi/pilih_lembaga.html", konteks)


@donatur_required
def kirim_donasi(request, kebutuhan_id):
    kebutuhan = get_object_or_404(
        Kebutuhan.objects.aktif().select_related("lembaga"), pk=kebutuhan_id)
    barang = _barang_dari_request(request)

    if not barang["nama"]:
        messages.error(request, "Pilih barang yang ingin kamu donasikan terlebih dahulu.")
        return redirect("donasi:pilih_lembaga")

    kondisi = barang["kondisi"] if barang["kondisi"] in Kondisi.values else Kondisi.TERAWAT
    FOTO_AMAN = re.compile(r"^(https?://|/)[^\s'\"()\\]+$")
    foto = barang["foto"] if FOTO_AMAN.match(barang["foto"]) else ""

    if request.method == "POST":
        form = PenawaranForm(request.POST, kebutuhan=kebutuhan)
        if form.is_valid():
            penawaran = form.save(commit=False)
            penawaran.donatur = request.user
            penawaran.lembaga = kebutuhan.lembaga
            penawaran.kebutuhan = kebutuhan
            penawaran.nama_barang = barang["nama"][:120]
            penawaran.ukuran = barang["ukuran"][:30]
            penawaran.kondisi = kondisi
            penawaran.jumlah = 1
            penawaran.foto_url = foto
            penawaran.lemari_id = barang["lemari_id"][:50]
            penawaran.save()
            messages.success(request, "Tawaran donasi terkirim. Lembaga akan menjawab dalam 2 hari.")
            return redirect("donasi:tawaran_saya")
    else:
        form = PenawaranForm(kebutuhan=kebutuhan)

    return render(request, "donasi/kirim_donasi.html", {
        "form": form,
        "kebutuhan": kebutuhan,
        "barang": barang,
        "foto": foto,
        "kondisi_label": _label_kondisi(kondisi),
    })


@donatur_required
def tawaran_saya(request):
    daftar = Penawaran.objects.filter(donatur=request.user).select_related("lembaga", "kebutuhan")
    status = request.GET.get("status", "")
    if status in Penawaran.Status.values:
        daftar = daftar.filter(status=status)
    return render(request, "donasi/tawaran_saya.html", {
        "daftar": daftar, "status": status, "opsi_status": Penawaran.Status.choices,
    })


@donatur_required
@require_http_methods(["DELETE", "POST"])
def batalkan_tawaran(request, pk):
    penawaran = get_object_or_404(
        Penawaran, pk=pk, donatur=request.user, status=Penawaran.Status.MENUNGGU
    )
    penawaran.delete()
    if _is_htmx(request):
        return HttpResponse("")
    messages.success(request, "Tawaran donasi dibatalkan.")
    return redirect("donasi:tawaran_saya")


# ---------------------------------------------------------------------------
# Sisi lembaga mitra
# ---------------------------------------------------------------------------
@lembaga_required
def dashboard_lembaga(request):
    sekarang = timezone.now()
    milik = Penawaran.objects.filter(lembaga=request.user)
    tawaran = list(
        milik.filter(status__in=[Penawaran.Status.MENUNGGU, Penawaran.Status.DITERIMA])
        .select_related("donatur", "kebutuhan")
    )
    tawaran.sort(key=lambda p: p.status != Penawaran.Status.MENUNGGU)

    kebutuhan_aktif = Kebutuhan.objects.filter(lembaga=request.user, status=Kebutuhan.Status.AKTIF)
    diterima_bulan_ini = milik.filter(
        status=Penawaran.Status.SELESAI,
        diterima_pada__year=sekarang.year,
        diterima_pada__month=sekarang.month,
    ).aggregate(total=Sum("jumlah"))["total"] or 0

    return render(request, "donasi/lembaga_dashboard.html", {
        "tawaran": tawaran,
        "jumlah_menunggu": milik.filter(status=Penawaran.Status.MENUNGGU).count(),
        "kebutuhan_aktif": kebutuhan_aktif,
        "diterima_bulan_ini": diterima_bulan_ini,
    })


@lembaga_required
def riwayat_lembaga(request):
    daftar = Penawaran.objects.filter(
        lembaga=request.user,
        status__in=[Penawaran.Status.SELESAI, Penawaran.Status.DITOLAK],
    ).select_related("donatur", "kebutuhan")
    return render(request, "donasi/lembaga_riwayat.html", {"daftar": daftar})


@lembaga_required
def kebutuhan_list(request):
    daftar = Kebutuhan.objects.filter(lembaga=request.user)
    q = request.GET.get("q", "").strip()
    status = request.GET.get("status", "")
    if q:
        daftar = daftar.filter(nama_barang__icontains=q)
    if status in Kebutuhan.Status.values:
        daftar = daftar.filter(status=status)
    konteks = {"daftar": daftar, "q": q, "status": status, "opsi_status": Kebutuhan.Status.choices}
    if _is_htmx(request):
        return render(request, "donasi/_need_rows.html", konteks)
    return render(request, "donasi/kebutuhan_list.html", konteks)


def _form_kebutuhan(request, instance=None):
    if request.method == "POST":
        form = KebutuhanForm(request.POST, instance=instance)
        if form.is_valid():
            kebutuhan = form.save(commit=False)
            kebutuhan.lembaga = request.user
            if request.POST.get("aksi") == "draf":
                kebutuhan.status = Kebutuhan.Status.DRAFT
            elif kebutuhan.terpenuhi >= kebutuhan.jumlah:
                kebutuhan.status = Kebutuhan.Status.SELESAI
            else:
                kebutuhan.status = Kebutuhan.Status.AKTIF
            kebutuhan.save()
            if kebutuhan.status == Kebutuhan.Status.DRAFT:
                messages.success(request, "Draf kebutuhan disimpan.")
            else:
                messages.success(request, "Kebutuhan ditayangkan.")
            return redirect("donasi:dashboard_lembaga")
    else:
        form = KebutuhanForm(instance=instance)
    return render(request, "donasi/kebutuhan_form.html", {
        "form": form, "kebutuhan": instance,
        "preview": instance or Kebutuhan(lembaga=request.user, nama_barang="", jumlah=0),
    })


@lembaga_required
def kebutuhan_buat(request):
    return _form_kebutuhan(request)


@lembaga_required
def kebutuhan_ubah(request, pk):
    kebutuhan = get_object_or_404(Kebutuhan, pk=pk, lembaga=request.user)
    return _form_kebutuhan(request, kebutuhan)


@lembaga_required
@require_http_methods(["DELETE", "POST"])
def kebutuhan_hapus(request, pk):
    kebutuhan = get_object_or_404(Kebutuhan, pk=pk, lembaga=request.user)
    kebutuhan.delete()
    if _is_htmx(request):
        return HttpResponse("")
    messages.success(request, "Kebutuhan dihapus.")
    return redirect("donasi:kebutuhan_list")


@lembaga_required
@require_POST
def kebutuhan_pratinjau(request):
    """Fragment pratinjau 'begini donatur melihatnya' dari isi form yang belum disimpan."""
    d = request.POST
    try:
        jumlah = max(int(d.get("jumlah") or 0), 0)
    except ValueError:
        jumlah = 0
    kebutuhan = Kebutuhan(
        lembaga=request.user,
        nama_barang=d.get("nama_barang", "").strip(),
        kategori=d.get("kategori", Kategori.LAINNYA),
        jumlah=jumlah,
        ukuran=",".join(d.getlist("ukuran")),
        kondisi_min=d.get("kondisi_min", Kondisi.TERAWAT),
        tenggat=parse_date(d.get("tenggat", "") or ""),
        foto_url=d.get("foto_url", "").strip(),
        cerita=d.get("cerita", "").strip(),
    )
    return render(request, "donasi/_preview_card.html", {"preview": kebutuhan})


def _aksi_penawaran(request, pk, aksi):
    penawaran = get_object_or_404(
        Penawaran.objects.select_related("donatur", "kebutuhan"), pk=pk, lembaga=request.user
    )
    berhasil = getattr(penawaran, aksi)()
    if not berhasil:
        messages.error(request, "Status tawaran ini sudah berubah.")

    if _is_htmx(request):
        html = render_to_string("donasi/_offer_row.html", {"p": penawaran}, request=request)

        jumlah_menunggu = Penawaran.objects.filter(
            lembaga=request.user, status=Penawaran.Status.MENUNGGU
        ).count()
        html += f'<span class="stat__value serif" id="stat-menunggu" hx-swap-oob="true">{jumlah_menunggu}</span>'

        if berhasil and aksi == "selesaikan" and penawaran.kebutuhan:
            k = penawaran.kebutuhan 
            if k.status == Kebutuhan.Status.AKTIF:
                html += render_to_string(
                    "donasi/_need_row.html", {"k": k, "oob": True}, request=request)
            else:
                html += f'<div id="need-{k.pk}" hx-swap-oob="delete"></div>'
        return HttpResponse(html)

    return redirect("donasi:dashboard_lembaga")


@lembaga_required
@require_POST
def penawaran_terima(request, pk):
    return _aksi_penawaran(request, pk, "terima")


@lembaga_required
@require_POST
def penawaran_tolak(request, pk):
    return _aksi_penawaran(request, pk, "tolak")


@lembaga_required
@require_POST
def penawaran_selesai(request, pk):
    return _aksi_penawaran(request, pk, "selesaikan")


# ---------------------------------------------------------------------------
# Data delivery (JSON)
# ---------------------------------------------------------------------------
def _kebutuhan_dict(k, login=False):
    data = {
        "id": k.pk,
        "lembaga": k.nama_lembaga,
        "nama_barang": k.nama_barang,
        "kategori": k.kategori,
        "jumlah": k.jumlah,
        "terpenuhi": k.terpenuhi,
        "sisa": k.sisa,
        "persen": k.persen,
        "ukuran": k.ukuran_list,
        "kondisi_min": k.kondisi_min,
        "tenggat": k.tenggat.isoformat() if k.tenggat else None,
        "foto_url": k.foto_url,
        "cerita": k.cerita,
    }
    if login:
        data["jumlah_tawaran_menunggu"] = (
            k.penawaran.filter(status=Penawaran.Status.MENUNGGU).count()
        )
    return data


def _penawaran_dict(p):
    nama_lembaga = (
        p.lembaga.institution_profile.name
        if hasattr(p.lembaga, "institution_profile") and p.lembaga.institution_profile.name
        else (p.lembaga.get_full_name() or p.lembaga.username)
    )
    return {
        "id": p.pk,
        "kebutuhan_id": p.kebutuhan_id,
        "lembaga": nama_lembaga,
        "donatur": p.donatur.username,
        "nama_barang": p.nama_barang,
        "jumlah": p.jumlah,
        "kondisi": p.kondisi,
        "metode": p.metode,
        "tanggal_rencana": p.tanggal_rencana.isoformat() if p.tanggal_rencana else None,
        "status": p.status,
        "dibuat": p.dibuat.isoformat(),
    }


@require_GET
def kebutuhan_json(request):
    daftar = Kebutuhan.objects.aktif().select_related("lembaga")
    kategori = request.GET.get("kategori", "")
    q = request.GET.get("q", "").strip()
    if kategori in Kategori.values:
        daftar = daftar.filter(kategori=kategori)
    if q:
        daftar = daftar.filter(nama_barang__icontains=q)
    login = request.user.is_authenticated
    hasil = [_kebutuhan_dict(k, login) for k in daftar]
    return JsonResponse({"count": len(hasil), "results": hasil})


@require_GET
def kebutuhan_json_by_id(request, pk):
    k = get_object_or_404(Kebutuhan.objects.aktif().select_related("lembaga"), pk=pk)
    return JsonResponse(_kebutuhan_dict(k, request.user.is_authenticated))


@require_GET
def penawaran_json(request):
    if not request.user.is_authenticated:
        return JsonResponse({"detail": "Login diperlukan."}, status=401)
    if is_lembaga(request.user):
        daftar = Penawaran.objects.filter(lembaga=request.user)
    else:
        daftar = Penawaran.objects.filter(donatur=request.user)
    daftar = daftar.select_related("donatur", "lembaga")
    hasil = [_penawaran_dict(p) for p in daftar]
    return JsonResponse({"count": len(hasil), "results": hasil})