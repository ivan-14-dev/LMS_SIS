"""Views for portail_etudiant portal (placeholder)."""
from django.shortcuts import render


def index(request):
    return render(request, "portail_etudiant/index.html", {})
