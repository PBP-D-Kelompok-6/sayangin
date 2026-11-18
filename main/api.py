import json
import os
import re

import requests
from django.conf import settings
from django.contrib.auth import login, logout
from django.contrib.auth.models import User
from django.core import serializers as django_serializers
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.urls import reverse
from rest_framework import permissions, status, viewsets
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import action, api_view, authentication_classes, permission_classes
from rest_framework.response import Response

from donasi.models import Kebutuhan, Penawaran
from impact.views import get_user_impact_summary
from main.models import InstitutionProfile, UserAddress, UserProfile
from main.permissions import IsLembaga, IsPersonal
from main.serializers import (
    ChangePasswordSerializer,
    DeleteAccountSerializer,
    InstitutionProfileSerializer,
    InstitutionPublicSerializer,
    LoginSerializer,
    PreferencesSerializer,
    ProfileUpdateSerializer,
    RegisterSerializer,
    UserAddressSerializer,
    UserSummarySerializer,
)
from main.services import (
    delete_user_address_and_sync,
    ensure_user_addresses_synced,
    filter_user_addresses,
    first_error_message,
    generate_unique_username,
    get_name_parts,
    is_institution_profile_complete,
)
from marketplace.ongkir import search_destinations


class CsrfExemptSessionAuthentication(SessionAuthentication):
    """Session cookie auth tanpa penolakan CSRF, cocok untuk Flutter (pbp_django_auth) & web."""

    def enforce_csrf(self, request):
        return


def _error_response(serializer, http_status=status.HTTP_400_BAD_REQUEST):
    return Response(
        {
            "status": "error",
            "message": first_error_message(serializer.errors),
            "errors": serializer.errors,
        },
        status=http_status,
    )


def _auth_next_step(user, profile: UserProfile) -> str:
    if profile.role == "LEMBAGA":
        if not is_institution_profile_complete(user):
            return "edit_institution_profile"
        return "dashboard_lembaga"
    has_address = bool(profile.address.strip() or UserAddress.objects.filter(user=user).exists())
    return "show_main" if has_address else "edit_profile"


# ---------------------------------------------------------------------------
# Authentication & Session
# ---------------------------------------------------------------------------

@api_view(["POST"])
@authentication_classes([CsrfExemptSessionAuthentication])
@permission_classes([permissions.AllowAny])
def api_login(request):
    serializer = LoginSerializer(data=request.data, context={"request": request._request})
    if not serializer.is_valid():
        return _error_response(serializer, status.HTTP_400_BAD_REQUEST)

    user = serializer.validated_data["user"]
    login(request._request, user)
    profile, _ = UserProfile.objects.get_or_create(user=user)
    return Response(
        {
            "status": "ok",
            "message": "Berhasil masuk.",
            "user": UserSummarySerializer(user).data,
            "next_step": _auth_next_step(user, profile),
        },
        status=status.HTTP_200_OK,
    )


