from apps.core.models import WorkflowEvent
from apps.integration.tests.tenant_test_case import TenantAPITestCase
from django.contrib.auth import get_user_model

BASE = "/api/v1/core/workflow-events/"


class ResearchWorkflowPrivacyTests(TenantAPITestCase):
    def test_generic_auditor_cannot_read_or_count_private_research_history(self):
        users = get_user_model()
        auditor = users.objects.create_superuser("research-auditor", etablissement=self.tenant)
        private_actor = users.objects.create_user("private-research-actor", etablissement=self.tenant)
        for app_label, model in (
            ("recherche", "laboratoire"),
            ("recherche", "projetrecherche"),
            ("recherche", "researchfinanceoperation"),
            ("core", "institutionalevent"),
        ):
            WorkflowEvent.objects.create(
                actor=private_actor,
                tenant_id=self.tenant.pk,
                app_label=app_label,
                model=model,
                object_id="1",
                object_repr="Private research object",
                action="private_research",
                title="Private research history",
                metadata={"reference": "PRIVATE-RESEARCH"},
            )
        public_event = WorkflowEvent.objects.create(
            actor=auditor,
            tenant_id=self.tenant.pk,
            app_label="notes",
            model="evaluation",
            object_id="2",
            object_repr="Public workflow object",
            action="public_workflow",
            title="Public workflow history",
        )
        self.client.force_authenticate(auditor)
        listed = self.client.get(BASE)
        assert listed.status_code == 200, listed.data
        assert listed.data["count"] == 1
        assert str(listed.data["results"][0]["id"]) == str(public_event.pk)
        actors = self.client.get(BASE + "acteurs/")
        assert actors.status_code == 200, actors.data
        assert [row["id"] for row in actors.data] == [auditor.pk]
        summary = self.client.get(BASE + "bilan/")
        assert summary.status_code == 200, summary.data
        assert summary.data == [{"groupe": "public_workflow", "nombre": 1}]
        filtered = self.client.get(BASE, {"app_label": "recherche"})
        assert filtered.status_code == 200, filtered.data
        assert filtered.data["count"] == 0
        assert WorkflowEvent.objects.filter(app_label="recherche").count() == 3
