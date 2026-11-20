from functools import wraps
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from rest_framework import permissions

LEMBAGA_GROUP = "Lembaga"


def is_lembaga(user):
    if not user or not user.is_authenticated:
        return False
    if hasattr(user, "profile") and user.profile.role == "LEMBAGA":
        return True
    if hasattr(user, "institution_profile"):
        return True
    return user.groups.filter(name=LEMBAGA_GROUP).exists()


def is_donatur(user):
    if not user or not user.is_authenticated:
        return False
    return not is_lembaga(user)


# Decorator untuk Django views konvensional (tetap dipertahankan)
def lembaga_required(view_func):
    @login_required(login_url="main:show_login")
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not is_lembaga(request.user):
            raise PermissionDenied("Hanya akun lembaga yang dapat mengakses halaman ini.")
        return view_func(request, *args, **kwargs)
    return _wrapped


def donatur_required(view_func):
    @login_required(login_url="main:show_login")
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if is_lembaga(request.user):
            raise PermissionDenied("Akun lembaga mitra tidak dapat mendonasikan barang.")
        return view_func(request, *args, **kwargs)
    return _wrapped


# ---------------------------------------------------------------------------
# DRF Permission Classes (Tutorial 07)
# ---------------------------------------------------------------------------
class IsLembagaUser(permissions.BasePermission):
    message = "Hanya akun Lembaga Mitra yang diizinkan melakukan tindakan ini."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and is_lembaga(request.user))


class IsDonaturUser(permissions.BasePermission):
    message = "Hanya akun Donatur (Personal) yang diizinkan melakukan tindakan ini."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and is_donatur(request.user))


class IsLembagaOrReadOnly(permissions.BasePermission):
    message = "Hanya akun Lembaga Mitra yang dapat menambah atau mengubah kebutuhan donasi."

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return bool(request.user and request.user.is_authenticated and is_lembaga(request.user))