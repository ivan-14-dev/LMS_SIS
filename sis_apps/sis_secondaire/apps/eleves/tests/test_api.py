"""API tests for eleves."""

from unittest.mock import patch

from apps.classes.models import Classe
from apps.eleves.models import Eleve, Inscription
from apps.etablissement.models import AnneeScolaire, Niveau
from apps.integration.tests.tenant_test_case import TenantAPITestCase
from apps.utilisateurs.models import Utilisateur
from django.core.cache.backends.locmem import LocMemCache
from django.test import SimpleTestCase
from django.urls import resolve
from django.utils import timezone
from rest_framework.throttling import SimpleRateThrottle


class ElevesAPITestCase(SimpleTestCase):
    def test_individual_subject_routes_are_registered(self):
        list_match = resolve("/api/v1/eleves/1/matieres-individuelles/")
        remove_match = resolve("/api/v1/eleves/1/retirer-matiere-individuelle/")

        assert list_match.url_name == "matieres-individuelles"
        assert remove_match.url_name == "retirer-matiere-individuelle"


class EnrollmentCapacityTestCase(TenantAPITestCase):
    def setUp(self):
        throttle_cache = patch.object(SimpleRateThrottle, "cache", LocMemCache("capacity-tests", {}))
        throttle_cache.start()
        self.addCleanup(throttle_cache.stop)
        self.today = timezone.localdate()
        self.admin = Utilisateur.objects.create_superuser(
            "capacity-admin", role="super_admin", etablissement=self.tenant
        )
        self.client.force_authenticate(self.admin)
        self.year = AnneeScolaire.objects.create(
            etablissement=self.tenant,
            libelle=f"{self.today.year}",
            date_debut=self.today.replace(month=1, day=1),
            date_fin=self.today.replace(month=12, day=31),
        )
        level = Niveau.objects.create(etablissement=self.tenant, code="6e", libelle="Sixième")
        self.source = Classe.objects.create(
            etablissement=self.tenant, annee_scolaire=self.year, niveau=level, nom="6A"
        )
        self.target = Classe.objects.create(
            etablissement=self.tenant, annee_scolaire=self.year, niveau=level, nom="6B", effectif_max=1
        )

    def enroll(self, username, classe, *, statut="validee", current=True):
        user = Utilisateur.objects.create_user(username, role="eleve", etablissement=self.tenant)
        pupil = Eleve.objects.create(
            etablissement=self.tenant,
            user=user,
            matricule=f"CAP-{username}",
            date_naissance="2008-01-01",
            lieu_naissance="Paris",
            sexe="F",
            date_inscription=self.today,
            classe_actuelle=classe if current else None,
        )
        enrollment = Inscription.objects.create(
            eleve=pupil, classe=classe, annee_scolaire=self.year, date_inscription=self.today, statut=statut
        )
        return pupil, enrollment

    def test_creating_pupil_cannot_assign_class_without_validated_enrollment(self):
        self.enroll("occupant", self.target)
        payload = {
            "username": "capacity-new-pupil",
            "email": "new-pupil@example.test",
            "first_name": "New",
            "last_name": "Pupil",
            "password": "Secure-Password-2030!",
            "date_naissance": "2008-01-01",
            "lieu_naissance": "Paris",
            "sexe": "F",
            "classe_actuelle": self.target.pk,
        }

        response = self.client.post("/api/v1/eleves/", payload, format="json", secure=True)
        assert response.status_code == 400, response.data
        assert "classe_actuelle" in response.data
        assert not Utilisateur.objects.filter(username=payload["username"]).exists()

        payload.pop("classe_actuelle")
        response = self.client.post("/api/v1/eleves/", payload, format="json", secure=True)
        assert response.status_code == 201, response.data
        pupil = Eleve.objects.get(user__username=payload["username"])
        assert pupil.classe_actuelle_id is None
        assert not pupil.inscriptions.exists()

    def test_validation_refuses_full_class_and_preserves_pending_enrollment(self):
        self.enroll("occupant", self.target)
        candidate, pending = self.enroll("candidate", self.target, statut="en_cours", current=False)

        url = f"/api/v1/eleves/inscriptions/{pending.pk}/valider/"
        response = self.client.post(url, secure=True)
        assert response.status_code == 400, response.data
        pending.refresh_from_db()
        candidate.refresh_from_db()
        assert pending.statut == "en_cours"
        assert candidate.classe_actuelle is None

        self.target.effectif_max = 2
        self.target.save(update_fields=["effectif_max"])
        response = self.client.post(url, secure=True)
        assert response.status_code == 200, response.data
        pending.refresh_from_db()
        candidate.refresh_from_db()
        assert pending.statut == "validee"
        assert candidate.classe_actuelle_id == self.target.pk

    def test_transfer_refuses_full_class_even_when_occupant_is_not_current(self):
        occupant, _ = self.enroll("occupant", self.target)
        pupil, enrollment = self.enroll("moving", self.source)
        url = f"/api/v1/eleves/{pupil.pk}/changer-classe/"
        payload = {"classe_id": self.target.pk, "motif": "Répartition"}

        for current_class in (self.target, None):
            occupant.classe_actuelle = current_class
            occupant.save(update_fields=["classe_actuelle"])
            response = self.client.post(url, payload, format="json", secure=True)
            assert response.status_code == 400, response.data
            pupil.refresh_from_db()
            enrollment.refresh_from_db()
            assert pupil.classe_actuelle_id == self.source.pk
            assert enrollment.classe_id == self.source.pk

    def test_transfer_fills_last_available_place(self):
        self.enroll("occupant", self.target)
        pupil, enrollment = self.enroll("moving", self.source)
        self.target.effectif_max = 2
        self.target.save(update_fields=["effectif_max"])

        response = self.client.post(
            f"/api/v1/eleves/{pupil.pk}/changer-classe/",
            {"classe_id": self.target.pk, "motif": "Répartition"},
            format="json",
            secure=True,
        )
        assert response.status_code == 200, response.data
        pupil.refresh_from_db()
        enrollment.refresh_from_db()
        assert pupil.classe_actuelle_id == self.target.pk
        assert enrollment.classe_id == self.target.pk
