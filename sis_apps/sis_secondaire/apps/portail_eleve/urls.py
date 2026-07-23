"""URLs for portail_eleve portal."""
from django.urls import path
from . import views

app_name = "portail_eleve"

urlpatterns = [
    path("", views.index, name="index"),
]