@api_view(["POST"])
@authentication_classes([CsrfExemptSessionAuthentication])
@permission_classes([permissions.AllowAny])
def api_register(request):
    serializer = RegisterSerializer(data=request.data)
    if not serializer.is_valid():
        return _error_response(serializer, status.HTTP_400_BAD_REQUEST)

    user = serializer.save()
    login(request._request, user)
    profile, _ = UserProfile.objects.get_or_create(user=user)
    return Response(
        {
            "status": "ok",
            "message": "Akun berhasil dibuat.",
            "user": UserSummarySerializer(user).data,
            "next_step": _auth_next_step(user, profile),
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(["POST"])
@authentication_classes([CsrfExemptSessionAuthentication])
@permission_classes([permissions.IsAuthenticated])
def api_logout(request):
    logout(request._request)
    return Response({"status": "ok", "message": "Berhasil keluar."}, status=status.HTTP_200_OK)


@api_view(["GET"])
@authentication_classes([CsrfExemptSessionAuthentication])
@permission_classes([permissions.IsAuthenticated])
def api_auth_me(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    payload = {
        "status": "ok",
        "authenticated": True,
        "user": UserSummarySerializer(request.user).data,
        "next_step": _auth_next_step(request.user, profile),
    }
    if profile.role == "LEMBAGA":
        inst = InstitutionProfile.objects.filter(user=request.user).first()
        payload["institution"] = (
            InstitutionProfileSerializer(inst, context={"request": request}).data if inst else None
        )
    else:
        addresses = ensure_user_addresses_synced(request.user, profile)
        primary = addresses.filter(is_primary=True).first() or addresses.first()
        payload["primary_address"] = UserAddressSerializer(primary).data if primary else None
    return Response(payload, status=status.HTTP_200_OK)


@api_view(["POST"])
@authentication_classes([CsrfExemptSessionAuthentication])
@permission_classes([permissions.AllowAny])
def api_google_auth(request):
    """Login, registrasi, atau hubungkan akun Google (via id_token atau chooser dev saat DEBUG)."""
    id_token = (request.data.get("id_token") or "").strip()
    action_type = (request.data.get("action") or "login").strip().lower()
    jenis = (request.data.get("jenis") or request.data.get("role") or "pribadi").strip().lower()
    client_id = os.getenv("GOOGLE_CLIENT_ID", "").strip()

    google_email = ""
    google_name = ""

    if id_token:
        if not settings.DEBUG and not client_id:
            return Response(
                {"status": "error", "message": "Login Google belum tersedia."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        try:
            res = requests.get(
                "https://oauth2.googleapis.com/tokeninfo",
                params={"id_token": id_token},
                timeout=10,
            )
            if res.status_code != 200:
                return Response(
                    {"status": "error", "message": "Token Google tidak valid."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            info = res.json()
            if client_id and info.get("aud") != client_id:
                return Response(
                    {"status": "error", "message": "Token Google bukan untuk aplikasi ini."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if str(info.get("email_verified", "")).lower() not in ("true", "1"):
                return Response(
                    {"status": "error", "message": "Email Google belum terverifikasi."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            google_email = (info.get("email") or "").strip().lower()
            google_name = (info.get("name") or "").strip()
        except requests.RequestException:
            return Response(
                {"status": "error", "message": "Gagal memverifikasi token Google."},
                status=status.HTTP_502_BAD_GATEWAY,
            )
    elif settings.DEBUG and not client_id:
        google_email = (request.data.get("email") or "").strip().lower()
        google_name = (request.data.get("full_name") or "").strip()
    else:
        return Response(
            {"status": "error", "message": "id_token Google wajib disertakan."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not google_email or not re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", google_email):
        return Response(
            {"status": "error", "message": "Alamat email Google tidak valid."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not google_name:
        local_part = google_email.split("@")[0].replace(".", " ").replace("_", " ")
        google_name = local_part.title()

    if action_type == "connect":
        if not request.user.is_authenticated:
            return Response(
                {"status": "error", "message": "Masuk terlebih dahulu untuk menghubungkan akun Google."},
                status=status.HTTP_403_FORBIDDEN,
            )
        conflict = (
            UserProfile.objects.filter(google_connected=True, google_email__iexact=google_email)
            .exclude(user=request.user)
            .exists()
        )
        if conflict:
            return Response(
                {"status": "error", "message": "Akun Google tersebut sudah terhubung ke akun lain."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        profile.google_connected = True
        profile.google_email = google_email
        profile.save(update_fields=["google_connected", "google_email"])
        return Response(
            {
                "status": "ok",
                "message": f"Akun Google ({google_email}) berhasil dihubungkan.",
                "user": UserSummarySerializer(request.user).data,
            },
            status=status.HTTP_200_OK,
        )

    linked_profile = (
        UserProfile.objects.filter(google_email__iexact=google_email).select_related("user").first()
    )
    if linked_profile:
        user = linked_profile.user
        is_new_user = False
    else:
        user = User.objects.filter(email__iexact=google_email).first()
        is_new_user = user is None

    if is_new_user:
        username = generate_unique_username(google_email)
        user = User(username=username, email=google_email)
        user.set_unusable_password()
        user.save()
        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.role = "LEMBAGA" if jenis == "lembaga" else "PERSONAL"
        profile.full_name = google_name
        profile.google_connected = True
        profile.google_email = google_email
        profile.save()
    else:
        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.google_connected = True
        profile.google_email = google_email
        if not profile.full_name.strip() and google_name:
            profile.full_name = google_name
        profile.save()

    user.profile = profile
    login(request._request, user)
    return Response(
        {
            "status": "ok",
            "message": "Berhasil masuk dengan Google.",
            "is_new_user": is_new_user,
            "user": UserSummarySerializer(user).data,
            "next_step": _auth_next_step(user, profile),
        },
        status=status.HTTP_201_CREATED if is_new_user else status.HTTP_200_OK,
    )


# ---------------------------------------------------------------------------
# Mobile Auth Endpoints (pbp_django_auth / CookieRequest compatibility)
# ---------------------------------------------------------------------------

@api_view(["POST"])
@authentication_classes([CsrfExemptSessionAuthentication])
@permission_classes([permissions.AllowAny])
def auth_login_pbp(request):
    """POST /auth/login/ untuk Flutter pbp_django_auth (CookieRequest.login)."""
    serializer = LoginSerializer(data=request.data, context={"request": request._request})
    if not serializer.is_valid():
        return Response(
            {
                "status": False,
                "message": "Email/username atau kata sandi salah.",
            },
            status=status.HTTP_401_UNAUTHORIZED,
        )

    user = serializer.validated_data["user"]
    login(request._request, user)
    profile, _ = UserProfile.objects.get_or_create(user=user)
    return Response(
        {
            "status": True,
            "message": "Login berhasil",
            "username": user.username,
            "role": profile.role,
        },
        status=status.HTTP_200_OK,
    )


@api_view(["POST"])
@authentication_classes([CsrfExemptSessionAuthentication])
@permission_classes([permissions.AllowAny])
def auth_logout_pbp(request):
    """POST /auth/logout/ untuk Flutter pbp_django_auth (CookieRequest.logout)."""
    logout(request._request)
    return Response(
        {
            "status": True,
            "message": "Logout berhasil",
        },
        status=status.HTTP_200_OK,
    )


@api_view(["POST"])
@authentication_classes([CsrfExemptSessionAuthentication])
@permission_classes([permissions.AllowAny])
def auth_register_pbp(request):
    """POST /auth/register/ untuk Flutter pbp_django_auth."""
    serializer = RegisterSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            {
                "status": False,
                "message": first_error_message(serializer.errors),
                "errors": serializer.errors,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    user = serializer.save()
    login(request._request, user)
    profile, _ = UserProfile.objects.get_or_create(user=user)
    return Response(
        {
            "status": True,
            "message": "Akun berhasil dibuat.",
            "username": user.username,
            "role": profile.role,
        },
        status=status.HTTP_201_CREATED,
    )


# ---------------------------------------------------------------------------
# Personal Profile & Preferences
# ---------------------------------------------------------------------------

@api_view(["GET"])
@authentication_classes([CsrfExemptSessionAuthentication])
@permission_classes([permissions.IsAuthenticated])
def api_profile_data(request):
    """Structured JSON untuk profil, dampak, preferensi, dan daftar alamat (DRF)."""
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    _, first_name, _ = get_name_parts(request.user, profile)

    if profile.role == "LEMBAGA":
        inst = InstitutionProfile.objects.filter(user=request.user).first()
        return Response(
            {
                "status": "ok",
                "user": {
                    "id": request.user.pk,
                    "username": request.user.username,
                    "email": request.user.email,
                    "first_name": first_name,
                    "full_name": profile.full_name,
                    "phone_number": profile.phone_number,
                    "role": profile.role,
                },
                "institution": (
                    InstitutionProfileSerializer(inst, context={"request": request}).data
                    if inst
                    else None
                ),
                "is_complete": is_institution_profile_complete(request.user),
            }
        )

    all_addresses = ensure_user_addresses_synced(request.user, profile)
    primary_addr = all_addresses.filter(is_primary=True).first() or all_addresses.first()
    filtered_addresses = filter_user_addresses(
        all_addresses,
        label=request.GET.get("label", ""),
        query=request.GET.get("q", ""),
    )

    return Response(
        {
            "status": "ok",
            "user": {
                "id": request.user.pk,
                "username": request.user.username,
                "email": request.user.email,
                "first_name": first_name,
                "full_name": profile.full_name,
                "phone_number": profile.phone_number,
                "role": profile.role,
            },
            "impact": get_user_impact_summary(request.user),
            "preferences": profile.get_preferences_dict(),
            "addresses": UserAddressSerializer(filtered_addresses, many=True).data,
            "primary_address": UserAddressSerializer(primary_addr).data if primary_addr else None,
            "serialized_addresses": json.loads(
                django_serializers.serialize("json", filtered_addresses)
            ),
        }
    )


@api_view(["POST", "PUT", "PATCH"])
@authentication_classes([CsrfExemptSessionAuthentication])
@permission_classes([IsPersonal])
def api_update_profile(request):
    serializer = ProfileUpdateSerializer(data=request.data, context={"request": request})
    if not serializer.is_valid():
        return _error_response(serializer, status.HTTP_400_BAD_REQUEST)

    profile = serializer.save()
    _, first_name, _ = get_name_parts(request.user, profile)
    return Response(
        {
            "status": "ok",
            "message": "Data diri berhasil diperbarui.",
            "user": {
                "username": request.user.username,
                "email": request.user.email,
                "first_name": first_name,
                "full_name": profile.full_name,
                "phone_number": profile.phone_number,
            },
        }
    )


@api_view(["POST", "PUT", "PATCH"])
@authentication_classes([CsrfExemptSessionAuthentication])
@permission_classes([IsPersonal])
def api_update_preferences(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    serializer = PreferencesSerializer(data=request.data, context={"profile": profile})
    if not serializer.is_valid():
        return _error_response(serializer, status.HTTP_400_BAD_REQUEST)

    new_prefs = serializer.save()
    return Response(
        {
            "status": "ok",
            "message": "Preferensi berhasil disimpan.",
            "preferences": new_prefs,
        }
    )


# ---------------------------------------------------------------------------
# User Addresses (DRF ViewSet + Legacy AJAX Endpoints)
# ---------------------------------------------------------------------------

class UserAddressViewSet(viewsets.ModelViewSet):
    """CRUD alamat lengkap DRF: /api/addresses/ dan /api/addresses/<id>/."""

    serializer_class = UserAddressSerializer
    authentication_classes = [CsrfExemptSessionAuthentication]
    permission_classes = [IsPersonal]
    lookup_value_regex = r"\d+"

    def get_queryset(self):
        profile, _ = UserProfile.objects.get_or_create(user=self.request.user)
        qs = ensure_user_addresses_synced(self.request.user, profile)
        if self.action == "list":
            qs = filter_user_addresses(
                qs,
                label=self.request.GET.get("label", ""),
                query=self.request.GET.get("q", ""),
            )
        return qs

    def perform_destroy(self, instance):
        delete_user_address_and_sync(self.request.user, instance)

    @action(detail=True, methods=["post"], url_path="set-primary")
    def set_primary(self, request, pk=None):
        addr = self.get_object()
        addr.is_primary = True
        addr.save()
        return Response(
            {
                "status": "ok",
                "message": "Alamat utama berhasil diubah.",
                "address": UserAddressSerializer(addr).data,
            }
        )


@api_view(["POST"])
@authentication_classes([CsrfExemptSessionAuthentication])
@permission_classes([IsPersonal])
def api_add_address(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    ensure_user_addresses_synced(request.user, profile)

    serializer = UserAddressSerializer(data=request.data, context={"request": request})
    if not serializer.is_valid():
        return _error_response(serializer, status.HTTP_400_BAD_REQUEST)

    new_addr = serializer.save()
    all_addresses = UserAddress.objects.filter(user=request.user)
    return Response(
        {
            "status": "ok",
            "message": "Alamat baru berhasil ditambahkan.",
            "address": UserAddressSerializer(new_addr).data,
            "addresses": UserAddressSerializer(all_addresses, many=True).data,
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(["POST", "PUT", "PATCH"])
@authentication_classes([CsrfExemptSessionAuthentication])
@permission_classes([IsPersonal])
def api_edit_address(request, address_id: int):
    addr = get_object_or_404(UserAddress, pk=address_id, user=request.user)
    serializer = UserAddressSerializer(
        addr,
        data=request.data,
        partial=(request.method == "PATCH"),
        context={"request": request},
    )
    if not serializer.is_valid():
        return _error_response(serializer, status.HTTP_400_BAD_REQUEST)

    updated_addr = serializer.save()
    all_addresses = UserAddress.objects.filter(user=request.user)
    return Response(
        {
            "status": "ok",
            "message": "Alamat berhasil diperbarui.",
            "address": UserAddressSerializer(updated_addr).data,
            "addresses": UserAddressSerializer(all_addresses, many=True).data,
        }
    )


@api_view(["POST", "DELETE"])
@authentication_classes([CsrfExemptSessionAuthentication])
@permission_classes([IsPersonal])
def api_delete_address(request, address_id: int):
    addr = get_object_or_404(UserAddress, pk=address_id, user=request.user)
    delete_user_address_and_sync(request.user, addr)
    all_addresses = UserAddress.objects.filter(user=request.user)
    return Response(
        {
            "status": "ok",
            "message": "Alamat berhasil dihapus.",
            "addresses": UserAddressSerializer(all_addresses, many=True).data,
        }
    )


@api_view(["POST"])
@authentication_classes([CsrfExemptSessionAuthentication])
@permission_classes([IsPersonal])
def api_set_primary_address(request, address_id: int):
    addr = get_object_or_404(UserAddress, pk=address_id, user=request.user)
    addr.is_primary = True
    addr.save()
    all_addresses = UserAddress.objects.filter(user=request.user)
    return Response(
        {
            "status": "ok",
            "message": "Alamat utama berhasil diubah.",
            "address": UserAddressSerializer(addr).data,
            "addresses": UserAddressSerializer(all_addresses, many=True).data,
        }
    )


@api_view(["GET"])
@authentication_classes([CsrfExemptSessionAuthentication])
@permission_classes([permissions.IsAuthenticated])
def api_rajaongkir_destinations(request):
    """Pencarian kota, kecamatan, kelurahan, atau kode pos via RajaOngkir (fallback lokal)."""
    q = (request.GET.get("q") or request.GET.get("search") or "").strip()
    raw_limit = request.GET.get("limit", "15")
    limit = min(max(int(raw_limit), 1), 25) if raw_limit.isdigit() else 15
    data = search_destinations(q, limit=limit)
    return Response(
        {
            "status": "ok",
            "query": q,
            "source": data["source"],
            "results": data["results"],
        }
    )


# ---------------------------------------------------------------------------
# Lembaga Mitra Profile & Public Directory
# ---------------------------------------------------------------------------

@api_view(["GET", "POST", "PUT", "PATCH"])
@authentication_classes([CsrfExemptSessionAuthentication])
@permission_classes([IsLembaga])
def api_lembaga_profile(request):
    institution = InstitutionProfile.objects.filter(user=request.user).first()

    if request.method == "GET":
        kebutuhan_aktif = Kebutuhan.objects.aktif().filter(lembaga=request.user).count()
        tawaran_menunggu = Penawaran.objects.filter(
            lembaga=request.user, status=Penawaran.Status.MENUNGGU
        ).count()
        donasi_selesai = Penawaran.objects.filter(
            lembaga=request.user, status=Penawaran.Status.SELESAI
        ).count()
        return Response(
            {
                "status": "ok",
                "exists": institution is not None,
                "is_complete": is_institution_profile_complete(request.user),
                "user": {
                    "id": request.user.pk,
                    "username": request.user.username,
                    "email": request.user.email,
                    "role": "LEMBAGA",
                    "has_usable_password": request.user.has_usable_password(),
                    "google_connected": request.user.profile.google_connected,
                    "google_email": request.user.profile.google_email,
                },
                "institution": (
                    InstitutionProfileSerializer(institution, context={"request": request}).data
                    if institution
                    else None
                ),
                "stats": {
                    "kebutuhan_aktif": kebutuhan_aktif,
                    "tawaran_menunggu": tawaran_menunggu,
                    "donasi_selesai": donasi_selesai,
                },
            }
        )

    is_creating = institution is None
    serializer = InstitutionProfileSerializer(
        institution,
        data=request.data,
        partial=(request.method == "PATCH" and institution is not None),
        context={"request": request},
    )
    if not serializer.is_valid():
        return _error_response(serializer, status.HTTP_400_BAD_REQUEST)

    saved_inst = serializer.save()
    return Response(
        {
            "status": "ok",
            "message": "Profil lembaga berhasil disimpan.",
            "is_complete": is_institution_profile_complete(request.user),
            "institution": InstitutionProfileSerializer(saved_inst, context={"request": request}).data,
        },
        status=status.HTTP_201_CREATED if is_creating else status.HTTP_200_OK,
    )


class InstitutionPublicViewSet(viewsets.ReadOnlyModelViewSet):
    """Direktori publik lembaga mitra: /api/lembaga/ dan /api/lembaga/<id>/."""

    serializer_class = InstitutionPublicSerializer
    authentication_classes = [CsrfExemptSessionAuthentication]
    permission_classes = [permissions.AllowAny]
    lookup_value_regex = r"\d+"

    def get_queryset(self):
        qs = (
            InstitutionProfile.objects.select_related("user")
            .exclude(name="")
            .exclude(address="")
            .order_by("-is_verified", "name")
        )
        inst_type = (self.request.GET.get("type") or "").strip().upper()
        if inst_type:
            qs = qs.filter(institution_type=inst_type)

        verified = (self.request.GET.get("verified") or "").strip().lower()
        if verified in ("true", "1"):
            qs = qs.filter(is_verified=True)
        elif verified in ("false", "0"):
            qs = qs.filter(is_verified=False)

        city = (self.request.GET.get("city") or "").strip()
        if city:
            qs = qs.filter(city__icontains=city)

        q = (self.request.GET.get("q") or "").strip()
        if q:
            qs = qs.filter(
                Q(name__icontains=q)
                | Q(city__icontains=q)
                | Q(description__icontains=q)
                | Q(address__icontains=q)
            )
        return qs


# ---------------------------------------------------------------------------
# Security (Password, Google Unlink, Account Deletion)
# ---------------------------------------------------------------------------

@api_view(["POST"])
@authentication_classes([CsrfExemptSessionAuthentication])
@permission_classes([permissions.IsAuthenticated])
def api_change_password(request):
    serializer = ChangePasswordSerializer(data=request.data, context={"request": request})
    if not serializer.is_valid():
        return _error_response(serializer, status.HTTP_400_BAD_REQUEST)

    serializer.save()
    return Response(
        {
            "status": "ok",
            "message": "Kata sandi berhasil diperbarui.",
            "has_usable_password": True,
            "password_status": "Baru saja diperbarui",
        }
    )


@api_view(["POST"])
@authentication_classes([CsrfExemptSessionAuthentication])
@permission_classes([permissions.IsAuthenticated])
def api_disconnect_google(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    if not request.user.has_usable_password():
        return Response(
            {
                "status": "error",
                "message": "Atur kata sandi terlebih dahulu sebelum memutuskan akun Google agar Anda tetap bisa masuk.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    profile.google_connected = False
    profile.google_email = ""
    profile.save(update_fields=["google_connected", "google_email"])
    return Response(
        {
            "status": "ok",
            "message": "Akun Google berhasil diputuskan.",
            "google_connected": False,
            "connect_url": f"{reverse('main:google_login')}?action=connect",
        }
    )


@api_view(["POST"])
@authentication_classes([CsrfExemptSessionAuthentication])
@permission_classes([permissions.IsAuthenticated])
def api_delete_account(request):
    serializer = DeleteAccountSerializer(data=request.data, context={"request": request})
    if not serializer.is_valid():
        return _error_response(serializer, status.HTTP_400_BAD_REQUEST)

    user = request.user
    logout(request._request)
    user.delete()
    return Response(
        {
            "status": "ok",
            "message": "Akun Anda telah dihapus.",
            "redirect_url": reverse("main:show_main"),
        }
    )
