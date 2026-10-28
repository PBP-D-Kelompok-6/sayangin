from django.urls import path
from . import views

app_name = "donasi"

urlpatterns = [
    # Dashboard & Riwayat
    path("lembaga/", views.dashboard_lembaga, name="dashboard_lembaga"),
    path("lembaga/riwayat/", views.riwayat_lembaga, name="riwayat_lembaga"),
    
    # Kelola Kebutuhan
    path("lembaga/kebutuhan/", views.kebutuhan_list, name="kebutuhan_list"),
    path("lembaga/kebutuhan/baru/", views.kebutuhan_buat, name="kebutuhan_buat"),
    path("lembaga/kebutuhan/pratinjau/", views.kebutuhan_pratinjau, name="kebutuhan_pratinjau"),
    path("lembaga/kebutuhan/<int:pk>/ubah/", views.kebutuhan_ubah, name="kebutuhan_ubah"),
    path("lembaga/kebutuhan/<int:pk>/hapus/", views.kebutuhan_hapus, name="kebutuhan_hapus"),
    
    # Tawaran
    path("lembaga/tawaran/<int:pk>/terima/", views.penawaran_terima, name="penawaran_terima"),
    path("lembaga/tawaran/<int:pk>/tolak/", views.penawaran_tolak, name="penawaran_tolak"),
    path("lembaga/tawaran/<int:pk>/selesai/", views.penawaran_selesai, name="penawaran_selesai"),
]