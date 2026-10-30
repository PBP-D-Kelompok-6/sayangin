# Semua URL Modul E; disambungkan di sayangin/urls.py dengan awalan "dampak/"
from django.urls import path

from impact import views

app_name = "impact" # nama namespace, dipakai di template: {% url 'impact:...' %}

urlpatterns = [
    path("", views.show_impact_dashboard, name="show_impact_dashboard"), #dashboard
    path("json/", views.show_impact_json, name="show_impact_json"), #Json
    path("peringkat/", views.show_impact_leaderboard, name="show_impact_leaderboard"), #papan peringkat publik (tanpa login)
    path("tantangan/", views.show_impact_challenges, name="show_impact_challenges"), #daftar
    path("tantangan/json/", views.show_impact_challenges_json, name="show_impact_challenges_json"), #daftar dalam bentuk Json
    path("tantangan/tambah/", views.create_impact_challenge, name="create_impact_challenge"), #tambah
    path("tantangan/<int:pk>/ubah/", views.edit_impact_challenge, name="edit_impact_challenge"), #ubah
    path("tantangan/<int:pk>/hapus/", views.delete_impact_challenge, name="delete_impact_challenge"), #hapus
]