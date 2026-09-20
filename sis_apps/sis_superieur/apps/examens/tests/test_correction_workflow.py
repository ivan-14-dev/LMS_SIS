from types import SimpleNamespace
from unittest.mock import Mock

from apps.examens.serializers import (
    AffectationCorrectionSerializer,
    CorrectionCopieSerializer,
)
from django.test import SimpleTestCase
from rest_framework.exceptions import ValidationError


class CorrectionWorkflowValidationTests(SimpleTestCase):
    def setUp(self):
        self.correcteur = SimpleNamespace(
            pk=7, role="enseignant", is_staff=False, is_active=True
        )
        self.copie = SimpleNamespace(
            statut="deposee",
            convocation=SimpleNamespace(etudiant=SimpleNamespace(user_id=9)),
            epreuve=SimpleNamespace(nombre_corrections=2, bareme=20),
            affectations=Mock(count=Mock(return_value=0)),
        )

    def test_candidate_cannot_correct_own_copy(self):
        self.copie.convocation.etudiant.user_id = self.correcteur.pk
        serializer = AffectationCorrectionSerializer()

        with self.assertRaisesMessage(ValidationError, "propre copie"):
            serializer.validate(
                {"copie": self.copie, "correcteur": self.correcteur, "ordre": 1}
            )

    def test_finalized_copy_rejects_new_assignment(self):
        self.copie.statut = "finalisee"
        serializer = AffectationCorrectionSerializer()

        with self.assertRaisesMessage(ValidationError, "n'accepte plus"):
            serializer.validate(
                {"copie": self.copie, "correcteur": self.correcteur, "ordre": 1}
            )

    def test_submitted_assignment_rejects_second_correction(self):
        affectation = SimpleNamespace(
            correcteur=self.correcteur,
            statut="soumise",
            copie=SimpleNamespace(statut="correction"),
        )
        serializer = CorrectionCopieSerializer(
            context={"request": SimpleNamespace(user=self.correcteur)}
        )

        with self.assertRaisesMessage(ValidationError, "n'accepte plus"):
            serializer.validate({"affectation": affectation, "note": 10})
