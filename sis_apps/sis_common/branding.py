"""Presentation-only tenant identity, available without administrative configuration."""

from rest_framework.exceptions import PermissionDenied


def branding_snapshot(request):
    tenant = getattr(request, "tenant", None)
    if tenant is None or not request.user.is_active or request.user.etablissement_id != tenant.pk:
        raise PermissionDenied("L'identité visuelle est réservée à votre établissement.")
    return {
        "id": tenant.pk,
        "name": tenant.nom,
        "primary_color": tenant.couleur_primaire,
        "logo": request.build_absolute_uri(tenant.logo.url) if tenant.logo else None,
    }
