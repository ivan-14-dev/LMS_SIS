"""API tests for ects."""

from types import SimpleNamespace

from apps.ects.serializers import BilanECTSSerializer
from django.test import SimpleTestCase
from django.urls import resolve
from rest_framework.exceptions import ValidationError


class EctsAPITestCase(SimpleTestCase):
    """Vérifie que le ViewSet `ects` est bien routé (et non un stub mort)."""

    def test_routes_are_registered(self):
        assert resolve("/api/v1/ects/bilans-ects/").url_name == "bilan-ects-list"


class BilanECTSEnrollmentTestCase(SimpleTestCase):
    def setUp(self):
        self.etudiant = SimpleNamespace(pk=11)
        self.annee = SimpleNamespace(pk=22)
        self.inscription = SimpleNamespace(
            pk=33, etudiant_id=self.etudiant.pk, annee_universitaire_id=self.annee.pk
        )
        self.bilan = {
            "etudiant": self.etudiant,
            "annee_universitaire": self.annee,
            "inscription_admin": self.inscription,
        }

    def test_create_rejects_enrollment_for_another_student_or_year(self):
        for field, mismatch in (
            ("etudiant", SimpleNamespace(etudiant_id=99, annee_universitaire_id=22)),
            ("annee_universitaire", SimpleNamespace(etudiant_id=11, annee_universitaire_id=99)),
        ):
            with self.subTest(field=field), self.assertRaises(ValidationError) as error:
                BilanECTSSerializer().validate({**self.bilan, "inscription_admin": mismatch})
            assert field in error.exception.detail

    def test_partial_update_rejects_enrollment_or_student_mismatch(self):
        instance = SimpleNamespace(
            **self.bilan, etudiant_id=self.etudiant.pk, annee_universitaire_id=self.annee.pk
        )
        for field, attrs in (
            ("etudiant", {"inscription_admin": SimpleNamespace(etudiant_id=99, annee_universitaire_id=22)}),
            ("etudiant", {"etudiant": SimpleNamespace(pk=99)}),
            ("annee_universitaire", {"annee_universitaire": SimpleNamespace(pk=99)}),
        ):
            with self.subTest(field=field), self.assertRaises(ValidationError) as error:
                BilanECTSSerializer(instance).validate(attrs)
            assert field in error.exception.detail

    def test_matching_enrollment_accepts_create_and_unrelated_partial_update(self):
        assert BilanECTSSerializer().validate(self.bilan) == self.bilan
        attrs = {"credits_valides": 6}
        instance = SimpleNamespace(
            **self.bilan, etudiant_id=self.etudiant.pk, annee_universitaire_id=self.annee.pk
        )
        assert BilanECTSSerializer(instance).validate(attrs) == attrs
