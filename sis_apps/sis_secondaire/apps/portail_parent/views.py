"""Views for portail_parent portal (placeholder)."""
from django.shortcuts import render


def index(request):
    return render(request, "portail_parent/index.html", {})
