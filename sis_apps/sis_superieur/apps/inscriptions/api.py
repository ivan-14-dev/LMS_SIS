"""Compatibility API for superior enrollment workflows."""

from apps.etudiants.api import InscriptionsAdminViewSet as _InscriptionsAdminViewSet


class InscriptionsViewSet(_InscriptionsAdminViewSet):
    """Backward-compatible viewset aligned with active administrative enrollments."""
