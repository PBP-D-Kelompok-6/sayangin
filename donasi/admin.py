from django.contrib import admin

from .models import Kebutuhan, Penawaran


@admin.register(Kebutuhan)
class KebutuhanAdmin(admin.ModelAdmin):
    list_display = ("nama_barang", "lembaga", "kategori", "terpenuhi", "jumlah", "tenggat", "status")
    list_filter = ("status", "kategori")
    search_fields = ("nama_barang", "lembaga__username", "lembaga__institution_profile__name")


@admin.register(Penawaran)
class PenawaranAdmin(admin.ModelAdmin):
    list_display = ("nama_barang", "donatur", "lembaga", "status", "tanggal_rencana", "dibuat")
    list_filter = ("status", "metode")
    search_fields = ("nama_barang", "donatur__username", "lembaga__username")