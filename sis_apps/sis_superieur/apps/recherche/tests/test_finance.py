"""Real tenant ORM/API coverage; run only on an explicitly owned test database."""

import csv
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Barrier
from unittest.mock import patch
from uuid import uuid4

import pytest
from apps.core.models import ModuleConfiguration, WorkflowEvent
from apps.enseignants.models import EnseignantChercheur
from apps.integration.tests.tenant_test_case import TenantAPITestCase
from apps.recherche.access import FINANCE, MANAGE, ResearchConflict
from apps.recherche.finance import financial_report, project_has_open_commitments, validate_budget_floor
from apps.recherche.finance_models import ResearchAccountingLine, ResearchFinanceOperation
from apps.recherche.models import Laboratoire, ProjetRecherche
from apps.structure.models import Faculte
from apps.utilisateurs.models import Utilisateur
from django.contrib.auth.models import Permission
from django.core.exceptions import SuspiciousFileOperation
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, connection, connections, transaction
from django.test import TransactionTestCase
from django.utils import timezone
from django_tenants.utils import schema_context
from rest_framework.test import APIClient, APIRequestFactory, force_authenticate

from sis_common.exam_files import PrivateFinancialStorage

URL = "/api/v1/recherche/projets-recherche/"
PROOF = b"%PDF-1.4\nresearch evidence\n%%EOF\n"


class FinanceFixture(TenantAPITestCase):
    def setUp(self):
        super().setUp()
        directory = TemporaryDirectory(prefix="research-finance-tests-")
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.storage = PrivateFinancialStorage(location=self.root)
        self.storage_patch = patch.object(ResearchFinanceOperation._meta.get_field("justificatif"), "storage", self.storage)
        self.storage_patch.start()
        self.addCleanup(self.storage_patch.stop)
        self.actor = Utilisateur.objects.create_user(
            "research-finance", etablissement=self.tenant, role="etudiant"
        )
        self.finance_permission = Permission.objects.get(
            content_type__app_label="recherche", codename=FINANCE.split(".")[1]
        )
        self.actor.user_permissions.add(self.finance_permission)
        self.academic = Utilisateur.objects.create_user(
            "research-academic", etablissement=self.tenant, role="comptable", is_staff=True
        )
        self.academic.user_permissions.add(Permission.objects.get(
            content_type__app_label="recherche", codename=MANAGE.split(".")[1]
        ))
        self.teacher = EnseignantChercheur.objects.create(user=self.academic, specialite="Sciences")
        self.faculty = Faculte.objects.create(universite=self.tenant, nom="Sciences", code="RF")
        self.lab = Laboratoire.objects.create(nom="Recherche", acronyme="RF", faculte=self.faculty, directeur=self.teacher)
        self.project = self.make_project("Projet financé")
        self.other_project = self.make_project("Autre projet")
        ModuleConfiguration.objects.update_or_create(
            etablissement=self.tenant, defaults={"enabled": {"sis.research": True}}
        )
        self.client.force_authenticate(self.actor)

    def make_project(self, title):
        today = timezone.localdate()
        return ProjetRecherche.objects.create(
            laboratoire=self.lab, titre=title, description="Confidentiel",
            responsable=self.teacher, budget=Decimal("100.00"),
            date_debut=today - timedelta(days=30), date_fin=today + timedelta(days=90),
            statut="en_cours",
        )

    @staticmethod
    def proof(content=PROOF, name="preuve.pdf"):
        return SimpleUploadedFile(name, content, content_type="application/pdf")

    def payload(self, kind="financement", amount="100.00", project=None, **changes):
        project = project or self.project
        project.refresh_from_db()
        return {
            "version": project.version, "idempotency_key": str(uuid4()), "type": kind,
            "montant": amount, "reference": f"RF-{uuid4().hex}", "date_operation": timezone.localdate().isoformat(),
            "libelle": "Opération confirmée", "justificatif": self.proof(), **changes,
        }

    def command(self, kind="financement", amount="100.00", project=None, **changes):
        project = project or self.project
        return self.client.post(
            f"{URL}{project.pk}/operations-financieres/",
            self.payload(kind, amount, project, **changes), format="multipart",
        )

    def posted(self, kind="financement", amount="100.00", **changes):
        response = self.command(kind, amount, **changes)
        assert response.status_code == 201, response.data
        return response.data["operation"]

    def report(self, project=None):
        project = project or self.project
        return self.client.get(f"{URL}{project.pk}/rapport-financier/")

    def state(self):
        self.project.refresh_from_db()
        return (
            ResearchFinanceOperation.objects.count(),
            ResearchAccountingLine.objects.count(),
            WorkflowEvent.objects.filter(action="recherche_operation_financiere").count(),
            self.project.version,
            sorted(str(path.relative_to(self.root)) for path in self.root.rglob("*") if path.is_file()),
        )


