"""API tests for diplomes."""

from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

from apps.diplomes.api import AlumniConsentViewSet, CessionsDiplomesViewSet
from apps.diplomes.models import CessionDiplome, ConsentementAlumni, Diplome
from apps.diplomes.serializers import CessionDiplomeDetailSerializer
from apps.etablissement.models import AnneeUniversitaire
from apps.etudiants.models import Etudiant
from apps.formations.models import Formation
from apps.integration.tests.tenant_test_case import TenantAPITestCase
from apps.utilisateurs.models import Utilisateur
from django.test import SimpleTestCase
from django.urls import resolve
from rest_framework.test import APIRequestFactory


class DiplomesAPITestCase(SimpleTestCase):
    def test_diplome_routes_are_registered(self):
        list_match = resolve("/api/v1/diplomes/")
        detail_match = resolve("/api/v1/diplomes/1/")
        pdf_match = resolve("/api/v1/diplomes/1/pdf_officiel/")
        history_match = resolve("/api/v1/diplomes/1/historique/")
        revocation_match = resolve("/api/v1/diplomes/1/revoquer/")
        catalogue_match = resolve("/api/v1/diplomes/catalogue/")
        alumni_match = resolve("/api/v1/diplomes/alumni/consentement/")

        assert list_match.url_name == "diplome-list"
        assert detail_match.url_name == "diplome-detail"
        assert pdf_match.url_name == "diplome-pdf-officiel"
        assert history_match.url_name == "diplome-historique"
        assert revocation_match.url_name == "diplome-revoquer"
        assert catalogue_match.url_name == "diplome-catalogue-list"
        assert alumni_match.url_name == "diplome-alumni-consentement"


class CessionSignatureAPITestCase(SimpleTestCase):
    def test_crud_cannot_issue_or_revoke_signature(self):
        cession = CessionDiplome(
            pk=1,
            etudiant=Etudiant(
                pk=1,
                matricule="E1",
                user=Utilisateur(pk=1, first_name="Alice", last_name="Exemple"),
            ),
            diplome=Diplome(pk=1, formation_id=1, nom="Licence"),
            annee_universitaire=AnneeUniversitaire(pk=1, universite_id=1, libelle="2025-2026"),
            date_obtention=date(2026, 6, 30),
            mention="",
            moyenne_finale=None,
            numero_serie="DIP-12345678",
            pdf_path="",
            date_signature=None,
            qr_verification="",
            created_at=datetime(2026, 6, 30, tzinfo=timezone.utc),
        )
        factory = APIRequestFactory()
        update = CessionsDiplomesViewSet.as_view(
            {"patch": "partial_update"}, permission_classes=[], throttle_classes=[]
        )
        verifier = CessionsDiplomesViewSet.as_view(
            {"get": "verifier"}, permission_classes=[], throttle_classes=[]
        )

        with (
            patch.object(CessionsDiplomesViewSet, "get_object", return_value=cession),
            patch.object(CessionDiplomeDetailSerializer, "get_validators", return_value=[]),
            patch.object(CessionDiplome, "save"),
        ):
            response = update(
                factory.patch(
                    "/api/v1/diplomes/1/",
                    {
                        "date_signature": "2026-07-01T10:00:00Z",
                        "qr_verification": "https://fake.example/verified",
                    },
                    format="json",
                ),
                pk=1,
            )
            assert response.status_code == 200
            assert verifier(factory.get("/api/v1/diplomes/1/verifier/"), pk=1).data["valide"] is False
            assert cession.date_signature is None
            assert cession.qr_verification == ""

            signed_at = datetime(2026, 7, 2, tzinfo=timezone.utc)
            cession.date_signature = signed_at
            cession.qr_verification = "https://verif.univ.fr/DIP-12345678"
            response = update(
                factory.patch(
                    "/api/v1/diplomes/1/",
                    {"date_signature": None, "date_revocation": "2026-07-03T10:00:00Z", "qr_verification": ""},
                    format="json",
                ),
                pk=1,
            )
            assert response.status_code == 200
            assert verifier(factory.get("/api/v1/diplomes/1/verifier/"), pk=1).data["valide"] is True
            assert cession.date_signature == signed_at
            assert cession.date_revocation is None
            assert cession.qr_verification == "https://verif.univ.fr/DIP-12345678"


