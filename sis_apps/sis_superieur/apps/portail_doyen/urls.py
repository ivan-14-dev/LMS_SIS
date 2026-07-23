"""URLs for portail_doyen portal."""
from django.urls import path
from . import views

app_name = "portail_doyen"

urlpatterns = [
    path("", views.index, name="index"),
]
