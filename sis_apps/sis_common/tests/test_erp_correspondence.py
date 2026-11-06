"""Both SIS variants run this test against their own tenant schema."""

from apps.core.models import Correspondance, WorkflowEvent
from apps.integration.tests.tenant_test_case import TenantAPITestCase
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django_tenants.utils import schema_context

BASE = "/api/v1/core/correspondances/"


class CorrespondanceTests(TenantAPITestCase):
    def setUp(self):
        user_model = get_user_model()
        self.creator = user_model.objects.create_user(
            "erp-creator", role="personnel_administratif", etablissement=self.tenant
        )
        self.coordinator = user_model.objects.create_user(
            "erp-coordinator", role="personnel_administratif", etablissement=self.tenant
        )
        self.reviewer = user_model.objects.create_user(
            "erp-reviewer", role="personnel_administratif", etablissement=self.tenant
        )
        self.unprivileged = user_model.objects.create_user(
            "erp-outsider", role="personnel_administratif", etablissement=self.tenant, is_staff=True
        )
        self.learner = user_model.objects.create_user(
            "erp-learner", role="eleve" if settings.SIS_VARIANT == "secondaire" else "etudiant",
            etablissement=self.tenant, is_staff=True,
        )
        self.grant(self.creator, "view_correspondance", "add_correspondance")
        self.grant(self.coordinator, "view_correspondance", "assign_correspondance", "archive_correspondance")
        self.grant(self.reviewer, "view_correspondance", "approve_correspondance", "archive_correspondance")
        self.grant(self.learner, "view_correspondance", "add_correspondance", "approve_correspondance")

    def grant(self, user, *codenames):
        user.user_permissions.add(*[
            Permission.objects.get(content_type__app_label="core", codename=codename)
            for codename in codenames
        ])
        for key in ("_perm_cache", "_user_perm_cache", "_group_perm_cache"):
            user.__dict__.pop(key, None)

    def create(self, direction="entrante"):
        self.client.force_authenticate(self.creator)
        response = self.client.post(BASE, {
            "direction": direction,
            "expediteur": "Partenaire externe",
            "destinataire": "Secrétariat",
            "objet": "Suivi de dossier",
            "contenu": "Contenu confidentiel",
            "reference_externe": "EXT-101",
            "statut": "archivee",
            "approuve_par": self.creator.pk,
            "etablissement": -1,
        }, format="json")
        assert response.status_code == 201, response.data
        return response.data

    def transition(self, item, action, actor, **fields):
        self.client.force_authenticate(actor)
        return self.client.post(
            f"{BASE}{item['id']}/{action}/", {"version": item["version"], **fields}, format="json"
        )

    def test_incoming_and_outgoing_have_independent_audited_lifecycles(self):
        for direction in ("entrante", "sortante"):
            item = self.create(direction)
            assert item["statut"] == "enregistree"
            assert item["direction"] == direction
            assert item["cree_par"] == self.creator.pk
            assert item["version"] == 1
            assert item["approuve_par"] is None
            assignment = self.transition(item, "affecter", self.coordinator, assigne_a=self.reviewer.pk)
            assert assignment.status_code == 200, assignment.data
            item = assignment.data
            assert item["statut"] == "affectee"
            approval = self.transition(item, "approuver", self.reviewer)
            assert approval.status_code == 200, approval.data
            item = approval.data
            assert item["approuve_par"] == self.reviewer.pk
            assert item["approuve_le"] is not None
            self.client.force_authenticate(self.reviewer)
            assert self.transition(item, "archiver", self.reviewer).status_code == 403
            archived = self.transition(item, "archiver", self.coordinator)
            assert archived.status_code == 200, archived.data
            item = archived.data
            assert item["statut"] == "archivee"
            assert item["version"] == 4
            assert item["archive_par"] == self.coordinator.pk
            self.client.force_authenticate(self.creator)
            history = self.client.get(f"{BASE}{item['id']}/historique/")
            assert history.status_code == 200, history.data
            assert {event["action"] for event in history.data} == {
                "correspondance_enregistree", "correspondance_affectee",
                "correspondance_approuvee", "correspondance_archivee",
            }
            assert all(event["metadata"]["direction"] == direction for event in history.data)
            detail = self.client.get(f"{BASE}{item['id']}/")
            assert detail.status_code == 200
            assert detail["Cache-Control"] == "private, no-store"
            assert WorkflowEvent.objects.filter(action="correspondance_consultee", object_id=item["id"]).count() == 1
            assert not WorkflowEvent.objects.filter(object_id=item["id"], message__contains="confidentiel").exists()
            assert self.transition(item, "archiver", self.coordinator).status_code == 400
            assert self.transition(item, "approuver", self.reviewer).status_code == 400
        self.client.force_authenticate(self.creator)
        assert self.client.get(BASE, {"direction": "sortante"}).data["count"] == 1
        assert Correspondance.objects.count() == 2

    def test_permissions_separation_invalid_inputs_and_concurrency(self):
        self.client.force_authenticate(self.unprivileged)
        assert self.client.get(BASE).status_code == 403
        assert self.client.post(BASE, {}, format="json").status_code == 403
        self.client.force_authenticate(self.learner)
        assert self.client.get(BASE).status_code == 403
        self.client.force_authenticate(self.creator)
        assert self.client.post(BASE, {"direction": "autre"}, format="json").status_code == 400
        item = self.create()
        self.client.force_authenticate(self.creator)
        assert self.client.patch(f"{BASE}{item['id']}/", {"objet": "Détourné"}, format="json").status_code == 405
        assert self.transition(item, "archiver", self.coordinator).status_code == 400
        assert self.transition(item, "approuver", self.reviewer).status_code == 400
        assert self.transition(item, "affecter", self.creator, assigne_a=self.reviewer.pk).status_code == 403
        for assignee in (self.creator, self.coordinator, self.unprivileged, self.learner):
            assert self.transition(
                item, "affecter", self.coordinator, assigne_a=assignee.pk
            ).status_code == 400
        response = self.transition(item, "affecter", self.coordinator, assigne_a=self.reviewer.pk)
        assert response.status_code == 200, response.data
        assert self.transition(item, "affecter", self.coordinator, assigne_a=self.reviewer.pk).status_code == 409
        assigned = response.data
        assert self.transition(assigned, "approuver", self.coordinator).status_code == 403
        self.reviewer.is_active = False
        self.reviewer.save(update_fields=["is_active"])
        assert self.transition(assigned, "approuver", self.reviewer).status_code == 403
        assert Correspondance.objects.get(pk=item["id"]).statut == "affectee"
        assert WorkflowEvent.objects.filter(object_id=item["id"]).count() == 2

    def test_creator_cannot_archive_own_approved_correspondence(self):
        self.grant(self.creator, "archive_correspondance")
        for direction in ("entrante", "sortante"):
            item = self.create(direction)
            assigned = self.transition(item, "affecter", self.coordinator, assigne_a=self.reviewer.pk)
            assert assigned.status_code == 200, assigned.data
            approved = self.transition(assigned.data, "approuver", self.reviewer)
            assert approved.status_code == 200, approved.data
            item = approved.data

            rejected = self.transition(item, "archiver", self.creator)
            assert rejected.status_code == 403, rejected.data
            unchanged = Correspondance.objects.get(pk=item["id"])
            assert unchanged.statut == "approuvee"
            assert unchanged.version == item["version"]
            assert unchanged.archive_par_id is None
            assert not WorkflowEvent.objects.filter(
                object_id=item["id"], action="correspondance_archivee"
            ).exists()

            archived = self.transition(item, "archiver", self.coordinator)
            assert archived.status_code == 200, archived.data
            assert archived.data["version"] == item["version"] + 1

    def test_former_assigner_cannot_approve_after_reassignment(self):
        self.grant(self.reviewer, "assign_correspondance")
        self.grant(self.coordinator, "approve_correspondance")
        successor = get_user_model().objects.create_user(
            "erp-successor", role="personnel_administratif", etablissement=self.tenant
        )
        self.grant(successor, "view_correspondance", "approve_correspondance")
        item = self.create()
        assigned = self.transition(item, "affecter", self.coordinator, assigne_a=self.reviewer.pk)
        assert assigned.status_code == 200, assigned.data
        item = assigned.data

        assert self.transition(
            item, "affecter", self.reviewer, assigne_a=self.coordinator.pk
        ).status_code == 400
        assert Correspondance.objects.get(pk=item["id"]).version == item["version"]

        reassigned = self.transition(item, "affecter", self.reviewer, assigne_a=successor.pk)
        assert reassigned.status_code == 200, reassigned.data
        item = reassigned.data
        # A legacy reassignment may already have assigned the former assigner.
        Correspondance.objects.filter(pk=item["id"]).update(assigne_a=self.coordinator)
        assert self.transition(item, "approuver", self.coordinator).status_code == 403
        assert Correspondance.objects.get(pk=item["id"]).statut == "affectee"

        Correspondance.objects.filter(pk=item["id"]).update(assigne_a=successor)
        approved = self.transition(item, "approuver", successor)
        assert approved.status_code == 200, approved.data

    def test_tenant_boundaries_apply_to_read_assignment_and_approval(self):
        item = self.create()
        other_tenant = type(self.tenant)(
            schema_name="erp_correspondence_other", nom="Autre établissement",
            type=self.tenant.type, adresse=self.tenant.adresse, code_postal=self.tenant.code_postal,
            ville=self.tenant.ville, telephone=self.tenant.telephone, email="other-erp@example.test",
        )
        other_tenant.auto_create_schema = False
        with schema_context("public"):
            other_tenant.save()
        foreign = get_user_model().objects.create_user(
            "erp-foreign", role="personnel_administratif", etablissement=other_tenant
        )
        self.grant(foreign, "view_correspondance", "approve_correspondance")
        assert self.transition(item, "affecter", self.coordinator, assigne_a=foreign.pk).status_code == 404
        self.client.force_authenticate(foreign)
        assert self.client.get(BASE).status_code == 403
        assert self.client.get(f"{BASE}{item['id']}/").status_code == 403
        assert self.transition(item, "approuver", foreign).status_code == 403
        Correspondance.objects.filter(pk=item["id"]).update(etablissement=other_tenant)
        for actor in (self.creator, self.coordinator, self.reviewer):
            self.client.force_authenticate(actor)
            assert self.client.get(f"{BASE}{item['id']}/").status_code == 404
            assert self.client.get(BASE).data["count"] == 0
        assert self.transition(item, "affecter", self.coordinator, assigne_a=self.reviewer.pk).status_code == 404
        assert self.transition(item, "approuver", self.reviewer).status_code == 404

    def test_persisted_assigner_cannot_be_reassigned_without_assignment_history(self):
        self.grant(self.reviewer, "assign_correspondance")
        self.grant(self.coordinator, "approve_correspondance")
        successor = get_user_model().objects.create_user(
            "erp-legacy-successor", role="personnel_administratif", etablissement=self.tenant
        )
        self.grant(successor, "view_correspondance", "approve_correspondance")

        for direction in ("entrante", "sortante"):
            item = self.create(direction)
            # Imported assignments can retain their actor fields without a workflow event.
            Correspondance.objects.filter(pk=item["id"]).update(
                statut="affectee", assigne_a=self.reviewer, assigne_par=self.coordinator, version=2
            )
            item["version"] = 2
            before = Correspondance.objects.values().get(pk=item["id"])
            history = list(WorkflowEvent.objects.filter(object_id=item["id"]).values())
            assert not WorkflowEvent.objects.filter(
                object_id=item["id"], action="correspondance_affectee"
            ).exists()

            rejected = self.transition(item, "affecter", self.reviewer, assigne_a=self.coordinator.pk)
            assert rejected.status_code == 400, rejected.data
            assert "assigne_a" in rejected.data
            assert Correspondance.objects.values().get(pk=item["id"]) == before
            assert list(WorkflowEvent.objects.filter(object_id=item["id"]).values()) == history

            reassigned = self.transition(item, "affecter", self.reviewer, assigne_a=successor.pk)
            assert reassigned.status_code == 200, reassigned.data
            assert reassigned.data["assigne_a"] == successor.pk
            assert reassigned.data["assigne_par"] == self.reviewer.pk
            assert reassigned.data["version"] == item["version"] + 1
            approved = self.transition(reassigned.data, "approuver", successor)
            assert approved.status_code == 200, approved.data
            archived = self.transition(approved.data, "archiver", self.coordinator)
            assert archived.status_code == 200, archived.data
            assert archived.data["statut"] == "archivee"
            assert archived.data["contenu"] == item["contenu"]
