"""URLs for portail_etudiant portal."""
from django.urls import path
from . import views

app_name = "portail_etudiant"

urlpatterns = [
    path("", views.index, name="index"),
]
