from django.contrib import admin
from main.models import UserProfile, InstitutionProfile

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "full_name", "phone_number",)
    list_filter = ("role",)
    search_fields = ("user__username", "user__email", "full_name",)

@admin.register(InstitutionProfile)
class InstitutionProfileAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "institution_type", "is_verified", "updated_at",)
    list_filter = ("institution_type", "is_verified",)
    search_fields = ("name","user__username",)
    readonly_fields = ("created_at", "updated_at",)