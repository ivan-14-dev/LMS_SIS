from django.apps import apps
from django.contrib.auth.models import Permission
from django_tenants.utils import schema_context

from sis_common.tests.test_grade_entry import GradeEntryFixture


class DocumentFixture(GradeEntryFixture):
    def setUp(self):
        super().setUp()
        second_period = self.create(
            self.period_model,
            **{self.year_field: self.year},
            **{**self.period_values, "numero": 2},
        )
        self.documents = {}
        self.resources = ["bulletins"] if self.secondary else ["releves", "releves/transcripts", "releves/attestations"]
        for resource in self.resources:
            records = []
            for index, learner in enumerate([*self.learners, self.learners[0]]):
                approved = index < 2
                period = second_period if index == 3 else self.period
                if self.secondary:
                    document = self.create(
                        "notes.Bulletin",
                        eleve=learner,
                        classe=self.classe,
                        periode=period,
                        publie=approved,
                        moyenne_generale=0,
                    )
                elif resource == "releves":
                    document = self.create(
                        "releves.ReleveNotes",
                        etudiant=learner,
                        semestre=period,
                        signe=approved,
                        signe_par=self.admin if approved else None,
                        date_emission=self.today,
                        numero_serie=f"RELEVE-{index}",
                        moyenne_generale=0,
                    )
                elif resource.endswith("transcripts"):
                    document = self.create(
                        "releves.Transcript",
                        etudiant=learner,
                        credits_total=60,
                        credits_valides=30,
                        signe_par=self.admin if approved else None,
                        date_emission=self.today,
                        numero_serie=f"TRANSCRIPT-{index}",
                    )
                    document.annees.add(self.year)
                else:
                    document = self.create(
                        "releves.Attestation",
                        etudiant=learner,
                        type="inscription",
                        signe_par=self.admin if approved else None,
                        date_emission=self.today,
                        numero=f"ATTESTATION-{index}",
                    )
                records.append(document)
            self.documents[resource] = records


