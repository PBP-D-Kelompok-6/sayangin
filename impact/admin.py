from django.contrib import admin

from impact.models import Challenge

# Register your models here.

@admin.register(Challenge)
class ChallengeAdmin(admin.ModelAdmin):
    list_display = ("title", "owner", "kind", "target", "start_date", "end_date")
    list_filter = ("kind",)