class ResearchFinanceTests(FinanceFixture):
    def test_equal_or_decreasing_timestamps_do_not_reorder_persisted_movements(self):
        clock = timezone.now()
        operation_date = (timezone.localdate() - timedelta(days=1)).isoformat()
        with patch("django.utils.timezone.now", return_value=clock):
            receipt = self.posted(date_operation=operation_date)
            commitment = self.posted("engagement", "80.00", date_operation=operation_date)
        with patch("django.utils.timezone.now", return_value=clock - timedelta(minutes=1)):
            payment = self.posted("depense", "30.00", engagement=commitment["id"], date_operation=operation_date)
        with patch("django.utils.timezone.now", return_value=clock - timedelta(minutes=2)):
            reversal = self.posted(
                "contrepassation", "30.00", contrepassation_de=payment["id"], date_operation=operation_date,
            )
        operations = list(ResearchFinanceOperation.objects.filter(projet=self.project))
        assert [operation.sequence for operation in operations] == [1, 2, 3, 4]
        assert [str(operation.pk) for operation in operations] == [
            row["id"] for row in (receipt, commitment, payment, reversal)
        ]
        assert operations[0].created_at == operations[1].created_at
        assert operations[1].created_at > operations[2].created_at > operations[3].created_at
        report = self.report()
        assert report.status_code == 200, report.data
        assert report.data["engagements_ouverts"] == "80.00"
        assert report.data["solde_tresorerie"] == "100.00"
        assert (report.data["total_debit"], report.data["total_credit"]) == ("160.00", "160.00")
        listing = self.client.get(f"{URL}{self.project.pk}/operations-financieres/")
        assert [row["sequence"] for row in listing.data["results"]] == [4, 3, 2, 1]
        before = self.state()
        replay = self.command(
            idempotency_key=str(operations[0].idempotency_key), reference=receipt["reference"],
            date_operation=operation_date, version=1,
        )
        assert replay.status_code == 200, replay.data
        assert replay.data["replayed"]
        assert replay.data["operation"]["sequence"] == 1
        assert self.state() == before
        self.posted("depense", "10.00", engagement=commitment["id"])
        assert self.report().data["solde_tresorerie"] == "90.00"

    def test_noncontiguous_sequence_is_corruption_not_a_new_append_position(self):
        receipt = self.posted(amount="20.00")
        table = connection.ops.quote_name(ResearchFinanceOperation._meta.db_table)
        with connection.cursor() as cursor:
            cursor.execute(f"UPDATE {table} SET sequence = 2 WHERE id = %s", [receipt["id"]])
        before = self.state()
        assert self.report().status_code == 409
        assert self.command(amount="1.00").status_code == 409
        assert self.state() == before

    def test_linked_operations_cannot_predate_commitment_or_reversed_original(self):
        receipt = self.posted()
        commitment = self.posted("engagement", "80.00")
        yesterday = (timezone.localdate() - timedelta(days=1)).isoformat()
        before = self.state()
        for kind, amount in (("depense", "10.00"), ("annulation_engagement", "80.00")):
            response = self.command(kind, amount, engagement=commitment["id"], date_operation=yesterday)
            assert response.status_code == 400, response.data
            assert "date_operation" in response.data
        response = self.command("contrepassation", "100.00", contrepassation_de=receipt["id"], date_operation=yesterday)
        assert response.status_code == 400, response.data
        assert self.state() == before
        payment = self.posted("depense", "10.00", engagement=commitment["id"])
        before = self.state()
        response = self.command("contrepassation", "10.00", contrepassation_de=payment["id"], date_operation=yesterday)
        assert response.status_code == 400, response.data
        assert self.state() == before

    def test_receipt_payment_cancel_and_exact_reversals_have_persisted_journals(self):
        receipt = self.posted()
        commitment = self.posted("engagement", "80.00")
        payment = self.posted("depense", "30.00", engagement=commitment["id"])
        report = self.report()
        assert report.status_code == 200, report.data
        assert {key: report.data[key] for key in ("encaissements", "depenses", "engagements_ouverts", "solde_tresorerie")} == {"encaissements": "100.00", "depenses": "30.00", "engagements_ouverts": "50.00", "solde_tresorerie": "70.00"}
        assert ResearchAccountingLine.objects.count() == 4
        assert project_has_open_commitments(self.project)
        cancellation = self.posted("annulation_engagement", "50.00", engagement=commitment["id"], libelle="Solde libéré")
        assert cancellation["lignes"] == []
        assert not project_has_open_commitments(self.project)
        reversal = self.posted("contrepassation", "30.00", contrepassation_de=payment["id"], libelle="Erreur corrigée")
        assert {line["compte"]: (line["debit"], line["credit"]) for line in reversal["lignes"]} == {"banque": ("30.00", "0.00"), "charge": ("0.00", "30.00")}
        assert self.report().data["engagements_ouverts"] == "0.00"
        self.posted("contrepassation", "100.00", contrepassation_de=receipt["id"], libelle="Financement retourné")
        report = self.report().data
        assert report["solde_tresorerie"] == "0.00"
        assert report["disponible_budgetaire"] == "100.00"
        assert (report["total_debit"], report["total_credit"]) == ("260.00", "260.00")
        assert report["version"] == 7
        assert report["rapproche"]
        assert self.state()[:3] == (6, 8, 6)

    def test_reversal_restores_only_uncancelled_commitment_and_cannot_repeat(self):
        self.posted()
        commitment = self.posted("engagement", "80.00")
        payment = self.posted("depense", "30.00", engagement=commitment["id"])
        reversal = self.posted("contrepassation", "30.00", contrepassation_de=payment["id"])
        assert self.report().data["engagements_ouverts"] == "80.00"
        before = self.state()
        for target in (payment, reversal, commitment):
            response = self.command("contrepassation", target["montant"], contrepassation_de=target["id"])
            assert response.status_code == 409, response.data
        assert self.state() == before
        self.posted("depense", "80.00", engagement=commitment["id"])
        assert self.report().data["solde_tresorerie"] == "20.00"

    def test_cash_budget_and_exact_remaining_reservation_are_enforced_without_writes(self):
        commitment = self.posted("engagement", "80.00")
        before = self.state()
        attempts = [
            ("engagement", "30.00", {}),
            ("financement", "100.01", {}),
            ("depense", "1.00", {"engagement": commitment["id"]}),
            ("annulation_engagement", "79.99", {"engagement": commitment["id"]}),
            ("annulation_engagement", "80.01", {"engagement": commitment["id"]}),
        ]
        for kind, amount, changes in attempts:
            response = self.command(kind, amount, **changes)
            assert response.status_code == 409, response.data
        assert self.state() == before
        receipt = self.posted("financement", "60.00")
        self.posted("depense", "50.00", engagement=commitment["id"])
        assert self.command("depense", "11.00", engagement=commitment["id"]).status_code == 409
        assert self.command("depense", "31.00", engagement=commitment["id"]).status_code == 409
        assert self.command("contrepassation", "60.00", contrepassation_de=receipt["id"]).status_code == 409
        assert self.command("contrepassation", "59.00", contrepassation_de=receipt["id"]).status_code == 409
        self.posted("annulation_engagement", "30.00", engagement=commitment["id"])
        assert self.command("depense", "1.00", engagement=commitment["id"]).status_code == 409
        assert self.command("annulation_engagement", "30.00", engagement=commitment["id"]).status_code == 409

    def test_exact_decimal_cents_and_budget_floor(self):
        self.posted("financement", "0.30")
        commitment = self.posted("engagement", "0.30")
        self.posted("depense", "0.10", engagement=commitment["id"])
        self.posted("depense", "0.20", engagement=commitment["id"])
        report = financial_report(self.project)
        assert (report["depenses"], report["solde_tresorerie"]) == ("0.30", "0.00")
        with transaction.atomic():
            project = ProjetRecherche.objects.select_for_update().get(pk=self.project.pk)
            with pytest.raises(ResearchConflict):
                validate_budget_floor(project, Decimal("0.29"))
            validate_budget_floor(project, Decimal("0.30"))
        self.client.force_authenticate(self.academic)
        self.project.refresh_from_db()
        response = self.client.patch(
            f"{URL}{self.project.pk}/", {"version": self.project.version, "budget": "0.29"}, format="json"
        )
        assert response.status_code == 409, response.data
        self.project.refresh_from_db()
        assert self.project.budget == Decimal("100.00")

    def test_project_start_cannot_move_past_persisted_financial_dates(self):
        operation_date = self.project.date_debut + timedelta(days=5)
        self.posted(amount="20.00", date_operation=operation_date.isoformat())
        before = self.state()
        original_start = self.project.date_debut
        self.client.force_authenticate(self.academic)
        response = self.client.patch(
            f"{URL}{self.project.pk}/",
            {"version": self.project.version, "date_debut": (operation_date + timedelta(days=1)).isoformat()},
            format="json",
        )
        assert response.status_code == 400, response.data
        assert self.state() == before
        assert self.project.date_debut == original_start

    def test_completed_project_cannot_archive_after_reversal_reopens_commitment(self):
        self.posted()
        commitment = self.posted("engagement", "80.00")
        payment = self.posted("depense", "80.00", engagement=commitment["id"])
        self.project.refresh_from_db()
        self.client.force_authenticate(self.academic)
        response = self.client.post(
            f"{URL}{self.project.pk}/terminer/", {"version": self.project.version}, format="json"
        )
        assert response.status_code == 200, response.data
        self.client.force_authenticate(self.actor)
        self.posted("contrepassation", "80.00", contrepassation_de=payment["id"])
        assert self.report().data["engagements_ouverts"] == "80.00"
        before = self.state()
        self.client.force_authenticate(self.academic)
        response = self.client.post(
            f"{URL}{self.project.pk}/archiver/", {"version": self.project.version}, format="json"
        )
        assert response.status_code == 400, response.data
        assert self.state() == before
        assert not self.project.archive
        assert self.project.statut == "termine"

    def test_idempotent_replay_precedes_stale_version_and_has_no_side_effects(self):
        data = self.payload(amount="20.00")
        response = self.client.post(f"{URL}{self.project.pk}/operations-financieres/", data, format="multipart")
        assert response.status_code == 201, response.data
        self.posted("engagement", "10.00")
        before = self.state()
        replay = self.client.post(
            f"{URL}{self.project.pk}/operations-financieres/",
            {**data, "montant": "20.0", "justificatif": self.proof()}, format="multipart",
        )
        assert replay.status_code == 200, replay.data
        assert replay.data["replayed"]
        assert replay.data["operation"]["id"] == response.data["operation"]["id"]
        assert replay.data["version"] == 3
        assert self.state() == before
        for changed in (
            {"montant": "21.00"}, {"reference": "OTHER"}, {"libelle": "Autre motif"},
            {"justificatif": self.proof(PROOF + b"changed")},
        ):
            result = self.client.post(
                f"{URL}{self.project.pk}/operations-financieres/",
                {**data, "justificatif": self.proof(), **changed}, format="multipart",
            )
            assert result.status_code == 409, result.data
        assert self.state() == before

    def test_stale_version_and_schema_wide_reference_and_key_collisions(self):
        data = self.payload(amount="20.00")
        assert self.client.post(f"{URL}{self.project.pk}/operations-financieres/", data, format="multipart").status_code == 201
        before = self.state()
        assert self.command(amount="1.00", version=1).status_code == 409
        assert self.command(amount="1.00", reference=data["reference"]).status_code == 409
        assert self.command(amount="1.00", project=self.other_project, reference=data["reference"]).status_code == 409
        assert self.command(amount="20.00", project=self.other_project, idempotency_key=data["idempotency_key"]).status_code == 409
        assert self.state() == before

    def test_strict_input_and_required_proof_do_not_create_files(self):
        before = self.state()
        changes = [
            {"montant": "1.001"}, {"montant": "1e1"}, {"montant": "-1"}, {"montant": "NaN"},
            {"montant": "0.00"}, {"montant": "10000000000.00"}, {"version": "01"},
            {"version": "1.0"}, {"idempotency_key": "bad"}, {"reference": " "}, {"libelle": " "},
            {"date_operation": "2026-02-31"}, {"date_operation": "01/01/2026"},
            {"date_operation": (timezone.localdate() + timedelta(days=1)).isoformat()},
            {"date_operation": (self.project.date_debut - timedelta(days=1)).isoformat()},
            {"extra": "denied"}, {"engagement": str(uuid4())}, {"type": "remboursement"},
            {"reference": ["FIRST", "SECOND"]},
            {"justificatif": self.proof(b"not-a-pdf")}, {"justificatif": self.proof(name="proof.exe")},
        ]
        for change in changes:
            with self.subTest(change={key: str(value) for key, value in change.items()}):
                response = self.command(amount="1.00", **change)
                assert response.status_code == 400, response.data
        response = self.client.post(
            f"{URL}{self.project.pk}/operations-financieres/", ["not-an-object"], format="json",
        )
        assert response.status_code == 400, response.data
        assert "non_field_errors" in response.data
        data = self.payload()
        del data["justificatif"]
        assert self.client.post(f"{URL}{self.project.pk}/operations-financieres/", data, format="multipart").status_code == 400
        assert self.state() == before

    def test_project_state_rules_and_archived_replay_are_denied(self):
        for status in ("propose", "suspendu", "termine"):
            ProjetRecherche.objects.filter(pk=self.project.pk).update(statut=status)
            assert self.command(amount="10.00").status_code == 409
        ProjetRecherche.objects.filter(pk=self.project.pk).update(statut="accepte")
        receipt = self.posted(amount="10.00")
        assert self.command("engagement", "1.00").status_code == 409
        ProjetRecherche.objects.filter(pk=self.project.pk).update(statut="termine")
        self.posted("contrepassation", "10.00", contrepassation_de=receipt["id"])
        ProjetRecherche.objects.filter(pk=self.project.pk).update(archive=True)
        assert self.command("contrepassation", "10.00", contrepassation_de=receipt["id"]).status_code == 409

    def test_private_proof_download_is_scoped_integrity_checked_and_never_a_storage_url(self):
        receipt = self.posted()
        operation = ResearchFinanceOperation.objects.get(pk=receipt["id"])
        assert "justificatif" not in receipt
        assert operation.justificatif.name not in str(receipt)
        assert operation.justificatif.name.startswith(f"recherche-finance/{self.tenant.schema_name}/")
        with pytest.raises(SuspiciousFileOperation):
            _ = operation.justificatif.url
        response = self.client.get(receipt["url_justificatif"])
        assert response.status_code == 200
        assert "no-store" in response["Cache-Control"]
        assert b"".join(response.streaming_content) == PROOF
        assert self.client.get(f"{URL}{self.other_project.pk}/justificatifs/{operation.pk}/").status_code == 404
        Path(operation.justificatif.path).write_bytes(PROOF + b"tampered")
        assert self.client.get(receipt["url_justificatif"]).status_code == 409

    def test_foreign_tenant_proof_path_is_never_opened(self):
        receipt = self.posted()
        table = connection.ops.quote_name(ResearchFinanceOperation._meta.db_table)
        with connection.cursor() as cursor:
            cursor.execute(
                f"UPDATE {table} SET justificatif = %s WHERE id = %s",
                [f"recherche-finance/foreign_tenant/{uuid4().hex}.pdf", receipt["id"]],
            )
        with patch.object(self.storage, "open", side_effect=AssertionError("foreign proof opened")):
            assert self.client.get(receipt["url_justificatif"]).status_code == 409
        assert self.report().status_code == 409

    def test_permission_and_module_revocation_apply_to_all_reads_downloads_and_retries(self):
        data = self.payload()
        created = self.client.post(f"{URL}{self.project.pk}/operations-financieres/", data, format="multipart")
        assert created.status_code == 201
        paths = [
            f"{URL}{self.project.pk}/operations-financieres/",
            f"{URL}{self.project.pk}/rapport-financier/",
            f"{URL}{self.project.pk}/exporter-rapport-financier/",
            created.data["operation"]["url_justificatif"],
        ]
        before = self.state()
        self.actor.user_permissions.remove(self.finance_permission)
        for path in paths:
            assert self.client.get(path).status_code in (403, 404)
        retry = self.client.post(
            paths[0], {**data, "justificatif": self.proof()}, format="multipart"
        )
        assert retry.status_code in (403, 404)
        self.actor.user_permissions.add(self.finance_permission)
        ModuleConfiguration.objects.filter(etablissement=self.tenant).update(enabled={"sis.research": False})
        for path in paths:
            assert self.client.get(path).status_code == 403
        assert self.command(amount="1.00").status_code == 403
        ModuleConfiguration.objects.filter(etablissement=self.tenant).update(enabled={"sis.research": True})
        Utilisateur.objects.filter(pk=self.actor.pk).update(is_active=False)
        assert self.client.get(paths[-1]).status_code == 403
        assert self.state() == before

    def test_finance_permission_does_not_grant_confidential_academic_access_or_role_fallback(self):
        detail = self.client.get(f"{URL}{self.project.pk}/")
        assert detail.status_code == 200, detail.data
        assert not detail.data["can_read_academic"]
        for field in ("jalons", "productions", "theses"):
            assert field not in detail.data
        self.client.force_authenticate(self.academic)
        assert self.report().status_code == 403
        assert self.command().status_code == 403

    def test_validated_scopes_cross_project_relations_and_foreign_accounts_deny(self):
        commitment = self.posted("engagement", "20.00", project=self.other_project)
        assert self.command("depense", "1.00", engagement=commitment["id"]).status_code == 400
        receipt = self.posted("financement", "20.00", project=self.other_project)
        assert self.command("contrepassation", "20.00", contrepassation_de=receipt["id"]).status_code == 400
        scopes = {"permission_scopes": {FINANCE: {"projet_id": [self.project.pk]}}}
        Utilisateur.objects.filter(pk=self.actor.pk).update(attributs_acces=scopes)
        assert self.report().status_code == 200
        assert self.report(self.other_project).status_code == 404
        listing = self.client.get(URL)
        assert [row["id"] for row in listing.data["results"]] == [self.project.pk]
        for malformed in (
            [], {"bad": [self.project.pk]}, {"projet_id": []}, {"projet_id": [True]},
            {"projet_id": [str(self.project.pk)]}, {"projet_id": [0]}, {"projet_id": "all"},
        ):
            Utilisateur.objects.filter(pk=self.actor.pk).update(attributs_acces={"permission_scopes": {FINANCE: malformed}})
            assert self.report().status_code in (403, 404)
        Utilisateur.objects.filter(pk=self.actor.pk).update(attributs_acces={}, etablissement=None)
        assert self.report().status_code == 403
        assert self.command().status_code == 403

    def test_foreign_related_teacher_and_request_schema_are_denied(self):
        from apps.recherche.api import ProjetsRechercheViewSet

        Utilisateur.objects.filter(pk=self.academic.pk).update(etablissement=None)
        assert self.report().status_code == 404
        Utilisateur.objects.filter(pk=self.academic.pk).update(etablissement=self.tenant)
        request = APIRequestFactory().get(f"{URL}{self.project.pk}/rapport-financier/")
        force_authenticate(request, self.actor)
        request.tenant = self.tenant
        # A foreign/public connection must be rejected before local ORM reads.
        with schema_context("public"):
            response = ProjetsRechercheViewSet.as_view({"get": "rapport_financier"})(request, pk=self.project.pk)
        assert response.status_code == 403

    def test_foreign_owned_account_is_denied_even_with_finance_permission_and_superuser_flag(self):
        foreign = type(self.tenant)(
            schema_name=f"research_foreign_{uuid4().hex[:12]}",
            nom="Établissement étranger", type="universite_publique",
            adresse="1 rue étrangère", code_postal="75000", ville="Paris",
            telephone="0100000000", email="foreign@example.test",
        )
        foreign.auto_create_schema = False
        with schema_context("public"):
            foreign.save()
        Utilisateur.objects.filter(pk=self.actor.pk).update(etablissement=foreign, is_superuser=True)
        self.actor.refresh_from_db()
        assert self.report().status_code == 403
        assert self.command().status_code == 403
        self.client.force_authenticate(self.academic)
        self.academic.user_permissions.add(self.finance_permission)
        Utilisateur.objects.filter(pk=self.academic.pk).update(etablissement=foreign)
        assert self.report().status_code == 403

    def test_corrupted_balanced_or_missing_journals_fail_reports_exports_and_writes(self):
        receipt = self.posted(amount="20.00")
        table = connection.ops.quote_name(ResearchAccountingLine._meta.db_table)
        with connection.cursor() as cursor:
            cursor.execute(
                f"UPDATE {table} SET debit = CASE WHEN debit > 0 THEN 19 ELSE 0 END, "
                "credit = CASE WHEN credit > 0 THEN 19 ELSE 0 END WHERE operation_id = %s",
                [receipt["id"]],
            )
        before = self.state()
        assert self.report().status_code == 409
        assert self.client.get(f"{URL}{self.project.pk}/exporter-rapport-financier/").status_code == 409
        assert self.client.get(f"{URL}{self.project.pk}/operations-financieres/").status_code == 409
        assert self.command(amount="1.00").status_code == 409
        assert self.state() == before
        with connection.cursor() as cursor:
            cursor.execute(f"DELETE FROM {table} WHERE operation_id = %s", [receipt["id"]])
        assert self.report().status_code == 409

    def test_commitments_cannot_hide_accounting_lines_and_records_are_immutable(self):
        commitment = self.posted("engagement", "20.00")
        operation = ResearchFinanceOperation.objects.get(pk=commitment["id"])
        with pytest.raises(DjangoValidationError):
            operation.save()
        with pytest.raises(DjangoValidationError):
            operation.delete()
        with pytest.raises(DjangoValidationError):
            ResearchFinanceOperation.objects.filter(pk=operation.pk).update(montant=Decimal("1"))
        with pytest.raises(DjangoValidationError):
            ResearchFinanceOperation.objects.filter(pk=operation.pk).delete()
        with pytest.raises(IntegrityError), transaction.atomic():
            ResearchAccountingLine.objects.create(operation=operation, compte="banque", debit=1, credit=1)
        ResearchAccountingLine.objects.create(operation=operation, compte="banque", debit=Decimal("20.00"))
        ResearchAccountingLine.objects.create(operation=operation, compte="financement", credit=Decimal("20.00"))
        assert self.report().status_code == 409

    def test_csv_has_totals_and_every_operation_and_line_without_formula_execution(self):
        self.posted(amount="1.00", reference="=1+1", libelle="@SUM(A1)", justificatif=self.proof(name="+proof.pdf"))
        for index in range(51):
            self.posted("engagement", "0.01", reference=f"CSV-{index}")
        listing = self.client.get(f"{URL}{self.project.pk}/operations-financieres/")
        assert listing.data["count"] == 52
        assert len(listing.data["results"]) == 50
        response = self.client.get(f"{URL}{self.project.pk}/exporter-rapport-financier/")
        assert response.status_code == 200
        rows = list(csv.reader(StringIO(response.content.decode())))
        assert ["engagements_ouverts", "0.51"] in rows
        header = next(index for index, row in enumerate(rows) if row and row[0] == "operation_id")
        data = rows[header + 1:]
        assert len(data) == 53
        assert len({row[0] for row in data}) == 52
        receipt_rows = [row for row in data if row[1] == "financement"]
        assert all(row[4] == "'=1+1" and row[6] == "'@SUM(A1)" and row[10] == "'+proof.pdf" for row in receipt_rows)
        assert "recherche-finance/" not in response.content.decode()

    def test_failed_storage_or_audit_rolls_back_only_new_files_and_all_database_effects(self):
        receipt = self.posted(amount="10.00")
        original = ResearchFinanceOperation.objects.get(pk=receipt["id"]).justificatif
        before = self.state()
        with patch("apps.recherche.finance.record_workflow_event", side_effect=RuntimeError("audit failure")):
            with self.assertRaisesMessage(RuntimeError, "audit failure"):
                self.command(amount="10.00")
        assert self.state() == before
        assert Path(original.path).read_bytes() == PROOF
        real_save = self.storage.save

        def partial_write(name, content, **kwargs):
            real_save(name, content, **kwargs)
            raise OSError("storage failure")

        with patch.object(self.storage, "save", side_effect=partial_write):
            with self.assertRaisesMessage(OSError, "storage failure"):
                self.command(amount="10.00")
        assert self.state() == before
        assert Path(original.path).read_bytes() == PROOF


