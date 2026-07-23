"""Views for portail_doyen portal (placeholder)."""
from django.shortcuts import render


def index(request):
    return render(request, "portail_doyen/index.html", {})
