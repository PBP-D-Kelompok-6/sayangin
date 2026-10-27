from django.urls import path
from . import views

app_name = "lemari"

urlpatterns = [
    path("", views.index, name="index"),
]
