from django.db import transaction
from django.db.models import Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from .models import Kategori, Kebutuhan, Penawaran
from .permissions import IsDonaturUser, IsLembagaOrReadOnly, IsLembagaUser, is_lembaga
from .serializers import KebutuhanSerializer, PenawaranSerializer


class CsrfExemptSessionAuthentication(SessionAuthentication):
    """Session authentication tanpa pembatalan CSRF, ramah untuk klien Flutter (pbp_django_auth)."""
    def enforce_csrf(self, request):
        return


# ===========================================================================
# API KEBUTUHAN
# ===========================================================================

@api_view(["GET", "POST"])
@authentication_classes([CsrfExemptSessionAuthentication, SessionAuthentication])
@permission_classes([IsLembagaOrReadOnly])
def api_kebutuhan_list(request):
    """
    GET: Melihat daftar kebutuhan aktif (bisa filter ?q= dan ?kategori=).
    POST: Membuat kebutuhan donasi baru (Khusus Lembaga Mitra).
    """
    if request.method == "GET":
        kebutuhan_qs = Kebutuhan.objects.aktif().select_related("lembaga")
        kategori = request.query_params.get("kategori", "").strip()
        q = request.query_params.get("q", "").strip()

        if kategori and kategori in Kategori.values:
            kebutuhan_qs = kebutuhan_qs.filter(kategori=kategori)
        if q:
            kebutuhan_qs = kebutuhan_qs.filter(nama_barang__icontains=q)

        serializer = KebutuhanSerializer(kebutuhan_qs, many=True, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    # POST: Lembaga membuat kebutuhan
    serializer = KebutuhanSerializer(data=request.data, context={"request": request})
    serializer.is_valid(raise_exception=True)
    status_input = request.data.get("status", Kebutuhan.Status.AKTIF)
    if status_input not in Kebutuhan.Status.values:
        status_input = Kebutuhan.Status.AKTIF

    serializer.save(lembaga=request.user, status=status_input)
    return Response(serializer.data, status=status.HTTP_201_CREATED)


@api_view(["GET", "PUT", "PATCH", "DELETE"])
@authentication_classes([CsrfExemptSessionAuthentication, SessionAuthentication])
@permission_classes([IsLembagaOrReadOnly])
def api_kebutuhan_detail(request, pk):
    """
    GET: Detail satu kebutuhan.
    PUT/PATCH: Mengubah kebutuhan (hanya oleh lembaga pemilik).
    DELETE: Menghapus kebutuhan (hanya oleh lembaga pemilik).
    """
    kebutuhan = get_object_or_404(Kebutuhan, pk=pk)

    if request.method == "GET":
        serializer = KebutuhanSerializer(kebutuhan, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    # Validasi kepemilikan untuk aksi tulis
    if kebutuhan.lembaga != request.user:
        return Response(
            {"detail": "Anda tidak memiliki izin mengelola kebutuhan lembaga lain."},
            status=status.HTTP_403_FORBIDDEN,
        )

    if request.method == "DELETE":
        kebutuhan.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    serializer = KebutuhanSerializer(
        kebutuhan,
        data=request.data,
        partial=(request.method == "PATCH"),
        context={"request": request},
    )
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(["GET"])
@authentication_classes([CsrfExemptSessionAuthentication, SessionAuthentication])
@permission_classes([IsLembagaUser])
def api_kebutuhan_saya(request):
    """Daftar seluruh kebutuhan yang dibuat oleh lembaga yang sedang login."""
    daftar = Kebutuhan.objects.filter(lembaga=request.user).order_by("-dibuat")
    serializer = KebutuhanSerializer(daftar, many=True, context={"request": request})
    return Response(serializer.data, status=status.HTTP_200_OK)


# ===========================================================================
# API PENAWARAN
# ===========================================================================

@api_view(["GET", "POST"])
@authentication_classes([CsrfExemptSessionAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated])
def api_penawaran_list(request):
    """
    GET: Daftar tawaran donasi (otomatis filter milik Donatur atau Lembaga login).
    POST: Membuat penawaran donasi baru (Khusus Donatur).
    """
    if request.method == "GET":
        if is_lembaga(request.user):
            daftar = Penawaran.objects.filter(lembaga=request.user)
        else:
            daftar = Penawaran.objects.filter(donatur=request.user)
        daftar = daftar.select_related("donatur", "lembaga", "kebutuhan").order_by("-dibuat")
        serializer = PenawaranSerializer(daftar, many=True, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    # POST: Kirim donasi (hanya donatur)
    if is_lembaga(request.user):
        return Response(
            {"detail": "Akun lembaga tidak dapat mendonasikan barang."},
            status=status.HTTP_403_FORBIDDEN,
        )

    kebutuhan_id = request.data.get("kebutuhan")
    if not kebutuhan_id:
        return Response({"detail": "Field 'kebutuhan' wajib disertakan."}, status=status.HTTP_400_BAD_REQUEST)

    kebutuhan = get_object_or_404(Kebutuhan.objects.aktif(), pk=kebutuhan_id)

    # Cegah tawaran duplikat untuk item lemari yang sama
    lemari_id = str(request.data.get("lemari_id", "")).strip()
    if lemari_id and Penawaran.objects.filter(
        donatur=request.user,
        lemari_id=lemari_id,
        status__in=[Penawaran.Status.MENUNGGU, Penawaran.Status.DITERIMA, Penawaran.Status.SELESAI],
    ).exists():
        return Response(
            {"detail": "Barang ini sudah pernah Anda tawarkan dan sedang diproses."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    serializer = PenawaranSerializer(data=request.data, context={"request": request})
    serializer.is_valid(raise_exception=True)
    serializer.save(donatur=request.user, lembaga=kebutuhan.lembaga, kebutuhan=kebutuhan)
    return Response(serializer.data, status=status.HTTP_201_CREATED)


@api_view(["GET"])
@authentication_classes([CsrfExemptSessionAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated])
def api_penawaran_detail(request, pk):
    """Melihat detail satu penawaran donasi."""
    penawaran = get_object_or_404(Penawaran.objects.select_related("donatur", "lembaga", "kebutuhan"), pk=pk)
    if penawaran.donatur != request.user and penawaran.lembaga != request.user:
        return Response({"detail": "Akses ditolak."}, status=status.HTTP_403_FORBIDDEN)

    serializer = PenawaranSerializer(penawaran, context={"request": request})
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(["POST"])
@authentication_classes([CsrfExemptSessionAuthentication, SessionAuthentication])
@permission_classes([IsDonaturUser])
def api_penawaran_batal(request, pk):
    """Donatur membatalkan tawaran miliknya yang masih berstatus menunggu."""
    penawaran = get_object_or_404(Penawaran, pk=pk, donatur=request.user)
    if penawaran.status != Penawaran.Status.MENUNGGU:
        return Response(
            {"detail": "Tawaran ini tidak dapat dibatalkan karena sudah diproses oleh lembaga."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    penawaran.delete()
    return Response({"detail": "Tawaran donasi berhasil dibatalkan."}, status=status.HTTP_200_OK)


# ===========================================================================
# AKSI KEPUTUSAN LEMBAGA (Terima / Tolak / Selesaikan)
# ===========================================================================

@api_view(["POST"])
@authentication_classes([CsrfExemptSessionAuthentication, SessionAuthentication])
@permission_classes([IsLembagaUser])
def api_penawaran_terima(request, pk):
    penawaran = get_object_or_404(Penawaran, pk=pk, lembaga=request.user)
    if not penawaran.terima():
        return Response(
            {"detail": "Hanya tawaran dengan status 'menunggu' yang dapat diterima."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    serializer = PenawaranSerializer(penawaran, context={"request": request})
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(["POST"])
@authentication_classes([CsrfExemptSessionAuthentication, SessionAuthentication])
@permission_classes([IsLembagaUser])
def api_penawaran_tolak(request, pk):
    penawaran = get_object_or_404(Penawaran, pk=pk, lembaga=request.user)
    if not penawaran.tolak():
        return Response(
            {"detail": "Hanya tawaran dengan status 'menunggu' yang dapat ditolak."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    serializer = PenawaranSerializer(penawaran, context={"request": request})
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(["POST"])
@authentication_classes([CsrfExemptSessionAuthentication, SessionAuthentication])
@permission_classes([IsLembagaUser])
def api_penawaran_selesai(request, pk):
    penawaran = get_object_or_404(Penawaran, pk=pk, lembaga=request.user)
    if not penawaran.selesaikan():
        return Response(
            {"detail": "Hanya tawaran berstatus 'diterima' yang dapat ditandai selesai (barang diterima fisik)."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    serializer = PenawaranSerializer(penawaran, context={"request": request})
    return Response(serializer.data, status=status.HTTP_200_OK)


# ===========================================================================
# STATISTIK DASHBOARD LEMBAGA
# ===========================================================================

@api_view(["GET"])
@authentication_classes([CsrfExemptSessionAuthentication, SessionAuthentication])
@permission_classes([IsLembagaUser])
def api_lembaga_dashboard(request):
    sekarang = timezone.localdate()
    milik = Penawaran.objects.filter(lembaga=request.user)
    jumlah_menunggu = milik.filter(status=Penawaran.Status.MENUNGGU).count()
    kebutuhan_aktif_count = Kebutuhan.objects.filter(lembaga=request.user, status=Kebutuhan.Status.AKTIF).count()
    diterima_bulan_ini = (
        milik.filter(
            status=Penawaran.Status.SELESAI,
            diterima_pada__year=sekarang.year,
            diterima_pada__month=sekarang.month,
        ).aggregate(total=Sum("jumlah"))["total"]
        or 0
    )
    return Response({
        "jumlah_menunggu": jumlah_menunggu,
        "kebutuhan_aktif": kebutuhan_aktif_count,
        "diterima_bulan_ini": diterima_bulan_ini,
    }, status=status.HTTP_200_OK)