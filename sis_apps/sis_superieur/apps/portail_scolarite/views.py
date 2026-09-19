"""Views for portail_scolarite portal (placeholder)."""

from django.shortcuts import render


def index(request):
    return render(request, "portail_scolarite/index.html", {})
