"""Document search must keep the authoritative official-document visibility."""

import uuid

from apps.etablissement.models import AnneeUniversitaire, Semestre, Universite
from apps.etudiants.models import Etudiant
from apps.integration.tests.tenant_test_case import TenantAPITestCase
from apps.releves.models import Attestation, ReleveNotes, Transcript
from apps.utilisateurs.models import Utilisateur
from django.contrib.auth.models import Permission
from django_tenants.utils import schema_context


class AcademicDocumentSearchAPITests(TenantAPITestCase):
    url = "/api/v1/core/recherche-academique/"
    resources = {
        "releves": (ReleveNotes, "numero_serie", "Relevé", "/api/v1/releves/"),
        "transcripts": (Transcript, "numero_serie", "Transcript", "/api/v1/releves/transcripts/"),
        "attestations": (Attestation, "numero", "Attestation", "/api/v1/releves/attestations/"),
    }

    def setUp(self):
        self.other = Universite(schema_name=f"doc_search_{uuid.uuid4().hex[:12]}")
        self.setup_tenant(self.other)
        self.other.auto_create_schema = False
        with schema_context("public"):
            self.other.save()
        self.owner = self._learner("owner", self.tenant)
        self.peer = self._learner("peer", self.tenant)
        foreign = self._learner("foreign", self.other)
        self.foreign_user = foreign.user
        self.manager = Utilisateur.objects.create_user(
            "doc-search-manager", role="autre", is_staff=True, etablissement=self.tenant
        )
        self.signer = Utilisateur.objects.create_user(
            "doc-search-signer", role="scolarite", etablissement=self.tenant
        )
        self.year = AnneeUniversitaire.objects.create(
            universite=self.tenant, libelle="2025-2026", date_debut="2025-09-01", date_fin="2026-06-30"
        )
        self.periods = [
            Semestre.objects.create(
                annee_universitaire=self.year, numero=number, type="impair" if number == 1 else "pair",
                date_debut="2025-09-01", date_fin="2026-06-30",
            )
            for number in (1, 2)
        ]
        self.documents = {}
        for resource, (model, number_field, _, _) in self.resources.items():
            documents = []
            for index, learner in enumerate((self.owner, self.peer, self.owner, foreign)):
                approved = index != 2
                values = {
                    "etudiant": learner,
                    number_field: f"DOC-{resource}-{index}",
                    "date_emission": "2026-01-15",
                    "pdf_path": "private/never-expose.pdf",
                    "signe_par": self.signer if approved else None,
                }
                if resource == "releves":
                    values.update(signe=approved, semestre=self.periods[1 if index == 2 else 0], moyenne_generale=15)
                elif resource == "transcripts":
                    values.update(credits_total=60, credits_valides=30, diplome_prepare="Private degree")
                else:
                    values["type"] = "inscription"
                document = model.objects.create(**values)
                if resource == "transcripts":
                    document.annees.add(self.year)
                documents.append(document)
            self.documents[resource] = documents

    def _learner(self, name, tenant):
        user = Utilisateur.objects.create_user(
            f"doc-search-{name}", role="etudiant", etablissement=tenant, is_staff=True,
            first_name="PrivateFirstName", last_name="PrivateLastName",
        )
        return Etudiant.objects.create(
            universite=tenant, user=user, matricule=f"PRIVATE-{name}", date_naissance="2003-01-01",
            lieu_naissance="Paris", sexe="F", adresse="Private address", code_postal="75000", ville="Paris",
            telephone="0100000000",
        )

    def _grant_documents(self, user):
        user.user_permissions.add(*[
            Permission.objects.get(content_type__app_label="releves", codename=f"view_{model._meta.model_name}")
            for model, _, _, _ in self.resources.values()
        ])
        return Utilisateur.objects.get(pk=user.pk)

    def _assert_results(self, resource, expected):
        _, number_field, label, source_url = self.resources[resource]
        result = self.client.get(self.url, {"ressource": resource, "q": "doc-", "page_size": "50"})
        source = self.client.get(source_url, {"search": "DOC-", "page_size": "50"})
        assert result.status_code == source.status_code == 200
        assert result.data["count"] == source.data["count"] == len(expected)
        assert result.data["results"] == [
            {"id": item.pk, "code": getattr(item, number_field), "nom": f"{label} {getattr(item, number_field)}"}
            for item in expected
        ]
        assert {item["id"] for item in source.data["results"]} == {item.pk for item in expected}
        body = str(result.data)
        for document in self.documents[resource]:
            if document not in expected:
                assert getattr(document, number_field) not in body
        for private_value in ("PrivateFirstName", "PrivateLastName", "PRIVATE-", "private/", "Private degree"):
            assert private_value not in body
        return result

    def test_owner_only_finds_approved_documents_without_private_metadata(self):
        self.client.force_authenticate(self.owner.user)
        for resource, documents in self.documents.items():
            self._assert_results(resource, documents[:1])
            result = self.client.get(self.url, {"ressource": resource, "q": "PrivateLastName"})
            assert result.data["count"] == 0

    def test_approval_withdrawal_removes_identifiers_on_the_next_request(self):
        self.client.force_authenticate(self.owner.user)
        for resource, documents in self.documents.items():
            self._assert_results(resource, documents[:1])
            document = documents[0]
            if resource == "releves":
                document.signe = False
                document.save(update_fields=["signe"])
            else:
                document.signe_par = None
                document.save(update_fields=["signe_par"])
            self._assert_results(resource, [])

    def test_staff_flag_is_not_access_and_model_grants_respect_scope_and_revocation(self):
        self.client.force_authenticate(self.manager)
        for resource in self.resources:
            self._assert_results(resource, [])
        self.manager = self._grant_documents(self.manager)
        self.client.force_authenticate(self.manager)
        for resource, documents in self.documents.items():
            self._assert_results(resource, documents[:3])
        self.manager.attributs_acces = {
            "permission_scopes": {
                f"releves.view_{model._meta.model_name}": {"etudiants": [self.owner.pk]}
                for model, _, _, _ in self.resources.values()
            }
        }
        self.manager.save(update_fields=["attributs_acces"])
        for resource, documents in self.documents.items():
            self._assert_results(resource, [documents[0], documents[2]])
        self.manager.user_permissions.clear()
        self.manager = Utilisateur.objects.get(pk=self.manager.pk)
        self.client.force_authenticate(self.manager)
        for resource in self.resources:
            self._assert_results(resource, [])

    def test_parent_role_and_missing_learner_profile_cannot_use_retained_model_grants(self):
        self.manager = self._grant_documents(self.manager)
        self.client.force_authenticate(self.manager)
        for role in ("parent", "etudiant"):
            self.manager.role = role
            self.manager.save(update_fields=["role"])
            for resource in self.resources:
                self._assert_results(resource, [])

    def test_empty_and_unknown_scopes_deny_documents_without_disclosing_serials(self):
        self.manager = self._grant_documents(self.manager)
        self.client.force_authenticate(self.manager)
        for scope in ({"etudiants": []}, {"unknown": [self.owner.pk]}):
            self.manager.attributs_acces = {
                "permission_scopes": {
                    f"releves.view_{model._meta.model_name}": scope
                    for model, _, _, _ in self.resources.values()
                }
            }
            self.manager.save(update_fields=["attributs_acces"])
            for resource in self.resources:
                self._assert_results(resource, [])

    def test_foreign_inactive_and_anonymous_accounts_are_rejected(self):
        self.foreign_user.is_superuser = True
        self.foreign_user.save(update_fields=["is_superuser"])
        self.manager.is_active = False
        self.manager.save(update_fields=["is_active"])
        for user in (self.foreign_user, self.manager, None):
            self.client.force_authenticate(user)
            for resource in self.resources:
                result = self.client.get(self.url, {"ressource": resource, "q": "DOC-"})
                assert result.status_code in (401, 403)
                assert "DOC-" not in str(result.data)

    def test_document_types_keep_query_validation_and_bounded_pagination(self):
        self.client.force_authenticate(self.owner.user)
        for resource in self.resources:
            for term in ("", " ", "a", "x" * 101, "DOC-\n", "DOC-\x7f", " " * 99 + "ab"):
                assert self.client.get(self.url, {"ressource": resource, "q": term}).status_code == 400
            result = self.client.get(self.url, {"ressource": resource, "q": "  DoC-  "})
            assert result.status_code == 200
            assert result.data["count"] == 1
        Attestation.objects.bulk_create([
            Attestation(
                etudiant=self.owner, type="inscription", numero=f"DOC-EXTRA-{index:02}",
                date_emission="2026-01-15", signe_par=self.signer,
            )
            for index in range(50)
        ])
        params = {"ressource": "attestations", "q": "DOC-"}
        default = self.client.get(self.url, params)
        first = self.client.get(self.url, {**params, "page_size": "999"})
        second = self.client.get(self.url, {**params, "page_size": "999", "page": "2"})
        assert default.status_code == first.status_code == second.status_code == 200
        assert default.data["count"] == first.data["count"] == second.data["count"] == 51
        assert len(default.data["results"]) == 20
        assert len(first.data["results"]) == 50
        assert len(second.data["results"]) == 1
        assert not {item["id"] for item in first.data["results"]} & {
            item["id"] for item in second.data["results"]
        }

    def test_transcript_year_scope_does_not_duplicate_search_results(self):
        other_year = AnneeUniversitaire.objects.create(
            universite=self.tenant, libelle="2024-2025", date_debut="2024-09-01", date_fin="2025-06-30"
        )
        self.documents["transcripts"][0].annees.add(other_year)
        self.manager = self._grant_documents(self.manager)
        self.manager.attributs_acces = {
            "permission_scopes": {
                "releves.view_transcript": {
                    "etudiants": [self.owner.pk], "annees": [self.year.pk, other_year.pk],
                }
            }
        }
        self.manager.save(update_fields=["attributs_acces"])
        self.client.force_authenticate(self.manager)
        documents = self.documents["transcripts"]
        self._assert_results("transcripts", [documents[0], documents[2]])
