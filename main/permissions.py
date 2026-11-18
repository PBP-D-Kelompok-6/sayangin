from rest_framework import permissions

from main.models import UserProfile


class IsPersonal(permissions.BasePermission):
    """Hanya akun personal yang sudah login."""

    message = "Hanya akun personal yang dapat mengakses endpoint ini."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        return profile.role == "PERSONAL"


class IsLembaga(permissions.BasePermission):
    """Hanya akun lembaga mitra yang sudah login."""

    message = "Hanya akun lembaga mitra yang dapat mengakses endpoint ini."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        return profile.role == "LEMBAGA"
