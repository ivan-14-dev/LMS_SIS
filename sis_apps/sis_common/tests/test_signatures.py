import base64
import json
import uuid
from datetime import timedelta
from unittest.mock import patch

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from django.apps import apps
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import DatabaseError, connection, transaction
from django.db.models import Q
from django.utils import timezone

from sis_common.encryption import decrypt_value
from sis_common.signed_documents import canonical_manifest
from sis_common.tests.test_document_access import DocumentFixture


class SignatureArchiveTests(DocumentFixture):
    signatures = "/api/v1/core/signatures/"
    archives = "/api/v1/core/documents-signes/"
    mandates = "/api/v1/core/mandats-signature/"

    def setUp(self):
        super().setUp()
        self.reviewer = type(self.admin).objects.create_superuser(
            "signature-reviewer", role="super_admin", etablissement=self.tenant
        )
        self.operator = type(self.admin).objects.create_superuser(
            "signature-operator", role="super_admin", etablissement=self.tenant
        )
        self.approvals = apps.get_model("core.SignatureApproval")
        self.archive_model = apps.get_model("core.DocumentArchive")
        self.notifications = apps.get_model("core.WorkflowNotification")
        self.documents_by_type = {records[0]._meta.label_lower: records for records in self.documents.values()}
        self.document_type = next(iter(self.documents_by_type))
        self.signature_payload = {
            "fonction": "Responsable de scolarité",
            "types_documents": list(self.documents_by_type),
            "debut": (timezone.now() - timedelta(hours=1)).isoformat(),
            "fin": (timezone.now() + timedelta(days=30)).isoformat(),
        }

    def request_signature(self):
        self.client.force_authenticate(self.admin)
        response = self.client.post(self.signatures, self.signature_payload, format="json")
        assert response.status_code == 201, response.data
        assert "cle_privee_chiffree" not in response.data
        self.signature_id = response.data["id"]
        return response

    def approve(self):
        self.request_signature()
        self.client.force_authenticate(self.reviewer)
        response = self.client.post(
            f"{self.signatures}{self.signature_id}/decider/",
            {"decision": "validee", "motif": "Identité et fonction contrôlées"},
            format="json",
        )
        assert response.status_code == 200, response.data
        self.client.force_authenticate(self.admin)
        self.signature = self.approvals.objects.get(pk=self.signature_id)

    def archive_payload(self, document_type=None, index=0):
        document_type = document_type or self.document_type
        return {
            "source_type": document_type,
            "source_id": self.documents_by_type[document_type][index].pk,
            "signature": self.signature_id,
            "idempotency_key": str(uuid.uuid4()),
        }

    def sign(self, payload=None):
        response = self.client.post(self.archives, payload or self.archive_payload(), format="json")
        assert response.status_code == 201, response.data
        return response.data["id"]

    def grant_mandate(self):
        response = self.client.post(
            self.mandates,
            {
                "signature": self.signature_id,
                "operateur": self.operator.pk,
                "debut": self.signature_payload["debut"],
                "fin": self.signature_payload["fin"],
                "motif": "Remplacement",
            },
            format="json",
        )
        assert response.status_code == 201, response.data
        assert response.data["titulaire_nom"] == self.admin.username
        assert response.data["operateur_nom"] == self.operator.username
        return response.data["id"]

    def test_independent_approval_and_encrypted_private_key(self):
        response = self.request_signature()
        assert response.data["statut"] == "en_attente"
        assert response.data["cle_publique"] == ""
        decision_url = f"{self.signatures}{self.signature_id}/decider/"
        assert (
            self.client.post(decision_url, {"decision": "validee", "motif": "Moi-même"}, format="json").status_code
            == 403
        )
        assert self.client.post(self.archives, self.archive_payload(), format="json").status_code == 403
        self.client.force_authenticate(self.reviewer)
        response = self.client.post(decision_url, {"decision": "validee", "motif": "Contrôle effectué"}, format="json")
        assert response.status_code == 200, response.data
        signature = self.approvals.objects.get(pk=self.signature_id)
        assert signature.valide_par_id == self.reviewer.pk
        assert signature.cle_privee_chiffree.startswith("gAAAA")
        assert len(base64.b64decode(decrypt_value(signature.cle_privee_chiffree))) == 32
        assert "cle_privee_chiffree" not in response.data
        self.client.force_authenticate(self.admin)
        assert (
            self.client.post(decision_url, {"decision": "suspendue", "motif": "Absence"}, format="json").status_code
            == 200
        )
        assert self.client.post(self.archives, self.archive_payload(), format="json").status_code == 403
        assert (
            self.client.post(decision_url, {"decision": "validee", "motif": "Retour"}, format="json").status_code == 403
        )

    def test_real_documents_have_private_verifiable_archives_and_exactly_one_notification_per_use(self):
        self.approve()
        for document_type in self.documents_by_type:
            payload = self.archive_payload(document_type)
            archive_id = self.sign(payload)
            again = self.client.post(self.archives, payload, format="json")
            assert again.status_code == 200, again.data
            assert again.data["id"] == archive_id
            assert again.data["titulaire_nom"] == self.admin.username
            assert again.data["beneficiaire_nom"] == self.learners[0].user.get_full_name()
            notifications = self.notifications.objects.filter(
                recipient=self.admin, category="signature_apposee", event__object_id=archive_id
            )
            assert notifications.count() == 1
            self.client.force_authenticate(self.learners[0].user)
            pdf = self.client.get(f"{self.archives}{archive_id}/pdf/")
            assert pdf.status_code == 200
            assert pdf.content.startswith(b"%PDF-")
            assert pdf["Cache-Control"] == "private, no-store"
            proof = json.loads(self.client.get(f"{self.archives}{archive_id}/preuve/").content)
            Ed25519PublicKey.from_public_bytes(base64.b64decode(proof["cle_publique"])).verify(
                base64.b64decode(proof["preuve"]), canonical_manifest(proof["manifeste"])
            )
            verified = self.client.post(f"{self.archives}{archive_id}/verifier/", {}, format="json")
            assert verified.status_code == 200, verified.data
            assert verified.data["integrite"] is True
            assert (
                self.client.post(
                    f"{self.archives}{archive_id}/verifier/",
                    {
                        "pdf": SimpleUploadedFile(
                            "document.pdf", pdf.content + b" altered", content_type="application/pdf"
                        )
                    },
                    format="multipart",
                ).status_code
                == 400
            )
            assert notifications.count() == 1
            self.client.force_authenticate(self.learners[1].user)
            for suffix in ("", "pdf/", "preuve/", "historique/"):
                assert self.client.get(f"{self.archives}{archive_id}/{suffix}").status_code == 404
            self.client.force_authenticate(self.admin)
            conflict = {**payload, "source_id": self.documents_by_type[document_type][1].pk}
            assert self.client.post(self.archives, conflict, format="json").status_code == 409
            assert (
                self.client.post(self.archives, self.archive_payload(document_type, 3), format="json").status_code
                == 404
            )
        assert self.archive_model.objects.count() == len(self.documents_by_type)

    def test_public_verification_uses_presented_pdf_without_disclosing_archive(self):
        self.approve()
        archive_id = self.sign()
        pdf = bytes(self.archive_model.objects.get(pk=archive_id).pdf)
        url = f"{self.archives}verification-publique/"

        def verify(content):
            return self.client.post(
                url,
                {
                    "archive_id": archive_id,
                    "pdf": SimpleUploadedFile("document.pdf", content, content_type="application/pdf"),
                },
                format="multipart",
            )

        self.client.force_authenticate(user=None)
        valid = verify(pdf)
        assert valid.status_code == 200, valid.data
        assert valid.data == {"valide": True}
        assert valid["Cache-Control"] == "no-store"
        assert verify(pdf + b" altered").data == {"valide": False}
        self.client.force_authenticate(self.admin)
        revoked = self.client.post(
            f"{self.archives}{archive_id}/revoquer/", {"motif": "Document retiré"}, format="json"
        )
        assert revoked.status_code == 200, revoked.data
        self.client.force_authenticate(user=None)
        assert verify(pdf).data == {"valide": False}

    def test_mandate_is_required_revocable_and_does_not_change_signer_identity(self):
        self.approve()
        self.client.force_authenticate(self.operator)
        assert self.client.post(self.archives, self.archive_payload(), format="json").status_code == 403
        self.client.force_authenticate(self.admin)
        mandate_id = self.grant_mandate()
        self.client.force_authenticate(self.operator)
        archive_id = self.sign()
        archive = self.archive_model.objects.get(pk=archive_id)
        assert archive.mandat_id == mandate_id
        assert archive.operateur_id == self.operator.pk
        assert archive.signature.titulaire_id == self.admin.pk
        assert (
            self.notifications.objects.filter(
                recipient=self.admin, event__object_id=archive_id, category="signature_apposee"
            ).count()
            == 1
        )
        self.client.force_authenticate(self.admin)
        response = self.client.post(
            f"{self.mandates}{mandate_id}/revoquer/", {"motif": "Fin de remplacement"}, format="json"
        )
        assert response.status_code == 200, response.data
        self.client.force_authenticate(self.operator)
        assert self.client.post(self.archives, self.archive_payload(), format="json").status_code == 403

    def test_delegated_usable_signatures_exclude_inactive_holder(self):
        self.approve()
        self.grant_mandate()
        self.client.force_authenticate(self.operator)
        usable = self.client.get(self.signatures, {"vue": "utilisables"})
        assert usable.status_code == 200, usable.data
        assert [item["id"] for item in usable.data["results"]] == [self.signature_id]

        self.admin.is_active = False
        self.admin.save(update_fields=["is_active"])
        usable = self.client.get(self.signatures, {"vue": "utilisables"})
        assert usable.status_code == 200, usable.data
        assert usable.data["count"] == 0
        assert self.client.post(self.archives, self.archive_payload(), format="json").status_code == 403

    def test_expiration_revocation_versions_and_database_immutability(self):
        self.approve()
        archive_id = self.sign()
        second = self.sign()
        assert self.archive_model.objects.get(pk=second).version == 2
        archive = self.archive_model.objects.get(pk=archive_id)
        with pytest.raises(ValidationError):
            archive.delete()
        with pytest.raises(ValidationError):
            self.archive_model.objects.filter(pk=archive_id).update(version=99)
        with pytest.raises(DatabaseError, match="immuables"), transaction.atomic(), connection.cursor() as cursor:
            cursor.execute("UPDATE core_documentarchive SET version=99 WHERE id=%s", [archive_id])
        response = self.client.post(
            f"{self.archives}{archive_id}/revoquer/", {"motif": "Correction nécessaire"}, format="json"
        )
        assert response.status_code == 200, response.data
        with pytest.raises(DatabaseError, match="immuables"), transaction.atomic(), connection.cursor() as cursor:
            cursor.execute("DELETE FROM core_archiverevocation WHERE archive_id=%s", [archive_id])
        self.approvals.objects.filter(pk=self.signature_id).update(fin=timezone.now() - timedelta(minutes=1))
        assert self.client.post(self.archives, self.archive_payload(), format="json").status_code == 403
        self.client.force_authenticate(self.learners[0].user)
        for pk, expected in ((archive_id, "revoque"), (second, "valide")):
            response = self.client.post(f"{self.archives}{pk}/verifier/", {}, format="json")
            assert response.status_code == 200, response.data
            assert response.data["statut"] == expected

    def test_notification_failure_or_corrupt_key_prevents_archive_creation(self):
        self.approve()
        with patch.object(self.notifications.objects, "create", side_effect=RuntimeError("notification failed")):
            with pytest.raises(RuntimeError, match="notification failed"):
                self.sign()
        assert self.archive_model.objects.count() == 0
        assert not apps.get_model("core.WorkflowEvent").objects.filter(action="signature_apposee").exists()
        self.approvals.objects.filter(pk=self.signature_id).update(cle_privee_chiffree="invalid encrypted key")
        response = self.client.post(self.archives, self.archive_payload(), format="json")
        assert response.status_code == 500, response.data
        assert self.archive_model.objects.count() == 0

    def test_staff_or_learner_flags_cannot_approve_or_sign_and_private_events_stay_private(self):
        self.approve()
        self.sign()
        self.client.force_authenticate(self.admin)
        for model in ("signatureapproval", "documentarchive", "accessdelegation"):
            response = self.client.get("/api/v1/core/workflow-events/", {"model": model})
            assert response.status_code == 200, response.data
            assert response.data["count"] == 0
        for user in (self.teacher, self.learners[0].user):
            user.is_staff = True
            if user == self.learners[0].user:
                user.user_permissions.add(
                    *Permission.objects.filter(
                        content_type__app_label="core",
                        codename__in=["request_signature", "approve_signature", "use_signature"],
                    )
                )
            user.save(update_fields=["is_staff"])
            self.client.force_authenticate(user)
            assert self.client.post(self.signatures, self.signature_payload, format="json").status_code == 403
            assert self.client.post(self.archives, self.archive_payload(), format="json").status_code == 403
            assert self.client.get(f"{self.signatures}?vue=validation").status_code == 403

    def test_change_scope_and_current_owner_cannot_expose_another_person_archive(self):
        self.approve()
        archive_id = self.sign()
        source = self.documents_by_type[self.document_type][0]
        self.documents_by_type[self.document_type][1].delete()
        owner = "eleve" if self.secondary else "etudiant"
        setattr(source, owner, self.learners[1])
        source.save(update_fields=[owner])
        self.client.force_authenticate(self.learners[1].user)
        assert self.client.get(f"{self.archives}{archive_id}/").status_code == 404
        self.client.force_authenticate(self.learners[0].user)
        assert self.client.get(f"{self.archives}{archive_id}/").status_code == 200
        self.admin.is_superuser = False
        self.admin.is_staff = False
        self.admin.role = "autre"
        model = source._meta
        self.admin.user_permissions.add(
            *Permission.objects.filter(
                Q(content_type__app_label="core", codename="use_signature")
                | Q(
                    content_type__app_label=model.app_label,
                    codename__in=[f"view_{model.model_name}", f"change_{model.model_name}"],
                )
            )
        )
        scope = "classes" if self.secondary else "etudiants"
        self.admin.attributs_acces = {
            "permission_scopes": {f"{model.app_label}.change_{model.model_name}": {scope: []}}
        }
        self.admin.save(update_fields=["is_superuser", "is_staff", "role", "attributs_acces"])
        self.client.force_authenticate(type(self.admin).objects.get(pk=self.admin.pk))
        assert self.client.post(self.archives, self.archive_payload(), format="json").status_code == 404
