from django.urls import path

from impact import views

app_name = "impact"

urlpatterns = [
    path("", views.show_impact_dashboard, name="show_impact_dashboard"),
    path("json/", views.show_impact_json, name="show_impact_json"),
    path("tantangan/", views.show_impact_challenges, name="show_impact_challenges"),
    path("tantangan/tambah/", views.create_impact_challenge, name="create_impact_challenge"),
    path("tantangan/<int:pk>/ubah/", views.edit_impact_challenge, name="edit_impact_challenge"),
    path("tantangan/<int:pk>/hapus/", views.delete_impact_challenge, name="delete_impact_challenge"),
]