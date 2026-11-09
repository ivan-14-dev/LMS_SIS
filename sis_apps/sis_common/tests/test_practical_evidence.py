"""Private PDF ownership, multipart validation and transactional failure regressions."""

import json
from hashlib import sha256

from apps.core.models import ModuleConfiguration
from django.contrib.auth import get_user_model
from django.core.exceptions import SuspiciousFileOperation
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings

from sis_common.tests.practical_fixtures import BASE, PDF, PracticalFixture, practical_model


class PracticalEvidenceTests(PracticalFixture):
    def test_private_multipart_hash_owner_and_fresh_authorized_download(self):
        self.prepare()
        response = self.upload(name="../preuve professionnelle.pdf")
        assert response.status_code == 201, response.data
        hour = response.data["heure"]
        evidence = hour["preuve"]
        assert evidence["sha256"] == sha256(PDF).hexdigest()
        assert evidence["taille"] == len(PDF)
        assert evidence["version_creation"] == response.data["version"]
        assert evidence["content_type"] == "application/pdf"
        assert "/" not in evidence["nom"]
        assert evidence["download_url"] == self.url(f"heures/{hour['id']}/preuve/")
        row = practical_model("HeurePratique").objects.get(pk=hour["id"])
        assert row.fichier.name.startswith(
            f"pratique/{self.tenant.schema_name}/{self.tenant.pk}/{self.dossier['id']}/heures/"
        )
        with row.fichier.open("rb") as stream:
            assert stream.read() == PDF
        with self.assertRaises(SuspiciousFileOperation):  # noqa: PT027
            _ = row.fichier.url
        wire = json.dumps(response.data)
        assert row.fichier.name not in wire
        assert "pdf_path" not in wire
        assert "legacy@example.test" not in wire
        for user in (self.learner_user, self.tutor, self.partner, self.manager):
            self.login(user)
            download = self.client.get(evidence["download_url"])
            assert download.status_code == 200
            assert download["Content-Type"] == "application/pdf"
            assert download["Cache-Control"] == "private, no-store"
            assert download["X-Content-Type-Options"] == "nosniff"
            assert download["Content-Disposition"].startswith("attachment;")
            assert b"".join(download.streaming_content) == PDF
        self.login(self.outsider)
        self.assert_error(self.client.get(evidence["download_url"]), 404)
        self.login(self.partner)
        download = self.client.get(evidence["download_url"])
        assert download.status_code == 200
        assert b"".join(download.streaming_content) == PDF
        self.partner.user_permissions.clear()
        self.assert_error(self.client.get(evidence["download_url"]), 404)
        get_user_model().objects.filter(pk=self.partner.pk).update(is_active=False)
        self.assert_error(self.client.get(evidence["download_url"]), 403)
        self.login(self.manager)
        ModuleConfiguration.objects.filter(etablissement=self.tenant).update(enabled={"sis.practical_training": False})
        self.assert_error(self.client.get(evidence["download_url"]), 403)
        self.client.force_authenticate(user=None)
        assert self.client.get(evidence["download_url"]).status_code in (401, 403)

    def test_replacement_does_not_copy_rebind_or_destroy_older_evidence(self):
        self.prepare()
        response = self.upload()
        assert response.status_code == 201, response.data
        original = response.data["heure"]
        old_files = self.state()["files"]
        replacement = self.command(
            f"heures/{original['id']}/remplacer/", self.learner_user,
            **self.hour_payload(heure_fin="10:00"), motif="Correction sans nouvelle pièce.",
        )
        assert replacement.status_code == 201, replacement.data
        assert replacement.data["heure"]["preuve"] is None
        assert replacement.data["heure_precedente"]["preuve"]["sha256"] == original["preuve"]["sha256"]
        assert self.state()["files"] == old_files
        self.login(self.learner_user)
        download = self.client.get(original["preuve"]["download_url"])
        assert b"".join(download.streaming_content) == PDF
        other = self.open_dossier(self.make_convention())
        self.assert_error(self.client.get(
            f"{BASE}dossiers/{other['id']}/heures/{original['id']}/preuve/"
        ), 404)
        self.login(self.outsider)
        before = self.state()
        self.assert_error(self.upload(user=self.outsider, content=PDF + b"unauthorized"), 404)
        assert self.state() == before

    def test_assessment_revision_keeps_both_private_files_and_only_new_revision_effective(self):
        self.prepare()
        payload = {
            "version": self.dossier["version"], "acquise": False,
            "contexte_professionnel": "Protection non maîtrisée.", "date_observation": "2026-11-07",
        }
        first = self.upload("competences/securite/evaluer/", self.tutor, payload=payload)
        assert first.status_code == 201, first.data
        original = first.data["evaluation"]
        second = self.upload("competences/securite/evaluer/", self.tutor, payload={
            **payload, "version": self.dossier["version"], "acquise": True,
            "motif_revision": "Observation complémentaire.", "date_observation": "2026-11-06",
        }, content=PDF + b"second decision")
        assert second.status_code == 201, second.data
        assert second.data["evaluation"]["remplace_id"] == original["id"]
        assert second.data["evaluation"]["preuve"]["sha256"] != original["preuve"]["sha256"]
        history = self.client.get(self.url("evaluations/"))
        assert history.status_code == 200, history.data
        assert [(row["id"], row["effective"]) for row in history.data["results"]] == [
            (second.data["evaluation"]["id"], True), (original["id"], False),
        ]
        assert self.report()["competences_acquises"] == 1
        for assessment, content in ((original, PDF), (second.data["evaluation"], PDF + b"second decision")):
            download = self.client.get(assessment["preuve"]["download_url"])
            assert download.status_code == 200
            assert b"".join(download.streaming_content) == content

    def test_malformed_multipart_invalid_pdf_and_stale_upload_create_no_rows_or_files(self):
        self.prepare()
        before = self.state()
        valid_payload = json.dumps(self.hour_payload())
        invalid_wrappers = (
            {"payload": "{"},
            {"payload": "[]"},
            {"payload": valid_payload, "reusable_evidence_id": 1},
            {"payload": [valid_payload, valid_payload]},
            {"payload": json.dumps(self.hour_payload(version=str(self.dossier["version"])))},
            {"payload": valid_payload, "fichier": [
                SimpleUploadedFile("one.pdf", PDF, content_type="application/pdf"),
                SimpleUploadedFile("two.pdf", PDF, content_type="application/pdf"),
            ]},
        )
        self.login(self.learner_user)
        for wrapper in invalid_wrappers:
            response = self.client.post(self.url("heures/"), wrapper, format="multipart")
            self.assert_error(response, 400, "validation_error")
            assert self.state() == before
        for content, name in ((b"not a PDF", "proof.pdf"), (PDF, "proof.html")):
            self.assert_error(self.upload(content=content, name=name), 400, "pdf_invalide")
            assert self.state() == before
        with override_settings(EXAM_COPY_MAX_SIZE=4):
            self.assert_error(self.upload(), 400, "pdf_invalide")
        assert self.state() == before
        self.assert_error(self.command(
            "heures/", self.learner_user, **self.hour_payload(), fichier="existing-private-key.pdf"
        ), 400, "validation_error")
        assert self.state() == before
        self.record()
        before = self.state()
        self.assert_error(self.upload(payload=self.hour_payload(version=1)), 409, "version_perimee")
        assert self.state() == before
        self.assert_error(self.upload(), 409, "intervalle_occupe")
        assert self.state() == before

    def test_actual_database_audit_failure_removes_only_new_upload_and_rolls_back_rows(self):
        self.prepare()
        existing = self.upload()
        assert existing.status_code == 201, existing.data
        practical_model("AuditPratique").objects.create(
            dossier_id=self.dossier["id"], version=self.dossier["version"] + 1,
            action="heure_creation", acteur=self.manager, acteur_nom="Audit collision",
        )
        before = self.state()
        self.client.raise_request_exception = False
        try:
            response = self.upload(
                payload=self.hour_payload(heure_debut="12:00", heure_fin="13:00"), content=PDF + b"must be removed",
            )
        finally:
            self.client.raise_request_exception = True
        assert response.status_code >= 400, "La contrainte unique d'audit doit faire échouer la transaction."
        assert self.state() == before
        row = practical_model("HeurePratique").objects.get(pk=existing.data["heure"]["id"])
        with row.fichier.open("rb") as stream:
            assert stream.read() == PDF

    def test_missing_bytes_and_absent_evidence_return_404_not_empty_pdf(self):
        self.prepare()
        first = self.record()
        self.assert_error(self.client.get(self.url(f"heures/{first['id']}/preuve/")), 404)
        uploaded = self.upload(payload=self.hour_payload(heure_debut="12:00", heure_fin="13:00"))
        assert uploaded.status_code == 201, uploaded.data
        row = practical_model("HeurePratique").objects.get(pk=uploaded.data["heure"]["id"])
        self.storage.delete(row.fichier.name)
        self.assert_error(self.client.get(uploaded.data["heure"]["preuve"]["download_url"]), 404)
