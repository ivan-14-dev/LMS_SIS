"""URLs for portail_enseignant portal."""

from django.urls import path

from . import views

app_name = "portail_enseignant"

urlpatterns = [
    path("", views.index, name="index"),
]
