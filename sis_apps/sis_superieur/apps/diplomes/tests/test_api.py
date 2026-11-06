"""API tests for diplomes."""

from datetime import date, datetime, timezone
from unittest.mock import patch

from apps.diplomes.api import CessionsDiplomesViewSet
from apps.diplomes.models import CessionDiplome, Diplome
from apps.diplomes.serializers import CessionDiplomeDetailSerializer
from apps.etablissement.models import AnneeUniversitaire
from apps.etudiants.models import Etudiant
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
        catalogue_match = resolve("/api/v1/diplomes/catalogue/")

        assert list_match.url_name == "diplome-list"
        assert detail_match.url_name == "diplome-detail"
        assert pdf_match.url_name == "diplome-pdf-officiel"
        assert history_match.url_name == "diplome-historique"
        assert catalogue_match.url_name == "diplome-catalogue-list"


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
                    {"date_signature": None, "qr_verification": ""},
                    format="json",
                ),
                pk=1,
            )
            assert response.status_code == 200
            assert verifier(factory.get("/api/v1/diplomes/1/verifier/"), pk=1).data["valide"] is True
            assert cession.date_signature == signed_at
            assert cession.qr_verification == "https://verif.univ.fr/DIP-12345678"
