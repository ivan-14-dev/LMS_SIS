"""Views for portail_eleve portal (placeholder)."""

from django.shortcuts import render


def index(request):
    return render(request, "portail_eleve/index.html", {})
