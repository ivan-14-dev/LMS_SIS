"""Research acceptance boundaries exercised against real tenant ORM/API fixtures."""

from concurrent.futures import ThreadPoolExecutor
from datetime import date
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Barrier
from unittest.mock import patch
from uuid import uuid4

import pytest
from apps.core.models import ModuleConfiguration, WorkflowEvent
from apps.enseignants.models import EnseignantChercheur
from apps.etudiants.models import Etudiant
from apps.integration.tests.tenant_test_case import TenantAPITestCase
from apps.recherche.access import CONSULT, CONTRIBUTE, FINANCE, MANAGE
from apps.recherche.files import PrivatePublicationStorage
from apps.recherche.models import (
    Laboratoire,
    ProductionScientifique,
    ProjetRecherche,
    ResearchDelivery,
    These,
)
from apps.structure.models import Faculte
from apps.utilisateurs.models import Utilisateur
from django.contrib.auth.models import Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection, connections
from django.test import TransactionTestCase, override_settings
from django_tenants.utils import schema_context
from rest_framework.test import APIClient

from sis_common.exam_files import PrivateExamStorage

BASE = "/api/v1/recherche/"
PDF = b"%PDF-1.4\nresearch evidence\n%%EOF"


class ResearchAcademicFixture(TenantAPITestCase):
    def setUp(self):
        ModuleConfiguration.objects.update_or_create(
            etablissement=self.tenant, defaults={"enabled": {"sis.research": True}},
        )
        self.manager = self.user("academic-manager", role="enseignant")
        self.grant(self.manager, MANAGE)
        self.member = self.user("academic-member")
        self.grant(self.member, CONSULT, CONTRIBUTE)
        self.reader = self.user("academic-reader")
        self.grant(self.reader, CONSULT)
        self.finance = self.user("academic-finance")
        self.grant(self.finance, FINANCE)
        self.owner = self.teacher(self.manager)
        self.member_teacher = self.teacher(self.member)
        self.reader_teacher = self.teacher(self.reader)
        self.lab = Laboratoire.objects.create(nom="Recherche locale", acronyme="LOCAL")
        self.other_lab = Laboratoire.objects.create(nom="Autre laboratoire", acronyme="AUTRE")
        self.project = self.project_row(self.lab, "Projet autorisé")
        self.other_project = self.project_row(self.other_lab, "Projet distinct")
        self.project.membres.set([self.member_teacher, self.reader_teacher])
        self.url = f"{BASE}projets-recherche/{self.project.pk}/"
        temporary = TemporaryDirectory(prefix="sis-research-academic-test-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.media = self.root / "media"
        self.media.mkdir()
        override = override_settings(MEDIA_ROOT=self.media)
        override.enable()
        self.addCleanup(override.disable)
        for model, storage in (
            (ProductionScientifique, PrivatePublicationStorage(location=self.root / "private")),
            (ResearchDelivery, PrivateExamStorage(location=self.root / "private")),
        ):
            field = model._meta.get_field("fichier")
            self.addCleanup(setattr, field, "storage", field.storage)
            field.storage = storage
        self.login(self.manager)

    def user(self, username, **kwargs):
        return Utilisateur.objects.create_user(username, etablissement=self.tenant, **kwargs)

    def teacher(self, user):
        return EnseignantChercheur.objects.create(user=user, specialite="Recherche")

    def grant(self, user, *permissions):
        for permission in permissions:
            user.user_permissions.add(Permission.objects.get(
                content_type__app_label="recherche", codename=permission.split(".")[1],
            ))

    def login(self, user):
        # Deliberately reuse objects: current authorization must not trust a cached grant.
        self.client.force_authenticate(user)

    def project_row(self, lab, title):
        return ProjetRecherche.objects.create(
            laboratoire=lab, titre=title, description="Informations académiques confidentielles",
            responsable=self.owner, date_debut=date(2020, 1, 1), date_fin=date(2030, 12, 31),
            budget="1000.00",
        )

    def command(self, name, **data):
        self.project.refresh_from_db()
        return self.client.post(
            f"{self.url}{name}/", {"version": self.project.version, **data}, format="json",
        )

    def activate_project(self):
        assert self.command("accepter").status_code == 200
        assert self.command("demarrer").status_code == 200

    def milestone(self):
        response = self.command("jalons", titre="Rapport", description="Preuve", echeance="2028-01-01")
        assert response.status_code == 200, response.data
        return response.data["jalons"][-1]["id"]

    def deliver(self, milestone, content=PDF):
        self.project.refresh_from_db()
        return self.client.post(f"{self.url}livrables/", {
            "version": self.project.version, "jalon": milestone, "commentaire": "Dépôt",
            "fichier": SimpleUploadedFile("rapport.pdf", content, "application/pdf"),
        }, format="multipart")

    def publication(self, project=None):
        project = project or self.project
        response = self.client.post(f"{BASE}productions-scientifiques/", {
            "titre": "Article privé", "type": "article", "laboratoire": project.laboratoire_id,
            "projet": project.pk, "auteurs": [self.owner.pk], "annee": 2026,
            "fichier": SimpleUploadedFile("article.pdf", PDF, "application/pdf"),
        }, format="multipart")
        assert response.status_code == 201, response.data
        return response.data

    def production_command(self, production, command):
        response = self.client.post(
            f"{BASE}productions-scientifiques/{production['id']}/{command}/",
            {"version": production["version"]}, format="json",
        )
        if response.status_code == 200:
            production.update(response.data)
        return response

    def student(self, username):
        user = self.user(username, role="doctorant")
        self.grant(user, CONSULT)
        student = Etudiant.objects.create(
            user=user, universite=self.tenant, matricule=username, date_naissance=date(1995, 1, 1),
            lieu_naissance="Paris", sexe="F", adresse="1 rue", code_postal="75000",
            ville="Paris", telephone="0100000000", statut="inscrit",
        )
        return student

    def thesis(self, student, project=None):
        project = project or self.project
        response = self.client.post(f"{BASE}theses/", {
            "titre": "Thèse", "resume": "Résumé", "laboratoire": project.laboratoire_id,
            "projet": project.pk, "doctorant": student.pk, "directeur": self.owner.pk,
            "date_debut": "2022-01-01",
        }, format="json")
        assert response.status_code == 201, response.data
        return response.data

    def foreign_tenant(self):
        tenant = type(self.tenant)(schema_name=f"research_foreign_{uuid4().hex[:12]}")
        self.setup_tenant(tenant)
        tenant.auto_create_schema = False
        with schema_context("public"):
            tenant.save()
        return tenant


class ResearchAcademicTestCase(ResearchAcademicFixture):
    def test_module_off_and_permission_revocation_apply_to_reused_accounts(self):
        assert self.client.get(self.url).status_code == 200
        self.manager.user_permissions.clear()
        assert self.client.get(self.url).status_code == 404
        self.grant(self.manager, MANAGE)
        assert self.client.get(self.url).status_code == 200
        ModuleConfiguration.objects.filter(etablissement=self.tenant).update(enabled={"sis.research": False})
        assert self.client.get(self.url).status_code == 403
        ModuleConfiguration.objects.filter(etablissement=self.tenant).update(enabled={"sis.research": True})
        Utilisateur.objects.filter(pk=self.manager.pk).update(is_active=False)
        assert self.client.get(self.url).status_code == 403

    def test_role_staff_and_unowned_superuser_never_grant_research(self):
        for user in (
            self.user("role-only", role="recherche"),
            self.user("staff-only", is_staff=True),
            Utilisateur.objects.create_superuser("global-superuser"),
        ):
            self.login(user)
            response = self.client.get(self.url)
            assert response.status_code in (403, 404)
        local_superuser = self.user("local-superuser", is_superuser=True)
        self.login(local_superuser)
        assert self.client.get(self.url).status_code == 200

    def test_strict_scope_shapes_fail_closed_on_reads_writes_and_selectors(self):
        bad = [
            [], None, "", {"unknown": [self.project.pk]}, {"projet_id": []},
            {"projet_id": [True]}, {"projet_id": ["1"]}, {"projet_id": [1.0]},
            {"projet_id": [-1]}, {"projet_id": [0]}, {"projet_id": {}},
        ]
        for constraints in bad:
            with self.subTest(constraints=constraints):
                Utilisateur.objects.filter(pk=self.manager.pk).update(
                    attributs_acces={"permission_scopes": {MANAGE: constraints}},
                )
                assert self.client.get(self.url).status_code == 404
                assert self.client.get(f"{BASE}laboratoires/selecteurs/?type=enseignants").status_code == 403
                assert self.command("accepter").status_code == 404
        for attributes in ([], {"permission_scopes": []}, {"permission_scopes": None}):
            Utilisateur.objects.filter(pk=self.manager.pk).update(attributs_acces=attributes)
            assert self.client.get(self.url).status_code == 404

    def test_project_scope_filters_nested_collections_statistics_and_selectors(self):
        self.project.membres.add(self.member_teacher)
        Utilisateur.objects.filter(pk=self.manager.pk).update(
            attributs_acces={"permission_scopes": {MANAGE: {"projet_id": [self.project.pk]}}},
        )
        projects = self.client.get(f"{BASE}projets-recherche/")
        assert [row["id"] for row in projects.data["results"]] == [self.project.pk]
        lab_url = f"{BASE}laboratoires/{self.lab.pk}/"
        assert self.client.get(f"{lab_url}statistiques/").data["nb_projets"] == 1
        assert len(self.client.get(f"{lab_url}projets/").data["results"]) == 1
        assert self.client.get(f"{BASE}laboratoires/{self.other_lab.pk}/").status_code == 404
        unrelated = self.teacher(self.user("unrelated-selector"))
        selected = self.client.get(f"{BASE}laboratoires/selecteurs/?type=enseignants").data["results"]
        assert unrelated.pk not in [row["id"] for row in selected]
        assert self.client.patch(self.url, {"version": 1, "membres": [unrelated.pk]}, format="json").status_code == 400
        capabilities = self.client.get(f"{BASE}projets-recherche/capacites/").data
        assert not capabilities["can_create_projet"]
        assert not capabilities["can_create_laboratoire"]
        assert capabilities["can_manage"]

    def test_people_selectors_search_full_display_names_and_existing_identifiers(self):
        student = self.student("selector-doctorant")
        student.matricule = "MAT-SELECTOR-001"
        student.save(update_fields=["matricule"])
        for kind, profile, last_name in (
            ("enseignants", self.owner, "Synthetic manager"),
            ("etudiants", student, "Synthetic doctorant"),
        ):
            user = profile.user
            user.first_name, user.last_name = "W39 a", last_name
            user.save(update_fields=["first_name", "last_name"])
            terms = [
                user.get_full_name(), f"  {user.get_full_name().lower()}  ",
                "a Synthetic", "W39", last_name, user.username,
            ]
            if kind == "etudiants":
                terms.append("SELECTOR-001")
            for term in terms:
                with self.subTest(kind=kind, term=term):
                    response = self.client.get(f"{BASE}laboratoires/selecteurs/", {"type": kind, "q": term})
                    assert response.status_code == 200, response.data
                    assert response.data["results"] == [{"id": profile.pk, "nom": user.get_full_name()}]

    def test_people_selectors_search_username_when_display_names_are_blank(self):
        student = self.student("fallback-doctorant")
        student.matricule = "MAT-FALLBACK-001"
        student.save(update_fields=["matricule"])
        for kind, profile, term in (
            ("enseignants", self.owner, "academic-man"),
            ("etudiants", student, "fallback-doc"),
        ):
            with self.subTest(kind=kind):
                response = self.client.get(f"{BASE}laboratoires/selecteurs/", {"type": kind, "q": term})
                assert response.status_code == 200, response.data
                assert response.data["results"] == [{"id": profile.pk, "nom": profile.user.username}]

    def test_people_full_name_search_preserves_tenant_and_project_scope(self):
        allowed_student = self.student("allowed-selector")
        outside_student = self.student("outside-selector")
        self.thesis(allowed_student)
        self.thesis(outside_student, self.other_project)
        outside_teacher = self.teacher(self.user("outside-teacher"))
        self.other_project.membres.add(outside_teacher)
        foreign = self.foreign_tenant()
        foreign_teacher = self.teacher(Utilisateur.objects.create_user("foreign-selector", etablissement=foreign))
        foreign_student = self.student("foreign-student-selector")
        foreign_student.universite = foreign
        foreign_student.save(update_fields=["universite"])
        Utilisateur.objects.filter(pk=foreign_student.user_id).update(etablissement=foreign)
        profiles = (
            self.member_teacher, outside_teacher, foreign_teacher, allowed_student, outside_student, foreign_student,
        )
        Utilisateur.objects.filter(pk__in=[profile.user_id for profile in profiles]).update(
            first_name="Scoped", last_name="Full name",
        )
        for scope in (None, {"projet_id": [self.project.pk]}):
            if scope is not None:
                Utilisateur.objects.filter(pk=self.manager.pk).update(
                    attributs_acces={"permission_scopes": {MANAGE: scope}},
                )
            for kind, allowed, outside in (
                ("enseignants", self.member_teacher, outside_teacher),
                ("etudiants", allowed_student, outside_student),
            ):
                with self.subTest(kind=kind, scope=scope):
                    response = self.client.get(
                        f"{BASE}laboratoires/selecteurs/", {"type": kind, "q": "Scoped Full name"},
                    )
                    assert response.status_code == 200, response.data
                    expected = {allowed.pk, outside.pk} if scope is None else {allowed.pk}
                    assert {row["id"] for row in response.data["results"]} == expected

    def test_current_membership_and_consult_are_required_and_revocable(self):
        self.login(self.reader)
        assert self.client.get(self.url).status_code == 200
        assert self.command("accepter").status_code == 403
        self.project.membres.remove(self.reader_teacher)
        assert self.client.get(self.url).status_code == 404
        self.project.membres.add(self.reader_teacher)
        self.reader.user_permissions.clear()
        assert self.client.get(self.url).status_code == 404

    def test_finance_metadata_does_not_expose_or_search_private_academic_data(self):
        self.publication()
        self.login(self.finance)
        response = self.client.get(self.url)
        assert response.status_code == 200
        assert response.data["can_finance"]
        assert not response.data["can_read_academic"]
        for key in ("description", "membres", "membres_list", "responsable", "jalons", "productions", "theses"):
            assert key not in response.data
        assert self.client.get(f"{self.url}jalons/").status_code == 403
        assert self.client.get(f"{BASE}projets-recherche/?search=confidentielles").data["count"] == 0
        assert self.client.get(f"{BASE}productions-scientifiques/").data["count"] == 0
        assert self.client.get(f"{BASE}laboratoires/{self.lab.pk}/statistiques/").data["nb_publications"] == 0

    def test_commands_require_version_and_reject_direct_state_write_delete_put(self):
        for path in (f"{BASE}laboratoires/", f"{self.url}accepter/"):
            response = self.client.post(path, ["not-an-object"], format="json")
            assert response.status_code == 400, response.data
            assert "non_field_errors" in response.data
        for version in (None, True, 1.0, "01", -1):
            payload = {} if version is None else {"version": version}
            response = self.client.post(f"{self.url}accepter/", payload, format="json")
            assert response.status_code == 400, response.data
        assert self.command("accepter").status_code == 200
        stale = self.client.patch(self.url, {"version": 1, "titre": "Perdu"}, format="json")
        assert stale.status_code == 409
        for field, value in (("statut", "termine"), ("archive", True)):
            assert self.client.patch(self.url, {"version": 2, field: value}, format="json").status_code == 400
        assert self.client.delete(self.url).status_code == 405
        assert self.client.put(self.url, {}, format="json").status_code == 405
        self.project.refresh_from_db()
        assert self.project.version == 2

    def test_project_lifecycle_milestone_acceptance_and_archive_are_guarded(self):
        assert self.command("demarrer").status_code == 400
        assert self.command("terminer").status_code == 400
        self.activate_project()
        milestone = self.milestone()
        assert self.command("terminer").status_code == 400
        assert self.command("valider-jalon", jalon=milestone).status_code == 400
        assert self.deliver(milestone).status_code == 200
        assert self.command("valider-jalon", jalon=milestone).status_code == 200
        assert self.command("valider-jalon", jalon=milestone).status_code == 400
        assert self.deliver(milestone).status_code == 400
        assert self.command("suspendre").status_code == 200
        assert self.command("terminer").status_code == 400
        assert self.command("reprendre").status_code == 200
        assert self.command("terminer").status_code == 200
        assert self.command("archiver").status_code == 200
        self.project.refresh_from_db()
        assert self.client.patch(self.url, {"version": self.project.version, "titre": "Archivé"}, format="json").status_code == 400
        lab = self.client.post(f"{BASE}laboratoires/{self.lab.pk}/archiver/", {"version": 1}, format="json")
        assert lab.status_code == 200, lab.data

    def test_lab_archive_and_milestone_dates_cannot_be_bypassed(self):
        response = self.client.post(f"{BASE}laboratoires/{self.lab.pk}/archiver/", {"version": 1}, format="json")
        assert response.status_code == 400
        response = self.command("jalons", titre="Hors période", echeance="2040-01-01")
        assert response.status_code == 400
        assert not self.project.jalons.exists()
        self.milestone()
        self.project.refresh_from_db()
        response = self.client.patch(
            self.url, {"version": self.project.version, "date_fin": "2027-01-01"}, format="json",
        )
        assert response.status_code == 400

    def test_deliveries_are_private_numbered_immutable_and_recheck_membership(self):
        self.activate_project()
        milestone = self.milestone()
        self.login(self.reader)
        assert self.deliver(milestone).status_code == 403
        self.login(self.member)
        assert self.deliver(milestone).status_code == 200
        assert self.deliver(milestone, PDF + b"\nsecond").status_code == 200
        rows = list(ResearchDelivery.objects.filter(jalon_id=milestone).order_by("revision"))
        assert [row.revision for row in rows] == [1, 2]
        assert rows[0].sha256 == sha256(PDF).hexdigest()
        url = f"{self.url}livrables/{rows[0].pk}/fichier/"
        response = self.client.get(url)
        assert response.status_code == 200
        assert b"".join(response.streaming_content) == PDF
        assert response["Cache-Control"] == "private, no-store"
        assert self.client.patch(url, {}, format="json").status_code == 405
        self.project.membres.remove(self.member_teacher)
        assert self.client.get(url).status_code == 404
        assert self.client.get(f"{BASE}projets-recherche/{self.other_project.pk}/livrables/{rows[0].pk}/fichier/").status_code == 404
        assert Path(rows[0].fichier.path).read_bytes() == PDF

    def test_invalid_upload_and_failed_audit_leave_no_delivery_or_file(self):
        self.activate_project()
        milestone = self.milestone()
        self.project.refresh_from_db()
        version = self.project.version
        count = WorkflowEvent.objects.filter(app_label="recherche").count()
        assert self.deliver(milestone, b"not a PDF").status_code == 400
        with patch("apps.recherche.api.audit", side_effect=RuntimeError("audit failure")):
            with pytest.raises(RuntimeError):
                self.deliver(milestone)
        assert not ResearchDelivery.objects.exists()
        assert not list((self.root / "private").rglob("*.pdf"))
        self.project.refresh_from_db()
        assert self.project.version == version
        assert WorkflowEvent.objects.filter(app_label="recherche").count() == count
        assert self.project.jalons.get(pk=milestone).statut == "a_faire"

    def test_publication_is_draft_until_validated_published_and_authorized(self):
        publication = self.publication()
        url = f"{BASE}productions-scientifiques/{publication['id']}/"
        assert publication["statut"] == "brouillon"
        assert publication["fichier"] == f"{url}fichier/"
        assert "recherche/" not in publication["fichier"].removeprefix("/api/v1/recherche/")
        self.login(self.reader)
        assert self.client.get(url).status_code == 404
        assert self.client.get(f"{url}fichier/").status_code == 404
        self.login(self.manager)
        assert self.production_command(publication, "publier").status_code == 400
        assert self.production_command(publication, "valider").status_code == 200
        assert self.client.patch(url, {"version": publication["version"], "titre": "Écrasé"}, format="json").status_code == 400
        assert self.production_command(publication, "publier").status_code == 200
        self.login(self.reader)
        download = self.client.get(f"{url}fichier/")
        assert download.status_code == 200
        assert b"".join(download.streaming_content) == PDF
        assert download["Cache-Control"] == "private, no-store"
        self.reader.user_permissions.clear()
        assert self.client.get(f"{url}fichier/").status_code == 404
        self.login(self.manager)
        assert self.production_command(publication, "archiver").status_code == 200
        assert publication["archive"]

    def test_publication_file_replacement_preserves_old_file_and_cleans_failed_new_file(self):
        publication = self.publication()
        obj = ProductionScientifique.objects.get(pk=publication["id"])
        old_name, old_path = obj.fichier.name, Path(obj.fichier.path)
        assert old_path.read_bytes() == PDF
        url = f"{BASE}productions-scientifiques/{obj.pk}/"
        with patch("apps.recherche.api.audit", side_effect=RuntimeError("audit failure")):
            with pytest.raises(RuntimeError):
                self.client.patch(url, {
                    "version": publication["version"],
                    "fichier": SimpleUploadedFile("replacement.pdf", PDF + b"\nnew", "application/pdf"),
                }, format="multipart")
        obj.refresh_from_db()
        assert obj.fichier.name == old_name
        assert list((self.root / "private").rglob("*.pdf")) == [old_path]
        response = self.client.patch(url, {
            "version": publication["version"],
            "fichier": SimpleUploadedFile("replacement.pdf", PDF + b"\nnew", "application/pdf"),
        }, format="multipart")
        assert response.status_code == 200, response.data
        assert old_path.read_bytes() == PDF
        obj.refresh_from_db()
        assert obj.fichier.name != old_name

    def test_exact_legacy_publications_fallback_preserves_name_bytes_and_denies_aliases(self):
        legacy = self.media / "publications" / "historique.pdf"
        legacy.parent.mkdir()
        legacy.write_bytes(PDF)
        publication = ProductionScientifique.objects.create(
            laboratoire=self.lab, projet=self.project, type="article", titre="Historique", annee=2020,
            fichier="publications/historique.pdf",
        )
        publication.auteurs.set([self.owner])
        url = f"{BASE}productions-scientifiques/{publication.pk}/fichier/"
        response = self.client.get(url)
        assert response.status_code == 200
        assert b"".join(response.streaming_content) == PDF
        publication.refresh_from_db()
        assert publication.fichier.name == "publications/historique.pdf"
        assert publication.statut == "brouillon"
        for name in (
            "publications/../secret.pdf", "publications//historique.pdf",
            "publications/./historique.pdf", "/publications/historique.pdf",
            "publications\\historique.pdf", "elsewhere/secret.pdf",
            "recherche/foreign_schema/publications/secret.pdf",
        ):
            ProductionScientifique.objects.filter(pk=publication.pk).update(fichier=name)
            assert self.client.get(url).status_code == 404, name
        private_file = self.media / "private.pdf"
        private_file.write_bytes(PDF + b"\nnot a publication")
        (legacy.parent / "alias.pdf").symlink_to(private_file)
        ProductionScientifique.objects.filter(pk=publication.pk).update(fichier="publications/alias.pdf")
        assert self.client.get(url).status_code == 404
        assert legacy.read_bytes() == PDF

    @override_settings(DEBUG=True)
    def test_legacy_publication_is_not_served_by_the_debug_media_fallback(self):
        legacy = self.media / "publications" / "historique.pdf"
        legacy.parent.mkdir()
        legacy.write_bytes(PDF)
        anonymous = APIClient(SERVER_NAME=self.get_test_tenant_domain())
        response = anonymous.get("/media/publications/historique.pdf", secure=True)
        assert response.status_code in (403, 404)

    def test_foreign_relations_in_local_schema_are_rejected_and_not_readable(self):
        foreign = self.foreign_tenant()
        user = Utilisateur.objects.create_user("foreign-author", etablissement=foreign)
        teacher = self.teacher(user)
        faculty = Faculte.objects.create(universite=foreign, nom="Foreign", code="FOREIGN")
        response = self.client.patch(
            f"{BASE}laboratoires/{self.lab.pk}/", {"version": 1, "faculte": faculty.pk}, format="json",
        )
        assert response.status_code == 400
        assert self.client.patch(self.url, {"version": 1, "membres": [teacher.pk]}, format="json").status_code == 400
        publication = self.publication()
        obj = ProductionScientifique.objects.get(pk=publication["id"])
        obj.auteurs.add(teacher)
        assert self.client.get(publication["fichier"]).status_code == 404
        self.project.membres.add(teacher)
        assert self.client.get(self.url).status_code == 404
        self.login(user)
        assert self.client.get(f"{BASE}laboratoires/").status_code == 403

    def test_project_lab_and_non_member_authors_are_rejected(self):
        unrelated = self.teacher(self.user("non-project-author"))
        payload = {
            "titre": "Interdit", "type": "article", "laboratoire": self.lab.pk,
            "projet": self.project.pk, "auteurs": [unrelated.pk], "annee": 2026,
        }
        assert self.client.post(f"{BASE}productions-scientifiques/", payload, format="json").status_code == 400
        payload.update(auteurs=[self.owner.pk], laboratoire=self.other_lab.pk)
        assert self.client.post(f"{BASE}productions-scientifiques/", payload, format="json").status_code == 400
        assert not ProductionScientifique.objects.exists()

    def test_student_reads_only_own_active_thesis_and_project_membership_is_revocable(self):
        alice, bob = self.student("doctoral-alice"), self.student("doctoral-bob")
        own, other = self.thesis(alice), self.thesis(bob)
        self.login(alice.user)
        response = self.client.get(self.url)
        assert response.status_code == 200, response.data
        assert [row["id"] for row in response.data["theses"]] == [own["id"]]
        assert self.client.get(f"{BASE}theses/{other['id']}/").status_code == 404
        assert self.command("accepter").status_code == 403
        assert self.client.get(f"{BASE}theses/").data["count"] == 1
        assert self.client.get(f"{BASE}laboratoires/{self.lab.pk}/statistiques/").data["nb_theses"] == 1
        These.objects.filter(pk=own["id"]).update(statut="suspendue")
        assert self.client.get(self.url).status_code == 404
        assert self.client.get(f"{BASE}theses/{own['id']}/").status_code == 404

    def test_thesis_lifecycle_dates_supervisors_and_legacy_preservation(self):
        student = self.student("doctoral-lifecycle")
        thesis = self.thesis(student)
        url = f"{BASE}theses/{thesis['id']}/"
        response = self.client.patch(
            url, {"version": 1, "co_directeur": self.owner.pk}, format="json",
        )
        assert response.status_code == 400
        response = self.client.post(
            f"{url}soutenir/", {"version": 1, "date_soutenance": "2040-01-01"}, format="json",
        )
        assert response.status_code == 400
        assert self.client.post(f"{url}archiver/", {"version": 1}, format="json").status_code == 400
        response = self.client.post(
            f"{url}soutenir/", {"version": 1, "date_soutenance": "2023-01-01"}, format="json",
        )
        assert response.status_code == 200, response.data
        assert response.data["statut"] == "soutenue"
        assert self.client.post(f"{url}reprendre/", {"version": 2}, format="json").status_code == 400
        assert self.client.post(f"{url}archiver/", {"version": 2}, format="json").status_code == 200
        legacy_student = self.student("doctoral-legacy")
        legacy = These.objects.create(
            laboratoire=self.lab, doctorant=legacy_student, directeur=self.owner,
            titre="Ancien dossier", resume="Conservé", date_debut=date(2020, 1, 1),
        )
        assert self.client.get(f"{BASE}theses/{legacy.pk}/").status_code == 200
        self.login(legacy_student.user)
        assert self.client.get(f"{BASE}theses/{legacy.pk}/").status_code == 404
        legacy.refresh_from_db()
        assert legacy.projet_id is None

    def test_command_audit_is_transactional_and_contains_fresh_version(self):
        response = self.command("accepter")
        assert response.status_code == 200
        event = WorkflowEvent.objects.get(
            app_label="recherche", model="projetrecherche", object_id=str(self.project.pk),
            action="recherche_accepter",
        )
        assert event.metadata["version"] == response.data["version"]
        with patch("apps.recherche.api.audit", side_effect=RuntimeError("audit failure")):
            with pytest.raises(RuntimeError):
                self.command("demarrer")
        self.project.refresh_from_db()
        assert self.project.statut == "accepte"
        assert self.project.version == 2


class ResearchAcademicConcurrencyTests(ResearchAcademicFixture):
    @classmethod
    def _fixture_setup(cls):
        TransactionTestCase._fixture_setup.__func__(cls)

    def _fixture_teardown(self):
        with schema_context(self.tenant.schema_name):
            TransactionTestCase._fixture_teardown(self)

    def test_delivery_and_metadata_serialize_on_the_project_version(self):
        assert not connection.in_atomic_block
        self.activate_project()
        milestone = self.milestone()
        self.project.refresh_from_db()
        version = self.project.version
        events = WorkflowEvent.objects.filter(app_label="recherche").count()
        barrier = Barrier(2)

        def mutate(kind):
            try:
                with schema_context(self.tenant.schema_name):
                    actor = Utilisateur.objects.get(pk=self.manager.pk)
                    client = APIClient(SERVER_NAME=self.get_test_tenant_domain())
                    client.force_authenticate(actor)
                    barrier.wait(timeout=15)
                    if kind == "delivery":
                        response = client.post(f"{self.url}livrables/", {
                            "version": version, "jalon": milestone,
                            "fichier": SimpleUploadedFile("race.pdf", PDF, "application/pdf"),
                        }, format="multipart")
                    else:
                        response = client.patch(
                            self.url, {"version": version, "titre": "Modification concurrente"}, format="json",
                        )
                    return response.status_code
            finally:
                connections["default"].close()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(mutate, ("delivery", "metadata")))
        assert sorted(results) == [200, 409]
        self.project.refresh_from_db()
        assert self.project.version == version + 1
        assert WorkflowEvent.objects.filter(app_label="recherche").count() == events + 1
        assert ResearchDelivery.objects.count() == (1 if results[0] == 200 else 0)
        assert len(list((self.root / "private").rglob("*.pdf"))) == ResearchDelivery.objects.count()
