from django.urls import path
from . import api_views

app_name = "donasi_api"

urlpatterns = [
    # Kebutuhan
    path("kebutuhan/", api_views.api_kebutuhan_list, name="kebutuhan_list"),
    path("kebutuhan/saya/", api_views.api_kebutuhan_saya, name="kebutuhan_saya"),
    path("kebutuhan/<int:pk>/", api_views.api_kebutuhan_detail, name="kebutuhan_detail"),

    # Penawaran
    path("penawaran/", api_views.api_penawaran_list, name="penawaran_list"),
    path("penawaran/<int:pk>/", api_views.api_penawaran_detail, name="penawaran_detail"),
    path("penawaran/<int:pk>/batal/", api_views.api_penawaran_batal, name="penawaran_batal"),

    # Aksi Lembaga
    path("penawaran/<int:pk>/terima/", api_views.api_penawaran_terima, name="penawaran_terima"),
    path("penawaran/<int:pk>/tolak/", api_views.api_penawaran_tolak, name="penawaran_tolak"),
    path("penawaran/<int:pk>/selesai/", api_views.api_penawaran_selesai, name="penawaran_selesai"),

    # Dashboard Lembaga
    path("lembaga/dashboard/", api_views.api_lembaga_dashboard, name="lembaga_dashboard"),
]