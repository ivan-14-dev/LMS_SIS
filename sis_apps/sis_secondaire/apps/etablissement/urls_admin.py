"""URLs for etablissement admin (SIS Secondaire)."""
from django.urls import path
from . import views

app_name = "etablissement"

urlpatterns = [
    path("", views.index, name="index"),
]
