"""Views for portail_enseignant portal (placeholder)."""
from django.shortcuts import render


def index(request):
    return render(request, "portail_enseignant/index.html", {})
