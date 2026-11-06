"""API integration-style tests for tenant-driven note exports."""

from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from apps.classes.models import Classe
from apps.eleves.models import Eleve
from apps.etablissement.models import AnneeScolaire, Niveau, Periode
from apps.integration.tests.tenant_test_case import TenantAPITestCase
from apps.notes.api import (
    BulletinsViewSet,
    EvaluationsViewSet,
    NotesViewSet,
    _ensure_secondary_continuous_assessment,
)
from apps.notes.models import Bulletin
from apps.utilisateurs.models import Utilisateur
from django.test import SimpleTestCase
from django.urls import resolve
from django.utils import timezone
from rest_framework import serializers
from rest_framework.test import APIRequestFactory


class FakeQuerySet:
    def __init__(self, rows):
        self.rows = rows
        self.filters = []
        self.selected_fields = ()

    def filter(self, **kwargs):
        self.filters.append(kwargs)
        return self

    def values_list(self, *fields):
        self.selected_fields = fields
        return self

    def distinct(self):
        return self.rows


class NotesAPITestCase(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = SimpleNamespace(
            is_authenticated=True,
            is_superuser=False,
            has_perm=lambda permission: permission == "notes.view_note",
        )

    def test_note_export_route_is_registered(self):
        match = resolve("/api/v1/notes/notes/exporter/")

        assert match.url_name == "note-exporter"

    def test_evaluation_import_routes_are_registered(self):
        template_match = resolve("/api/v1/notes/evaluations/1/modele_import_notes/")
        import_match = resolve("/api/v1/notes/evaluations/1/importer_notes/")
        history_match = resolve("/api/v1/notes/evaluations/1/historique/")

        assert template_match.url_name == "evaluation-modele-import-notes"
        assert import_match.url_name == "evaluation-importer-notes"
        assert history_match.url_name == "evaluation-historique"

    def test_bulletin_export_route_is_registered(self):
        match = resolve("/api/v1/notes/bulletins/exporter/")

        assert match.url_name == "bulletin-exporter"

    def test_note_export_uses_tenant_report_configuration(self):
        payload = {
            "report": "notes-secondary",
            "filters": {"classe": 9},
        }
        request = self.factory.post(
            "/api/v1/notes/notes/exporter/",
            payload,
            format="json",
        )
        request.user = self.user
        request.data = payload
        request.tenant = SimpleNamespace(
            configuration_academique={
                "reports": [
                    {
                        "code": "notes-secondary",
                        "label": "Notes secondaire",
                        "dataset": "notes",
                        "fields": ["matricule", "note"],
                        "allowed_filters": ["classe"],
                    }
                ]
            }
        )
        queryset = FakeQuerySet([("MAT-001", "14.5")])
        view = NotesViewSet()
        view.request = request
        view.action = "exporter"
        view.get_queryset = lambda: queryset
        view.filter_queryset = lambda qs: qs

        response = view.exporter(request)

        assert response.status_code == 200
        assert queryset.filters == [{"evaluation__classe_id": 9}]
        assert queryset.selected_fields == ("eleve__matricule", "valeur")
        assert "MAT-001,14.5" in response.content.decode()

    @patch("apps.notes.api.record_workflow_event")
    @patch("apps.notes.api._import_secondary_notes", return_value=(2, 1))
    @patch(
        "apps.notes.api.load_excel_rows",
        return_value=[
            {"matricule": "MAT-001", "note": "14", "appreciation": "", "statut": "presente", "__row_number__": 2}
        ],
    )
    def test_secondary_note_import_uses_excel_template_rules(
        self, _load_rows, _import_notes, _record_workflow_event  # noqa: PT019
    ):
        request = self.factory.post("/api/v1/notes/evaluations/1/importer_notes/", {}, format="multipart")
        request.user = self.user
        request.tenant = SimpleNamespace(
            configuration_academique={"import_templates": [{"code": "continuous_assessment_grades"}]}
        )
        request.FILES["file"] = SimpleNamespace(name="notes.xlsx")
        evaluation = SimpleNamespace(
            pk=1,
            id=1,
            titre="Devoir surveillé n°1",
            type="ds",
            classe_id=9,
            matiere_id=3,
            classe=SimpleNamespace(annee_scolaire=SimpleNamespace(cloturee=False)),
            periode=SimpleNamespace(cloturee=False),
        )

        view = EvaluationsViewSet()
        view.request = request
        view.action = "importer_notes"
        view.get_object = lambda: evaluation

        response = view.importer_notes(request, pk=1)

        assert response.status_code == 200
        assert response.data["evaluation_id"] == 1
        assert response.data["notes_creees"] == 2
        assert response.data["notes_modifiees"] == 1

    @patch("apps.notes.api.request_has_business_access", return_value=True)
    @patch("apps.notes.api.filter_queryset_by_scopes", side_effect=lambda qs, *_args, **_kwargs: qs)
    def test_bulletin_export_uses_tenant_report_configuration(self, _scoped_queryset, _business_access):  # noqa: PT019
        payload = {
            "report": "bulletins-secondary",
            "filters": {"publie": True},
        }
        request = self.factory.post(
            "/api/v1/notes/bulletins/exporter/",
            payload,
            format="json",
        )
        request.user = self.user
        request.data = payload
        request.tenant = SimpleNamespace(
            configuration_academique={
                "reports": [
                    {
                        "code": "bulletins-secondary",
                        "label": "Bulletins secondaire",
                        "dataset": "bulletins",
                        "fields": ["matricule", "decision"],
                        "allowed_filters": ["publie"],
                    }
                ]
            },
            id=1,
        )
        queryset = FakeQuerySet([("MAT-002", "passage")])
        view = BulletinsViewSet()
        view.request = request
        view.action = "exporter"
        view.get_queryset = lambda: queryset
        view.filter_queryset = lambda qs: qs

        response = view.exporter(request)

        assert response.status_code == 200
        assert queryset.filters == [{"publie": True}]
        assert queryset.selected_fields == ("eleve__matricule", "decision")
        assert "MAT-002,passage" in response.content.decode()

    def test_secondary_continuous_assessment_blocks_submission_before_window(self):
        evaluation = SimpleNamespace(
            type="ds",
            debut_soumission=timezone.now() + timedelta(hours=2),
            fin_soumission=None,
            classe=SimpleNamespace(annee_scolaire=SimpleNamespace(cloturee=False)),
            periode=SimpleNamespace(cloturee=False),
        )

        with pytest.raises(serializers.ValidationError) as context:
            _ensure_secondary_continuous_assessment(evaluation)

        assert "soumission" in context.value.detail


class PublishedBulletinHTTPTestCase(TenantAPITestCase):
    def test_published_outcome_cannot_be_edited_via_either_bulletin_route(self):
        direction = Utilisateur.objects.create_user(
            "notes-direction", role="direction", etablissement=self.tenant
        )
        student = Utilisateur.objects.create_user(
            "notes-student", role="eleve", etablissement=self.tenant
        )
        year = AnneeScolaire.objects.create(
            etablissement=self.tenant,
            libelle="2026-2027",
            date_debut=date(2026, 9, 1),
            date_fin=date(2027, 6, 30),
        )
        period = Periode.objects.create(
            annee_scolaire=year,
            type="trimestre",
            numero=1,
            date_debut=date(2026, 9, 1),
            date_fin=date(2027, 6, 30),
        )
        level = Niveau.objects.create(etablissement=self.tenant, code="6e", libelle="Sixième")
        classroom = Classe.objects.create(
            etablissement=self.tenant, annee_scolaire=year, niveau=level, nom="6e A"
        )
        pupil = Eleve.objects.create(
            etablissement=self.tenant,
            user=student,
            matricule="NOTES-001",
            date_naissance=date(2012, 1, 1),
            lieu_naissance="Paris",
            sexe="F",
            date_inscription=date(2026, 9, 1),
            classe_actuelle=classroom,
        )
        bulletin = Bulletin.objects.create(
            eleve=pupil, classe=classroom, periode=period, decision="en attente"
        )
        self.client.force_authenticate(direction)
        notes_url = f"/api/v1/notes/bulletins/{bulletin.pk}/"

        draft_response = self.client.patch(notes_url, {"decision": "passage"}, format="json", secure=True)
        assert draft_response.status_code == 200, draft_response.data
        bulletin.publie = True
        bulletin.date_publication = timezone.now()
        bulletin.save(update_fields=["publie", "date_publication"])

        for url in (notes_url, f"/api/v1/bulletins/{bulletin.pk}/"):
            response = self.client.patch(url, {"decision": "redoublement"}, format="json", secure=True)
            assert response.status_code == 400, response.data
            bulletin.refresh_from_db()
            assert bulletin.decision == "passage"
            assert bulletin.publie is True
