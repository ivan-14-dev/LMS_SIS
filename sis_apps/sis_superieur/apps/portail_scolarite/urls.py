"""URLs for portail_scolarite portal."""
from django.urls import path
from . import views

app_name = "portail_scolarite"

urlpatterns = [
    path("", views.index, name="index"),
]
