from functools import wraps
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

LEMBAGA_GROUP = "Lembaga"

def is_lembaga(user):
    if not user.is_authenticated:
        return False
    # Cek role lembaga dari UserProfile atau relasi institution_profile milik modul main
    if hasattr(user, "profile") and user.profile.role == "LEMBAGA":
        return True
    if hasattr(user, "institution_profile"):
        return True
    return user.groups.filter(name=LEMBAGA_GROUP).exists()


def lembaga_required(view_func):
    """Hanya akun Lembaga Mitra yang sudah login. Lainnya: redirect login / 403."""
    @login_required(login_url='main:show_login')
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not is_lembaga(request.user):
            raise PermissionDenied("Hanya akun lembaga yang dapat mengakses halaman ini.")
        return view_func(request, *args, **kwargs)

    return _wrapped


def donatur_required(view_func):
    """Hanya Donatur (Personal) yang sudah login. Akun Lembaga tidak boleh mendonasikan barang."""
    @login_required(login_url='main:show_login')
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if is_lembaga(request.user):
            raise PermissionDenied("Akun lembaga mitra tidak dapat mendonasikan barang.")
        return view_func(request, *args, **kwargs)

    return _wrapped