from django.contrib import messages
from django.db.models import Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_POST, require_http_methods
from .forms import KebutuhanForm
from .models import Kategori, Kebutuhan, Kondisi, Penawaran
from .permissions import lembaga_required

def _is_htmx(request):
    return request.headers.get("HX-Request") == "true"

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
    tawaran.sort(key=lambda p: p.status != Penawaran.Status.MENUNGGU)  # yang menunggu di atas (sort stabil)

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
    if not getattr(penawaran, aksi)():
        messages.error(request, "Status tawaran ini sudah berubah.")
    if _is_htmx(request):
        return render(request, "donasi/_offer_row.html", {"p": penawaran})
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