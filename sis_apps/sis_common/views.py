"""Shared HTTP views for SIS services."""

from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.views.decorators.http import require_GET


@require_GET
def csrf_token(request):
    """Issue the CSRF token expected by authenticated Open edX clients."""
    return JsonResponse({"csrfToken": get_token(request)})
