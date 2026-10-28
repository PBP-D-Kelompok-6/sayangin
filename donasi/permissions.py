from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

LEMBAGA_GROUP = "Lembaga"

def is_lembaga(user):
    return user.is_authenticated and user.groups.filter(name=LEMBAGA_GROUP).exists()


def lembaga_required(view_func):
    """Hanya akun Lembaga Mitra yang sudah login. Lainnya: login dulu / 403."""
    @login_required
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not is_lembaga(request.user):
            raise PermissionDenied
        return view_func(request, *args, **kwargs)

    return _wrapped

def donatur_required(view_func):
    """Hanya User (donatur) yang sudah login. Akun Lembaga tidak boleh mendonasikan barang."""

    @login_required
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if is_lembaga(request.user):
            raise PermissionDenied
        return view_func(request, *args, **kwargs)

    return _wrapped