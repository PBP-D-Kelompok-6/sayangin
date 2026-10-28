from django.urls import path
from . import views

app_name = "lemari"

urlpatterns = [
    path("", views.index, name="index"),
    path("kosong/", views.kosong, name="kosong"),
    path("mulai/", views.awal, name="awal"),
    path("foto/<int:item_id>/", views.wardrobe_photo, name="wardrobe_photo"),
    path("hapus/<int:item_id>/", views.hapus_item, name="hapus_item"),
    path("jual/", views.jual, name="jual"),
    path("jual/sukses/<int:listing_id>/", views.jual_sukses, name="jual_sukses"),
]
