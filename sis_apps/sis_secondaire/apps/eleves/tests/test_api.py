"""API tests for eleves."""

import uuid
from unittest.mock import patch

from apps.classes.models import Classe, Matiere, ProgrammeMatiere
from apps.eleves.models import AffectationMatiereIndividuelle, Eleve, Inscription
from apps.etablissement.models import AnneeScolaire, Etablissement, Niveau
from apps.integration.tests.tenant_test_case import TenantAPITestCase
from apps.utilisateurs.models import Utilisateur
from django.core.cache.backends.locmem import LocMemCache
from django.test import SimpleTestCase
from django.urls import resolve
from django.utils import timezone
from django_tenants.utils import schema_context
from rest_framework.throttling import SimpleRateThrottle


class ElevesAPITestCase(SimpleTestCase):
    def test_individual_subject_routes_are_registered(self):
        list_match = resolve("/api/v1/eleves/1/matieres-individuelles/")
        remove_match = resolve("/api/v1/eleves/1/retirer-matiere-individuelle/")

        assert list_match.url_name == "matieres-individuelles"
        assert remove_match.url_name == "retirer-matiere-individuelle"


class ForeignSchoolAccountAccessTestCase(TenantAPITestCase):
    def test_foreign_superuser_cannot_read_or_write_school_pupils(self):
        other = Etablissement(
            schema_name=f"other_pupils_{uuid.uuid4().hex[:12]}",
            nom="Autre établissement", type="college", adresse="1 rue des Tests",
            code_postal="75000", ville="Paris", telephone="0100000000", email="other@example.test",
        )
        other.auto_create_schema = False
        with schema_context("public"):
            other.save()
        local = Utilisateur.objects.create_superuser(
            "local-school-admin", etablissement=self.tenant, role="super_admin",
        )
        foreign = Utilisateur.objects.create_superuser(
            "foreign-school-admin", etablissement=other, role="super_admin",
        )
        pupil_user = Utilisateur.objects.create_user(
            "local-pupil", etablissement=self.tenant, role="eleve",
        )
        pupil = Eleve.objects.create(
            etablissement=self.tenant, user=pupil_user, matricule="FOREIGN-ACCESS-TEST",
            date_naissance="2008-01-01", lieu_naissance="Paris", sexe="F",
            date_inscription="2026-09-01",
        )

        self.client.force_authenticate(local)
        for url in ("/api/v1/eleves/", f"/api/v1/eleves/{pupil.pk}/"):
            assert self.client.get(url, secure=True).status_code == 200

        self.client.force_authenticate(foreign)
        for url in ("/api/v1/eleves/", f"/api/v1/eleves/{pupil.pk}/"):
            assert self.client.get(url, secure=True).status_code == 403
        assert self.client.post("/api/v1/eleves/", {}, format="json", secure=True).status_code == 403


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

    def test_individual_subject_source_cannot_belong_to_another_school_year(self):
        pupil, _ = self.enroll("optional-subject", self.source)
        previous_year = AnneeScolaire.objects.create(
            etablissement=self.tenant,
            libelle=str(self.today.year - 1),
            date_debut=self.today.replace(year=self.today.year - 1, month=1, day=1),
            date_fin=self.today.replace(year=self.today.year - 1, month=12, day=31),
        )
        subject = Matiere.objects.create(etablissement=self.tenant, code="OPT", nom="Option")
        programme = ProgrammeMatiere.objects.create(classe=self.target, matiere=subject)
        url = f"/api/v1/eleves/{pupil.pk}/matieres-individuelles/"
        payload = {
            "annee_scolaire": previous_year.pk,
            "matiere": subject.pk,
            "programme_source": programme.pk,
        }

        response = self.client.post(url, payload, format="json", secure=True)
        assert response.status_code == 400, response.data
        assert "annee_scolaire" in response.data
        assert not AffectationMatiereIndividuelle.objects.filter(eleve=pupil).exists()

        payload["annee_scolaire"] = self.year.pk
        response = self.client.post(url, payload, format="json", secure=True)
        assert response.status_code == 201, response.data
        assert response.data["annee_scolaire"] == self.year.pk
