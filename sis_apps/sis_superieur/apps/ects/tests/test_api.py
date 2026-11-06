"""API tests for ects."""

import datetime
from types import SimpleNamespace

from apps.ects.models import BilanECTS
from apps.ects.serializers import BilanECTSSerializer
from apps.etablissement.models import AnneeUniversitaire
from apps.etudiants.models import Etudiant, InscriptionAdministrative
from apps.formations.models import Formation
from apps.integration.tests.tenant_test_case import TenantAPITestCase
from apps.utilisateurs.models import Utilisateur
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
            **self.bilan, etudiant_id=self.etudiant.pk, annee_universitaire_id=self.annee.pk,
            credits_inscrits=6,
        )
        assert BilanECTSSerializer(instance).validate(attrs) == attrs


class BilanECTSCreditWriteTestCase(TenantAPITestCase):
    def setUp(self):
        super().setUp()
        agent = Utilisateur.objects.create_user(
            username="ects-agent", role="scolarite", etablissement=self.tenant
        )
        student_user = Utilisateur.objects.create_user(
            username="ects-student", role="etudiant", etablissement=self.tenant
        )
        self.etudiant = Etudiant.objects.create(
            user=student_user, universite=self.tenant, matricule="ECTS-01",
            date_naissance=datetime.date(2000, 1, 1),
        )
        self.annee = AnneeUniversitaire.objects.create(
            universite=self.tenant, libelle="2026-2027",
            date_debut=datetime.date(2026, 9, 1), date_fin=datetime.date(2027, 8, 31),
        )
        formation = Formation.objects.create(nom="Informatique", code="INFO", type="licence")
        self.inscription = InscriptionAdministrative.objects.create(
            etudiant=self.etudiant, annee_universitaire=self.annee,
            formation=formation, date_inscription=datetime.date(2026, 9, 1),
        )
        self.client.force_authenticate(agent)

    def test_create_rejects_more_validated_credits_than_enrolled(self):
        url = "/api/v1/ects/bilans-ects/"
        payload = {
            "etudiant": self.etudiant.pk,
            "annee_universitaire": self.annee.pk,
            "inscription_admin": self.inscription.pk,
            "credits_inscrits": "6.00",
            "credits_valides": "7.00",
        }
        response = self.client.post(url, payload, format="json")

        assert response.status_code == 400, response.data
        assert "credits_valides" in response.data
        assert not BilanECTS.objects.exists()

        response = self.client.post(url, {**payload, "credits_valides": "6.00"}, format="json")
        assert response.status_code == 201, response.data
        assert BilanECTS.objects.get().credits_valides == 6

    def test_create_rejects_negative_credits(self):
        url = "/api/v1/ects/bilans-ects/"
        payload = {
            "etudiant": self.etudiant.pk,
            "annee_universitaire": self.annee.pk,
            "inscription_admin": self.inscription.pk,
            "credits_inscrits": "6.00",
        }
        for field in (
            "credits_inscrits",
            "credits_valides",
            "credits_compenses",
            "credits_echec",
        ):
            with self.subTest(field=field):
                response = self.client.post(
                    url, {**payload, field: "-1.00"}, format="json"
                )
                assert response.status_code == 400, response.data
                assert field in response.data
                assert not BilanECTS.objects.exists()

    def test_patch_cannot_raise_validated_credits_or_lower_enrolled_credits_past_them(self):
        bilan = BilanECTS.objects.create(
            etudiant=self.etudiant, annee_universitaire=self.annee,
            inscription_admin=self.inscription, credits_inscrits=6, credits_valides=6,
        )
        url = f"/api/v1/ects/bilans-ects/{bilan.pk}/"
        for update in ({"credits_valides": "7.00"}, {"credits_inscrits": "5.00"}):
            with self.subTest(update=update):
                response = self.client.patch(url, update, format="json")
                assert response.status_code == 400, response.data
                assert "credits_valides" in response.data
                bilan.refresh_from_db()
                assert bilan.credits_inscrits == 6
                assert bilan.credits_valides == 6

    def test_patch_rejects_negative_credits_without_changing_bilan(self):
        bilan = BilanECTS.objects.create(
            etudiant=self.etudiant, annee_universitaire=self.annee,
            inscription_admin=self.inscription, credits_inscrits=6,
        )
        url = f"/api/v1/ects/bilans-ects/{bilan.pk}/"
        for field in (
            "credits_inscrits",
            "credits_valides",
            "credits_compenses",
            "credits_echec",
        ):
            with self.subTest(field=field):
                response = self.client.patch(url, {field: "-1.00"}, format="json")
                assert response.status_code == 400, response.data
                assert field in response.data
                bilan.refresh_from_db()
                assert getattr(bilan, field) == (6 if field == "credits_inscrits" else 0)
