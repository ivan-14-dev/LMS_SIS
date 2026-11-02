"""API tests for presences."""

from types import SimpleNamespace

from apps.presences.serializers import PresenceSaisieSerializer, validate_attendance
from django.test import SimpleTestCase
from django.urls import resolve
from rest_framework.exceptions import ValidationError


class PresencesAPITestCase(SimpleTestCase):
    """Vérifie que les ViewSets `presences` sont bien routés (et non des stubs morts)."""

    def test_routes_are_registered(self):
        assert resolve("/api/v1/presences/appels/").url_name == "appel-list"
        assert resolve("/api/v1/presences/").url_name == "presence-list"
        assert resolve("/api/v1/presences/justificatifs/").url_name == "justificatif-list"

    def test_attendance_rejects_closed_calls_other_classes_and_other_teachers(self):
        request = SimpleNamespace(
            tenant=SimpleNamespace(pk=1),
            user=SimpleNamespace(pk=10, is_staff=False, role="enseignant"),
        )
        appel = SimpleNamespace(
            statut="ouvert",
            enseignant=SimpleNamespace(user_id=10),
            creneau=SimpleNamespace(
                classe_id=1,
                classe=SimpleNamespace(etablissement_id=1, annee_scolaire=SimpleNamespace(cloturee=False)),
            ),
        )
        validate_attendance(request, appel, SimpleNamespace(classe_actuelle_id=1))
        with self.assertRaises(ValidationError):
            validate_attendance(request, appel, SimpleNamespace(classe_actuelle_id=2))
        appel.enseignant.user_id = 99
        with self.assertRaises(ValidationError):
            validate_attendance(request, appel)
        appel.enseignant.user_id = 10
        appel.statut = "ferme"
        with self.assertRaises(ValidationError):
            validate_attendance(request, appel)

    def test_negative_delays_cannot_enter_bulk_attendance(self):
        serializer = PresenceSaisieSerializer(data={"eleve_id": 1, "retard_minutes": -1})
        assert not serializer.is_valid()
        assert "retard_minutes" in serializer.errors
