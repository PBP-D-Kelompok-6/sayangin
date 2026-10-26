from django.contrib import admin
from main.models import InstitutionProfile

@admin.register(InstitutionProfile)
class InstitutionProfileAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "user",
        "institution_type",
        "is_verified",
        "updated_at",
    )
    list_filter = (
        "institution_type",
        "is_verified",
    )
    search_fields = (
        "name",
        "user__username",
    )
    readonly_fields = (
        "created_at",
        "updated_at",
    )

# Register your models here.