class ResearchFinanceConcurrencyTests(FinanceFixture):
    @classmethod
    def _fixture_setup(cls):
        TransactionTestCase._fixture_setup.__func__(cls)

    def _fixture_teardown(self):
        with schema_context(self.tenant.schema_name):
            TransactionTestCase._fixture_teardown(self)

    def race(self, commands):
        assert not connection.in_atomic_block
        barrier = Barrier(len(commands))

        def submit(command):
            project, data, *method = command
            try:
                with schema_context(self.tenant.schema_name):
                    client = APIClient(SERVER_NAME=self.get_test_tenant_domain())
                    client.force_authenticate(Utilisateur.objects.get(pk=self.actor.pk))
                    barrier.wait(timeout=20)
                    if method == ["patch"]:
                        response = client.patch(f"{URL}{project.pk}/", data, format="json")
                    else:
                        response = client.post(
                            f"{URL}{project.pk}/operations-financieres/",
                            {**data, "justificatif": self.proof()}, format="multipart",
                        )
                    return response.status_code, response.data
            finally:
                connections["default"].close()

        with ThreadPoolExecutor(max_workers=len(commands)) as pool:
            return list(pool.map(submit, commands))

    def test_simultaneous_payments_cannot_double_spend_or_overwrite_version(self):
        self.posted()
        commitment = self.posted("engagement", "100.00")
        data = self.payload("depense", "70.00", engagement=commitment["id"])
        statuses = sorted(status for status, _ in self.race([
            (self.project, data),
            (self.project, {**data, "reference": "SECOND-PAYMENT", "idempotency_key": str(uuid4())}),
        ]))
        assert statuses == [201, 409]
        assert self.report().data["solde_tresorerie"] == "30.00"
        assert self.report().data["engagements_ouverts"] == "30.00"
        assert self.state()[:4] == (3, 4, 3, 4)

    def test_simultaneous_same_key_replays_exactly_once(self):
        data = self.payload()
        results = self.race([(self.project, data), (self.project, data)])
        assert sorted(status for status, _ in results) == [200, 201]
        assert sorted(result["replayed"] for _, result in results) == [False, True]
        assert self.state()[:4] == (1, 2, 1, 2)
        assert len(self.state()[-1]) == 1

    def test_simultaneous_commitments_cannot_reserve_the_same_budget(self):
        first = self.payload("engagement", "70.00")
        second = self.payload("engagement", "70.00")
        results = self.race([(self.project, first), (self.project, second)])
        assert sorted(status for status, _ in results) == [201, 409]
        assert self.report().data["engagements_ouverts"] == "70.00"
        assert self.state()[:4] == (1, 0, 1, 2)

    def test_metadata_budget_patch_and_financial_reservation_share_project_lock(self):
        self.actor.user_permissions.add(*self.academic.user_permissions.all())
        data = self.payload("engagement", "80.00")
        results = self.race([
            (self.project, data),
            (self.project, {"version": 1, "budget": "50.00"}, "patch"),
        ])
        assert sorted(status for status, _ in results) in ([200, 409], [201, 409])
        report = self.report().data
        assert (report["budget"], report["engagements_ouverts"]) in (("100.00", "80.00"), ("50.00", "0.00"))
        assert report["version"] == 2

    def test_reference_race_across_projects_recovers_savepoint_without_file_or_audit_leak(self):
        first = self.payload()
        second = self.payload(project=self.other_project, reference=first["reference"])
        results = self.race([(self.project, first), (self.other_project, second)])
        assert sorted(status for status, _ in results) == [201, 409]
        assert self.state()[:3] == (1, 2, 1)
        assert len(self.state()[-1]) == 1
        assert self.report().status_code == 200
        assert self.report(self.other_project).status_code == 200

    def test_idempotency_key_race_across_projects_is_a_conflict_not_a_foreign_replay(self):
        first = self.payload()
        second = self.payload(project=self.other_project, idempotency_key=first["idempotency_key"])
        results = self.race([(self.project, first), (self.other_project, second)])
        assert sorted(status for status, _ in results) == [201, 409]
        assert self.state()[:3] == (1, 2, 1)
        assert len(self.state()[-1]) == 1
