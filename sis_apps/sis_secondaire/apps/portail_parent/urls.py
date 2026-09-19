"""URLs for portail_parent portal."""

from django.urls import path

from . import views

app_name = "portail_parent"

urlpatterns = [
    path("", views.index, name="index"),
]
