from django.contrib import admin
from main.models import UserProfile, UserAddress, InstitutionProfile

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "full_name", "phone_number",)
    list_filter = ("role",)
    search_fields = ("user__username", "user__email", "full_name",)

@admin.register(UserAddress)
class UserAddressAdmin(admin.ModelAdmin):
    list_display = ("user", "label", "city", "rajaongkir_city_id", "postal_code", "is_primary", "updated_at",)
    list_filter = ("label", "is_primary", "city",)
    search_fields = ("user__username", "address", "city", "postal_code",)
    readonly_fields = ("created_at", "updated_at",)

@admin.register(InstitutionProfile)
class InstitutionProfileAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "institution_type", "is_verified", "updated_at",)
    list_filter = ("institution_type", "is_verified",)
    search_fields = ("name", "user__username",)
    readonly_fields = ("created_at", "updated_at",)