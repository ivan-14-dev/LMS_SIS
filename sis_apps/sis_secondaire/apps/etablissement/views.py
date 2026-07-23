"""Views for etablissement admin (placeholder)."""
from django.shortcuts import render


def index(request):
    return render(request, "etablissement/index.html", {})