class AlumniConsentAPITestCase(TenantAPITestCase):
    url = "/api/v1/diplomes/alumni/consentement/"

    def setUp(self):
        self.year = AnneeUniversitaire.objects.create(
            universite=self.tenant,
            libelle="2025-2026",
            date_debut=date(2025, 9, 1),
            date_fin=date(2026, 8, 31),
        )
        self.formation = Formation.objects.create(nom="Licence", code="ALUMNI", type="licence")
        self.diplome = Diplome.objects.create(
            formation=self.formation, nom="Licence", niveau_grade="Licence"
        )
        self.graduate = self._student("graduate", statut="inscrit")
        self.other = self._student("other", statut="diplome")
        self.credential = CessionDiplome.objects.create(
            etudiant=self.graduate,
            diplome=self.diplome,
            annee_universitaire=self.year,
            date_obtention=date(2026, 6, 30),
            numero_serie="DIP-ALUMNI",
            pdf_path="",
            date_signature=datetime(2026, 7, 1, tzinfo=timezone.utc),
            signe_par=self.graduate.user,
            qr_verification="https://verif.univ.fr/DIP-ALUMNI",
        )
        self.client.force_authenticate(self.graduate.user)

    def _student(self, name, *, statut):
        user = Utilisateur.objects.create_user(name, role="etudiant", etablissement=self.tenant)
        return Etudiant.objects.create(
            user=user,
            universite=self.tenant,
            matricule=f"M-{name}",
            date_naissance=date(2000, 1, 1),
            lieu_naissance="Paris",
            sexe="F",
            adresse="Adresse confidentielle",
            code_postal="75000",
            ville="Paris",
            telephone="0600000000",
            email_personnel=f"{name}@private.example",
            statut=statut,
        )

    def test_signed_credential_not_self_declared_student_status_controls_eligibility(self):
        status_response = self.client.get(self.url)
        assert status_response.status_code == 200
        assert status_response.data["eligible"] is True
        assert status_response.data["consentement_actif"] is False
        assert status_response["Cache-Control"] == "private, no-store"
        assert "email_personnel" not in status_response.data
        assert "telephone" not in status_response.data

        self.client.force_authenticate(self.other.user)
        other_status = self.client.get(self.url)
        assert other_status.data["eligible"] is False
        assert other_status.data["revision"] == 0
        assert self.client.post(
            self.url, {"consentement": True, "revision": 0}, format="json"
        ).status_code == 403
        assert not ConsentementAlumni.objects.filter(etudiant=self.other).exists()

    def test_unsigned_and_revoked_credentials_never_authorize_opt_in(self):
        self.credential.date_signature = None
        self.credential.save(update_fields=["date_signature"])
        assert self.client.post(
            self.url, {"consentement": True, "revision": 0}, format="json"
        ).status_code == 403
        self.credential.date_signature = datetime(2026, 7, 1, tzinfo=timezone.utc)
        self.credential.date_revocation = datetime(2026, 7, 2, tzinfo=timezone.utc)
        self.credential.save(update_fields=["date_signature", "date_revocation"])
        assert self.client.get(self.url).data["eligible"] is False
        assert self.client.post(
            self.url, {"consentement": True, "revision": 0}, format="json"
        ).status_code == 403
        assert self.client.get(
            f"/api/v1/diplomes/{self.credential.pk}/verifier/"
        ).data["valide"] is False
        self.credential.refresh_from_db()
        assert self.credential.date_signature is not None

    def test_only_registry_can_revoke_and_signature_remains_intact(self):
        url = f"/api/v1/diplomes/{self.credential.pk}/revoquer/"
        assert self.client.post(url).status_code == 403
        assert self.client.post(
            self.url, {"consentement": True, "revision": 0}, format="json"
        ).status_code == 200
        registrar = Utilisateur.objects.create_user(
            "registrar", role="scolarite", etablissement=self.tenant
        )
        self.client.force_authenticate(registrar)
        assert self.client.post(url).status_code == 200
        self.credential.refresh_from_db()
        revoked_at = self.credential.date_revocation
        assert revoked_at is not None
        assert self.credential.date_signature == datetime(2026, 7, 1, tzinfo=timezone.utc)
        assert self.client.post(url).status_code == 200
        self.credential.refresh_from_db()
        assert self.credential.date_revocation == revoked_at
        self.client.force_authenticate(self.graduate.user)
        assert self.client.get(self.url).data["eligible"] is False
        assert self.client.get(self.url).data["consentement_actif"] is False
        assert self.client.delete(
            self.url, {"revision": 1}, format="json"
        ).data["revision"] == 2

    def test_withdrawal_and_replays_require_fresh_revision_to_reactivate(self):
        assert self.client.post(
            self.url, {"consentement": False, "revision": 0}, format="json"
        ).status_code == 400
        assert self.client.post(
            self.url, {"consentement": True, "revision": 0, "email": "public@example.com"},
            format="json",
        ).status_code == 400
        assert self.client.post(
            self.url, {"consentement": True, "revision": 0}, format="json"
        ).status_code == 200
        consent = ConsentementAlumni.objects.get(etudiant=self.graduate)
        first_date = consent.consenti_le
        replay = self.client.post(
            self.url, {"consentement": True, "revision": 0}, format="json"
        )
        assert replay.data["revision"] == 1
        consent.refresh_from_db()
        assert consent.consenti_le == first_date
        withdrawal = self.client.delete(self.url, {"revision": 1}, format="json")
        assert withdrawal.status_code == 200
        assert withdrawal.data["consentement_actif"] is False
        consent.refresh_from_db()
        withdrawn_at = consent.retire_le
        assert self.client.delete(
            self.url, {"revision": 1}, format="json"
        ).data["revision"] == 2
        consent.refresh_from_db()
        assert consent.retire_le == withdrawn_at
        assert self.client.post(
            self.url, {"consentement": True, "revision": 0}, format="json"
        ).status_code == 409
        assert self.client.post(
            self.url, {"consentement": True, "revision": 2}, format="json"
        ).data["revision"] == 3
        assert self.client.delete(self.url, {"revision": 1}, format="json").status_code == 409
        assert self.client.get(self.url).data["consentement_actif"] is True

    def test_tenant_and_identity_are_required_even_for_existing_consent(self):
        self.client.post(self.url, {"consentement": True, "revision": 0}, format="json")
        assert not AlumniConsentViewSet()._eligible(
            self.graduate, SimpleNamespace(pk=self.tenant.pk + 100)
        )
        self.client.force_authenticate(self.other.user)
        assert self.client.get(self.url).data["consentement_actif"] is False
        self.other.user.etablissement_id = self.tenant.pk + 100
        assert self.client.get(self.url).status_code == 403
        self.client.force_authenticate(None)
        assert self.client.get(self.url).status_code in (401, 403)