class DocumentAccessTests(DocumentFixture):
    def test_learner_even_with_staff_flag_cannot_guess_other_documents_or_modify_them(self):
        self.learners[0].user.is_staff = True
        self.client.force_authenticate(self.learners[0].user)
        for resource, records in self.documents.items():
            base = f"/api/v1/{resource}/"
            response = self.client.get(base, {"page_size": 1})
            assert response.status_code == 200, response.data
            assert response.data["count"] == 1
            assert response.data["results"][0]["id"] == records[0].pk
            for inaccessible in records[1:]:
                for suffix in ("", "pdf_officiel/", "historique/"):
                    assert self.client.get(f"{base}{inaccessible.pk}/{suffix}").status_code == 404
            assert self.client.patch(f"{base}{records[0].pk}/", {}, format="json").status_code == 403
            assert self.client.post(f"{base}{records[0].pk}/signer/", {}, format="json").status_code == 403

    def test_real_pdf_download_is_private_and_audited_without_inventing_a_digital_signature(self):
        self.client.force_authenticate(self.learners[0].user)
        events = apps.get_model("core.WorkflowEvent")
        for resource, records in self.documents.items():
            response = self.client.get(f"/api/v1/{resource}/{records[0].pk}/pdf_officiel/")
            assert response.status_code == 200
            assert response.content.startswith(b"%PDF-")
            assert len(response.content) > 1000
            assert response["Cache-Control"] == "private, no-store"
            event = events.objects.get(
                action="telechargement", model=records[0]._meta.model_name, object_id=str(records[0].pk)
            )
            assert event.actor_id == self.learners[0].user_id
            assert event.tenant_id == self.tenant.pk
        assert events.objects.filter(action="telechargement").count() == len(self.resources)

    def test_missing_profile_and_revoked_family_access_do_not_expose_documents(self):
        user_model = type(self.admin)
        user = user_model.objects.create_user(
            "documents-no-profile",
            role="eleve" if self.secondary else "etudiant",
            etablissement=self.tenant,
            is_staff=True,
        )
        self.client.force_authenticate(user)
        for resource in self.resources:
            assert self.client.get(f"/api/v1/{resource}/").data["count"] == 0
        if not self.secondary:
            for resource, action in zip(self.resources, ["mes_releves", "mes_transcripts", "mes_attestations"]):
                assert self.client.get(f"/api/v1/{resource}/{action}/").status_code == 403
                self.client.force_authenticate(self.learners[0].user)
                response = self.client.get(f"/api/v1/{resource}/{action}/")
                assert [item["id"] for item in response.data] == [self.documents[resource][0].pk]
                self.client.force_authenticate(user)
            return
        user.role = "parent"
        user.save(update_fields=["role"])
        guardian = self.create(
            "eleves.Tuteur", user=user, etablissement=self.tenant, nom="Parent", prenom="Test", lien_parente="mere"
        )
        link = self.create("eleves.EleveTuteur", eleve=self.learners[0], tuteur=guardian)
        assert self.client.get("/api/v1/bulletins/").data["count"] == 1
        link.autorise_acces_portail = False
        link.save(update_fields=["autorise_acces_portail"])
        assert self.client.get("/api/v1/bulletins/").data["count"] == 0
        assert (
            self.client.get(f"/api/v1/bulletins/{self.documents['bulletins'][0].pk}/pdf_officiel/").status_code == 404
        )

    def test_manager_scopes_are_applied_to_lists_details_and_downloads(self):
        user = type(self.admin).objects.create_user("documents-clerk", role="autre", etablissement=self.tenant)
        self.client.force_authenticate(user)
        for resource, records in self.documents.items():
            model = records[0]._meta
            permission = Permission.objects.get(
                content_type__app_label=model.app_label, codename=f"view_{model.model_name}"
            )
            user.user_permissions.add(permission)
            permission_name = f"{model.app_label}.{permission.codename}"
            scope = "classes" if self.secondary else "etudiants"
            value = self.classe.pk if self.secondary else self.learners[0].pk
            user.attributs_acces = {"permission_scopes": {permission_name: {scope: [value]}}}
            user.save(update_fields=["attributs_acces"])
            user = type(user).objects.get(pk=user.pk)
            self.client.force_authenticate(user)
            response = self.client.get(f"/api/v1/{resource}/")
            assert response.data["count"] == (4 if self.secondary else 2), response.data
            user.attributs_acces["permission_scopes"][permission_name][scope] = []
            user.save(update_fields=["attributs_acces"])
            assert self.client.get(f"/api/v1/{resource}/").data["count"] == 0
            assert self.client.get(f"/api/v1/{resource}/{records[0].pk}/pdf_officiel/").status_code == 404

    def test_inactive_anonymous_and_cross_tenant_accounts_are_rejected(self):
        user = self.learners[0].user
        self.client.force_authenticate(None)
        for resource in self.resources:
            assert self.client.get(f"/api/v1/{resource}/").status_code in (401, 403)
        self.client.force_authenticate(user)
        user.is_active = False
        for resource in self.resources:
            assert self.client.get(f"/api/v1/{resource}/").status_code == 403
        other = type(self.tenant)(schema_name="documents_other")
        self.setup_tenant(other)
        other.auto_create_schema = False
        with schema_context("public"):
            other.save()
        user.is_active = True
        user.etablissement = other
        user.save(update_fields=["etablissement"])
        for resource in self.resources:
            assert self.client.get(f"/api/v1/{resource}/").status_code == 403

    def test_search_does_not_escape_ownership_and_staff_can_inspect_drafts(self):
        self.client.force_authenticate(self.learners[0].user)
        for resource in self.resources:
            response = self.client.get(f"/api/v1/{resource}/", {"search": self.learners[1].matricule})
            assert response.data["count"] == 0
        self.client.force_authenticate(self.admin)
        for resource, records in self.documents.items():
            assert self.client.get(f"/api/v1/{resource}/").data["count"] == 4
            assert self.client.get(f"/api/v1/{resource}/{records[3].pk}/").status_code == 200
        if not self.secondary:
            self.client.force_authenticate(self.learners[0].user)
            response = self.client.get("/api/v1/portail/apprenant/releves/")
            assert [item["id"] for item in response.data] == [self.documents["releves"][0].pk]
