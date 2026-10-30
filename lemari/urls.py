from django.urls import path
from . import views

app_name = "lemari"

urlpatterns = [
    path("", views.index, name="index"),
    path("kosong/", views.kosong, name="kosong"),
    path("mulai/", views.awal, name="awal"),
    path("tambah-barang/", views.tambah_barang, name="tambah_barang"),
    path("detail-barang/<int:item_id>/", views.detail_barang, name="detail_barang"),
    path("foto/<int:item_id>/", views.wardrobe_photo, name="wardrobe_photo"),
    path("hapus/<int:item_id>/", views.hapus_item, name="hapus_item"),
    path("pengingat/<int:item_id>/toggle/", views.toggle_reminder, name="toggle_reminder"),
    path("jual/", views.jual, name="jual"),
    path("jual/sukses/<int:listing_id>/", views.jual_sukses, name="jual_sukses"),
]
