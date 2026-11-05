from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from apps.core.models import Reclamation, ReclamationEntry, ReclamationPiece, WorkflowEvent, WorkflowNotification
from apps.integration.tests.tenant_test_case import TenantAPITestCase
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django_tenants.utils import schema_context

from sis_common.exam_files import PrivateExamStorage

BASE = "/api/v1/core/reclamations/"


class ComplaintTests(TenantAPITestCase):
    def setUp(self):
        self.user_model = get_user_model()
        self.owner = self.make_user("owner", "eleve" if settings.SIS_VARIANT == "secondaire" else "etudiant")
        self.other = self.make_user("other", self.owner.role)
        self.staff = self.make_user("staff", "enseignant", is_staff=True)
        self.coordinator = self.make_user("coordinator", "scolarite")
        self.handler = self.make_user("handler", "enseignant")
        self.other_handler = self.make_user("other-handler", "enseignant")
        self.grant(self.coordinator, "affecter_reclamation")
        self.grant(self.handler, "traiter_reclamation")
        self.grant(self.other_handler, "traiter_reclamation")
        self.folder = TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        field = ReclamationPiece._meta.get_field("fichier")
        old_storage = field.storage
        field.storage = PrivateExamStorage(location=self.folder.name)
        self.addCleanup(setattr, field, "storage", old_storage)
        self.client.force_authenticate(self.owner)

    def make_user(self, username, role, **kwargs):
        return self.user_model.objects.create_user(username, role=role, etablissement=self.tenant, **kwargs)

    def grant(self, user, codename):
        user.user_permissions.add(Permission.objects.get(content_type__app_label="core", codename=codename))
        for attr in ("_perm_cache", "_user_perm_cache", "_group_perm_cache"):
            user.__dict__.pop(attr, None)

    def create(self):
        self.client.force_authenticate(self.owner)
        response = self.client.post(
            BASE,
            {
                "categorie": "resultat",
                "objet": "Vérification de résultat",
                "description": "Motif confidentiel.",
                "reference_dossier": "Evaluation 12",
                "demandeur": self.other.pk,
                "statut": "resolue",
                "responsable": self.staff.pk,
            },
            format="json",
        )
        assert response.status_code == 201, response.data
        return response.data

    def post(self, item, action, user, **data):
        self.client.force_authenticate(user)
        return self.client.post(f"{BASE}{item['id']}/{action}/", {"version": item["version"], **data}, format="json")

    def assigned(self):
        item = self.create()
        response = self.post(item, "affecter", self.coordinator, responsable=self.handler.pk)
        assert response.status_code == 200, response.data
        return response.data

    def test_complete_private_workflow_and_immediate_history(self):
        item = self.assigned()
        assert item["statut"] == "en_cours"
        assert len(item["historique"]) == 2
        assert item["demandeur_nom"] == self.owner.username
        assert item["responsable_nom"] == self.handler.username
        assert item["historique"][-1]["auteur_nom"] == self.coordinator.username
        assert item["actions"]["traiter"] is False  # The coordinator is not the assigned handler.
        response = self.post(item, "transition", self.handler, statut="complement", message="Précisez la date.")
        assert response.status_code == 200, response.data
        response = self.post(response.data, "message", self.owner, message="Le 12 octobre.")
        assert response.status_code == 200, response.data
        assert response.data["statut"] == "en_cours"
        response = self.post(response.data, "transition", self.handler, statut="resolue", message="Résultat vérifié.")
        assert response.status_code == 200, response.data
        assert response.data["decision"] == "Résultat vérifié."
        assert response.data["historique"][-1]["message"] == "Résultat vérifié."
        response = self.post(response.data, "transition", self.owner, statut="cloturee", message="Réponse reçue.")
        assert response.status_code == 200
        response = self.post(response.data, "transition", self.owner, statut="recours", message="Nouvel élément.")
        assert response.status_code == 200
        assert response.data["statut"] == "en_cours"
        assert response.data["decision"] == "Résultat vérifié."
        assert WorkflowNotification.objects.filter(recipient=self.owner).count() == 7
        assert WorkflowNotification.objects.filter(recipient=self.handler).exists()
        assert WorkflowNotification.objects.filter(recipient=self.coordinator).exists()
        assert not WorkflowNotification.objects.filter(recipient=self.other).exists()
        assert not WorkflowEvent.objects.filter(message__contains="Motif confidentiel").exists()

    def test_followup_before_assignment_notifies_the_receiving_service(self):
        item = self.create()
        response = self.post(item, "message", self.owner, message="Complément privé avant affectation.")
        assert response.status_code == 200
        assert WorkflowNotification.objects.filter(recipient=self.coordinator).count() == 2
        assert not WorkflowNotification.objects.filter(message__contains="Complément privé").exists()

    def test_update_queries_do_not_grow_with_history_and_authors_remain_fresh(self):
        self.handler.first_name = "Agent"
        self.handler.last_name = "Recette"
        self.handler.save()
        counts = []
        for history_size in (10, 30):
            item = self.assigned()
            ReclamationEntry.objects.bulk_create(
                [
                    ReclamationEntry(
                        reclamation_id=item["id"],
                        auteur=self.handler,
                        action="message",
                        message=f"Historique {index}",
                        statut=item["statut"],
                    )
                    for index in range(history_size - 2)
                ]
            )
            owner = self.user_model.objects.get(pk=self.owner.pk)
            with CaptureQueriesContext(connection) as queries:
                response = self.post(item, "message", owner, message="Nouveau complément.")
            assert response.status_code == 200, response.data
            assert response.data["version"] == item["version"] + 1
            history = response.data["historique"]
            assert len(history) == history_size + 1
            assert history[-1]["message"] == "Nouveau complément."
            assert history[-1]["auteur_nom"] == self.owner.username
            assert "Agent Recette" in {entry["auteur_nom"] for entry in history}
            history_reads = [
                query
                for query in queries
                if query["sql"].lstrip().startswith("SELECT")
                and f'FROM "{ReclamationEntry._meta.db_table}"' in query["sql"]
            ]
            assert len(history_reads) == 1, "Only the updated history should be loaded."
            counts.append(len(queries))
        assert counts[0] == counts[1], f"Queries grow with complaint history: {counts}"

    def test_list_detail_actions_and_files_are_scoped_to_owner_or_assigned_service(self):
        item = self.assigned()
        self.client.force_authenticate(self.owner)
        upload = self.client.post(
            f"{BASE}{item['id']}/pieces/",
            {
                "version": item["version"],
                "fichier": SimpleUploadedFile("preuve.pdf", b"%PDF-1.4\nproof", content_type="application/pdf"),
            },
            format="multipart",
        )
        assert upload.status_code == 200, upload.data
        assert len(upload.data["pieces"]) == 1
        file_url = f"{BASE}{item['id']}/pieces/{upload.data['pieces'][0]['id']}/telecharger/"
        assert "fichier" not in upload.data["pieces"][0]
        for user, expected in (
            (self.owner, 200),
            (self.handler, 200),
            (self.coordinator, 200),
            (self.other, 404),
            (self.other_handler, 404),
            (self.staff, 403),
        ):
            self.client.force_authenticate(user)
            detail = self.client.get(f"{BASE}{item['id']}/")
            assert detail.status_code == expected
            downloaded = self.client.get(file_url)
            assert downloaded.status_code == expected
            if expected == 200:
                assert b"".join(downloaded.streaming_content).startswith(b"%PDF-")
                assert downloaded["Cache-Control"] == "private, no-store"
            else:
                attempted = self.post(upload.data, "message", user, message="Intrusion")
                assert attempted.status_code == expected
                listing = self.client.get(BASE)
                assert listing.status_code == 403 or listing.data["count"] == 0
        self.client.force_authenticate(self.staff)
        audit_url = "/api/v1/core/workflow-events/?model=reclamation"
        assert self.client.get(audit_url).status_code == 403
        self.grant(self.staff, "view_workflowevent")
        response = self.client.get(audit_url)
        assert response.status_code == 200, response.data
        assert not response.data["results"]

    def test_decisions_assignments_and_overposts_cannot_bypass_authorization(self):
        item = self.create()
        obj = Reclamation.objects.get()
        assert obj.demandeur == self.owner
        assert obj.responsable is None
        assert obj.statut == "soumise"
        assert self.post(item, "transition", self.owner, statut="resolue", message="Auto-validation").status_code == 403
        assert self.post(item, "affecter", self.coordinator, responsable=self.staff.pk).status_code == 400
        self.grant(self.owner, "affecter_reclamation")
        self.grant(self.owner, "traiter_reclamation")
        assert self.post(item, "affecter", self.owner, responsable=self.owner.pk).status_code == 403
        assert self.post(item, "affecter", self.coordinator, responsable=self.owner.pk).status_code == 400
        for method in (self.client.patch, self.client.put, self.client.delete):
            assert method(f"{BASE}{item['id']}/", {"statut": "resolue"}, format="json").status_code == 405

    def test_reason_and_version_required_and_duplicate_transition_rejected(self):
        item = self.assigned()
        assert self.post(item, "transition", self.handler, statut="resolue", message=" ").status_code == 400
        self.client.force_authenticate(self.handler)
        assert self.client.post(f"{BASE}{item['id']}/message/", {"message": "Sans version"}).status_code == 400
        response = self.post(item, "message", self.handler, message="Examen en cours.")
        assert response.status_code == 200
        assert self.post(item, "message", self.handler, message="Doublon").status_code == 409
        assert ReclamationEntry.objects.filter(message="Doublon").count() == 0

    def test_revocation_and_tenant_constraints_apply_to_assigned_agents(self):
        item = self.assigned()
        self.handler.attributs_acces = {"permission_scopes": {"core.traiter_reclamation": {"etablissement_id": [-1]}}}
        self.handler.save()
        assert self.post(item, "message", self.handler, message="Interdit").status_code == 403
        self.handler.attributs_acces = {}
        self.handler.etablissement = None
        self.handler.save()
        assert self.post(item, "message", self.handler, message="Mauvais établissement").status_code == 403
        self.handler.etablissement = self.tenant
        self.handler.user_permissions.clear()
        self.handler.save()
        self.handler = self.user_model.objects.get(pk=self.handler.pk)
        assert self.post(item, "message", self.handler, message="Habilitation retirée").status_code == 403

    def test_reassignment_removes_previous_handler_access_and_other_tenant_rows_are_excluded(self):
        item = self.assigned()
        response = self.post(item, "affecter", self.coordinator, responsable=self.other_handler.pk)
        assert response.status_code == 200
        assert self.post(response.data, "message", self.handler, message="Ancien responsable").status_code == 404
        assert self.post(response.data, "message", self.other_handler, message="Nouveau responsable").status_code == 200
        tenant_model = type(self.tenant)
        other_tenant = tenant_model(
            schema_name="complaint_other",
            nom="Autre établissement",
            type=self.tenant.type,
            adresse=self.tenant.adresse,
            code_postal=self.tenant.code_postal,
            ville=self.tenant.ville,
            telephone=self.tenant.telephone,
            email="other@example.test",
        )
        other_tenant.auto_create_schema = False
        with schema_context("public"):
            other_tenant.save()
        Reclamation.objects.filter(pk=item["id"]).update(etablissement=other_tenant)
        for user in (self.owner, self.coordinator, self.other_handler):
            self.client.force_authenticate(user)
            assert self.client.get(f"{BASE}{item['id']}/").status_code == 404
            assert self.client.get(BASE).data["count"] == 0

    def test_invalid_upload_and_notification_failure_leave_no_file_or_partial_history(self):
        item = self.create()
        response = self.client.post(
            f"{BASE}{item['id']}/pieces/",
            {
                "version": item["version"],
                "fichier": SimpleUploadedFile("preuve.pdf", b"not a pdf", content_type="application/pdf"),
            },
            format="multipart",
        )
        assert response.status_code == 400
        assert ReclamationPiece.objects.count() == 0
        with patch("sis_common.complaints.record_workflow_event", side_effect=RuntimeError("notification unavailable")):
            with self.assertRaises(RuntimeError):
                self.client.post(
                    f"{BASE}{item['id']}/pieces/",
                    {
                        "version": item["version"],
                        "fichier": SimpleUploadedFile("preuve.pdf", b"%PDF-1.4\nproof", content_type="application/pdf"),
                    },
                    format="multipart",
                )
        assert ReclamationPiece.objects.count() == 0
        assert ReclamationEntry.objects.count() == 1
        assert Reclamation.objects.get().version == 1
        assert not any(path.is_file() for path in Path(self.folder.name).rglob("*"))
        with patch("sis_common.complaints.record_workflow_event", side_effect=RuntimeError("notification unavailable")):
            with self.assertRaises(RuntimeError):
                self.client.post(
                    BASE,
                    {
                        "categorie": "autre",
                        "objet": "Demande",
                        "description": "Motif",
                    },
                    format="json",
                )
        assert Reclamation.objects.count() == 1
