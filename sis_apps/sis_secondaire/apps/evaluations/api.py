"""Compatibility API for secondary evaluations."""

from apps.notes.api import EvaluationsViewSet as _NotesEvaluationsViewSet


class EvaluationsViewSet(_NotesEvaluationsViewSet):
    """Backward-compatible viewset aligned with active notes evaluations."""

