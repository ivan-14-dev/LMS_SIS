from copy import deepcopy
from unittest.mock import patch

import pytest
from django.apps import apps
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.utils import timezone
from django_tenants.utils import schema_context

from sis_common.hierarchy import OFFERING_SETTING, resolve_configuration, unit_path
from sis_common.tests import test_hierarchy as hierarchy_tests
from sis_common.tests.test_grade_entry import GradeEntryFixture
from sis_common.tests.test_institutional_profiles import offering

UNITS = hierarchy_tests.UNITS


class OrganizationTests(GradeEntryFixture):
    publication_payload = hierarchy_tests.HierarchicalConfigurationTests.publication_payload
    publish = hierarchy_tests.HierarchicalConfigurationTests.publish
    create_parent = hierarchy_tests.HierarchicalConfigurationTests.create_parent

    def unit(self, code, kind="company", parent=None, **extra):
        data = {
            "code": code, "nom": code, "kind": kind, "topology_version": 2,
            "parent": parent.pk if parent else None, **extra,
        }
        response = self.client.post(UNITS, data, format="json")
        assert response.status_code == 201, response.data
        return apps.get_model("core.OrganizationUnit").objects.get(pk=response.data["id"])

    def attach(self, unit, target_kind, item, **extra):
        return self.client.post(
            f"{UNITS}{unit.pk}/attachments/",
            {"kind": target_kind, "object_id": item.pk, "confirm": True, **extra}, format="json",
        )

    def listing(self, unit, kind, **params):
        return self.client.get(f"{UNITS}{unit.pk}/attachments/", {"kind": kind, **params})

    def detail(self, unit, kind, item):
        return self.client.get(
            f"{UNITS}{unit.pk}/attached-object/", {"kind": kind, "object_id": item.pk},
        )

    def activity(self):
        if self.secondary:
            return self.create(
                "emplois_du_temps.Creneau", classe=self.classe, matiere=self.subject,
                enseignant=self.author, jour=1, heure_debut="09:00", heure_fin="10:00",
            )
        slot = self.create("emplois_du_temps.CreneauHoraire", heure_debut="09:00", heure_fin="10:00")
        return self.create(
            "emplois_du_temps.CreneauCours", formation=self.formation, semestre=self.period,
            ecue=self.subject, jour=1, creneau_horaire=slot,
        )

    def foreign(self):
        tenant = type(self.tenant)(schema_name="organization_foreign")
        self.setup_tenant(tenant)
        tenant.auto_create_schema = False
        with schema_context("public"):
            tenant.save()
        return tenant

    def test_university_and_company_topologies_are_free_but_legacy_contract_is_preserved(self):
        previous = None
        for kind in ("university", "faculty", "school", "department", "track", "level", "class", "group", "teaching_unit"):
            previous = self.unit(f"uni-{kind}", kind, previous)
        assert len(unit_path(self.tenant, previous)) == 9
        university = apps.get_model("core.OrganizationUnit").objects.get(code="uni-university")
        independent_school = self.unit("school-direct", "school", university)
        assert len(unit_path(self.tenant, independent_school)) == 2
        company = self.unit("company")
        previous = company
        for kind in ("directorate", "service", "department", "team", "program"):
            previous = self.unit(f"company-{kind}", kind, previous)
        self.unit("another-service", "service", previous)
        custom = self.unit("cell", "custom", previous, category_label="Cellule qualité")
        assert custom.category_label == "Cellule qualité"
        self.publish(offering("vocational"), company, locks=[OFFERING_SETTING])
        assert resolve_configuration(self.tenant, custom)["locks"][OFFERING_SETTING]["unit"] == company.pk
        legacy = self.unit("old-campus", "campus", topology_version=1)
        old_program = self.unit("old-program", "program", legacy, topology_version=1)
        self.unit("new-service", "service", old_program)
        payload = {"code": "invalid", "nom": "Invalid", "kind": "campus", "parent": old_program.pk}
        assert self.client.post(UNITS, payload, format="json").status_code == 400
        for change in ({"topology_version": 2}, {"parent": company.pk}, {"kind": "company"}, {"code": "renamed"}):
            assert self.client.patch(f"{UNITS}{legacy.pk}/", change, format="json").status_code == 400
        assert self.client.patch(f"{UNITS}{legacy.pk}/", {"nom": "Nouveau nom"}, format="json").status_code == 200
        assert self.client.post(UNITS, {**payload, "kind": "custom", "topology_version": 2}, format="json").status_code == 400
        assert self.client.delete(f"{UNITS}{company.pk}/").status_code == 405

    def test_four_real_target_categories_are_attached_and_read_without_authorization_side_effects(self):
        unit = self.unit("four-targets")
        book = self.create("bibliotheque.Livre", titre="Document réel", auteurs="Auteur", resume="Contenu catalogue")
        course = self.classe if self.secondary else self.formation
        activity = self.activity()
        before = type(self.teacher).objects.values().get(pk=self.teacher.pk)
        groups = list(self.teacher.groups.values_list("pk", flat=True))
        permissions = list(self.teacher.user_permissions.values_list("pk", flat=True))
        for kind, target in (("user", self.teacher), ("course", course), ("book", book), ("activity", activity)):
            response = self.attach(unit, kind, target)
            assert response.status_code == 201, response.data
            listed = self.listing(unit, kind)
            assert listed.status_code == 200, listed.data
            assert [(row["kind"], row["id"]) for row in listed.data["results"]] == [(kind, target.pk)]
            detail = self.detail(unit, kind, target)
            assert detail.status_code == 200, detail.data
            assert detail.data["unit"] == unit.pk
            assert self.attach(unit, kind, target).status_code == 400
        assert self.detail(unit, "book", book).data["details"]["resume"] == "Contenu catalogue"
        assert type(self.teacher).objects.values().get(pk=self.teacher.pk) == before
        assert list(self.teacher.groups.values_list("pk", flat=True)) == groups
        assert list(self.teacher.user_permissions.values_list("pk", flat=True)) == permissions
        assert apps.get_model("core.OrganizationAttachment").objects.count() == 3
        course.refresh_from_db()
        assert course.organisation_unit_id == unit.pk
        assert apps.get_model("core.WorkflowEvent").objects.filter(action="rattachement_organisation").count() == 4

    def test_academic_bridges_keep_real_relationships_and_identifiers(self):
        root = self.unit("academic", "university")
        course = self.classe if self.secondary else self.formation
        if self.secondary:
            level = self.classe.niveau
            group = self.create("classes.Groupe", etablissement=self.tenant, annee_scolaire=self.year, nom="TP A", type="tp")
            group.classes.add(self.classe)
            cases = [("level", level), ("group", group), ("subject", self.subject)]
        else:
            faculty = self.create("structure.Faculte", universite=self.tenant, nom="Sciences", code="SCI")
            dept = self.create("structure.Departement", faculte=faculty, nom="Maths", code="MAT")
            school = self.create("structure.EcoleDoctorale", universite=self.tenant, nom="ED", code="ED")
            self.formation.departement = dept
            self.formation.ecole_doctorale = school
            self.formation.niveau = "L2"
            self.formation.save()
            track = self.create("formations.Parcours", formation=self.formation, nom="Analyse", code="AN")
            cases = [
                ("faculty", faculty), ("department", dept), ("school", school), ("track", track),
                ("teaching_unit", self.subject.ue), ("subject", self.subject),
            ]
        assert self.attach(root, "course", course).status_code == 201
        for kind, item in cases:
            unit = self.unit(f"academic-{kind}", "group" if kind == "group" else "custom", root,
                             category_label=kind)
            assert self.attach(unit, kind, item).status_code == 201
            response = self.detail(unit, kind, item)
            assert response.status_code == 200, response.data
            assert response.data["id"] == item.pk
            if kind in ("group", "track", "teaching_unit"):
                assert any(row["kind"] == "course" and row["id"] == course.pk and row["unit"] == root.pk
                           for row in response.data["relations"])
        course.refresh_from_db()
        if self.secondary:
            assert list(group.classes.values_list("pk", flat=True)) == [course.pk]
        else:
            assert course.departement_id == dept.pk
            assert course.niveau == "L2"
            assert self.detail(root, "course", course).data["details"]["niveau"] == "L2"

    def test_initial_reconciliation_preserves_snapshots_provenance_and_existing_results(self):
        self.publish(offering("secondary"), locks=[OFFERING_SETTING])
        created = self.create_parent("historic")
        assert created.status_code == 201, created.data
        model = apps.get_model("classes.Classe" if self.secondary else "formations.Formation")
        old = model.objects.get(pk=created.data["id"])
        snapshot = deepcopy(old.offre_configuration)
        provenance = deepcopy(old.configuration_origine)
        self.publish(offering("secondary"), locks=[])
        unit = self.unit("new-organization")
        self.publish(offering("vocational"), unit, locks=[OFFERING_SETTING])
        evaluation = apps.get_model("notes.Evaluation").objects.values().get(pk=self.evaluation.pk)
        assert self.attach(unit, "course", old).status_code == 201
        old.refresh_from_db()
        assert old.offre_configuration == snapshot
        assert old.configuration_origine == provenance
        assert old.configuration_origine["source"]["unit"] is None
        assert apps.get_model("notes.Evaluation").objects.values().get(pk=self.evaluation.pk) == evaluation
        another = self.unit("another")
        assert self.attach(another, "course", old).status_code == 400
        new = self.create_parent("future", unit)
        assert new.status_code == 201, new.data
        assert new.data["configuration_origine"]["unit"] == unit.pk
        assert new.data["configuration_origine"]["locked"] is True
        assert new.data["offre_configuration"] == offering("vocational")
        assert old.offre_configuration != new.data["offre_configuration"]

    def test_foreign_parents_targets_and_cycles_are_rejected_by_api_and_models(self):
        unit = self.unit("local")
        foreign = self.foreign()
        foreign_unit = self.create("core.OrganizationUnit", etablissement=foreign, code="foreign", nom="Foreign", kind="campus")
        assert self.client.post(UNITS, {
            "code": "bad-parent", "nom": "Bad", "kind": "team", "topology_version": 2, "parent": foreign_unit.pk,
        }, format="json").status_code == 400
        assert self.listing(foreign_unit, "user").status_code == 404
        alien = self.create("utilisateurs.Utilisateur", username="alien", etablissement=foreign)
        assert self.attach(unit, "user", alien).status_code == 400
        if self.secondary:
            target = self.create("etablissement.Niveau", etablissement=foreign, code="alien", libelle="Foreign level")
            kind = "level"
        else:
            target = self.create("structure.Faculte", universite=foreign, code="alien", nom="Foreign faculty")
            kind = "faculty"
        assert self.attach(unit, kind, target).status_code == 400
        references = self.client.get(f"{UNITS}references/", {"kind": kind})
        assert target.pk not in [row["id"] for row in references.data["results"]]
        with pytest.raises(ValidationError):
            self.create("core.OrganizationAttachment", unit=unit, user=alien, created_by=self.admin)
        unit.parent = unit
        with pytest.raises(ValidationError):
            unit.save()
        # Defense in depth for a pre-existing corrupted database, outside normal save/API paths.
        apps.get_model("core.OrganizationUnit").objects.filter(pk=unit.pk).update(parent_id=unit.pk)
        with self.assertRaisesMessage(Exception, "Périmètre organisationnel invalide"):
            unit_path(self.tenant, apps.get_model("core.OrganizationUnit").objects.get(pk=unit.pk))

    def test_nonadmins_inactive_actors_and_unknown_models_cannot_use_attachment_endpoints(self):
        unit = self.unit("permissions")
        for changes in ({"kind": "auth.Permission"}, {"role": "super_admin"}, {"confirm": False}, {"object_id": 999999}):
            assert self.attach(unit, "user", self.teacher, **changes).status_code == 400
        alien_admin = self.create(
            "utilisateurs.Utilisateur", username="alien-admin", etablissement=self.foreign(),
            is_active=True, is_staff=True, is_superuser=True,
        )
        for user in (alien_admin, self.teacher, self.admin):
            if user == self.admin:
                user.is_active = False
                user.save(update_fields=["is_active"])
            self.client.force_authenticate(user)
            for endpoint in (f"{UNITS}catalogue/", f"{UNITS}references/?kind=user",
                             f"{UNITS}{unit.pk}/attachments/?kind=user",
                             f"{UNITS}{unit.pk}/attached-object/?kind=user&object_id={self.teacher.pk}"):
                assert self.client.get(endpoint).status_code == 403
            assert self.attach(unit, "user", self.teacher).status_code == 403
        self.client.force_authenticate(None)
        assert self.client.get(f"{UNITS}references/?kind=user").status_code in (401, 403)

    def test_paginated_references_and_attachments_and_native_read_scope_are_real(self):
        unit = self.unit("pages")
        for index in range(3):
            book = self.create("bibliotheque.Livre", titre=f"Catalogue {index}", auteurs="Auteur")
            assert self.attach(unit, "book", book).status_code == 201
        first = self.listing(unit, "book", page_size=2)
        second = self.listing(unit, "book", page_size=2, page=2)
        assert first.data["count"] == 3
        assert first.data["next"]
        assert len(second.data["results"]) == 1
        assert not ({item["id"] for item in first.data["results"]} & {item["id"] for item in second.data["results"]})
        references = self.client.get(f"{UNITS}references/", {"kind": "book", "search": "Catalogue 2", "page_size": 1})
        assert references.data["count"] == 1
        assert references.data["results"][0]["id"] == book.pk
        assert self.client.get(f"{UNITS}references/", {"kind": "not-installed"}).status_code == 400
        assert self.detail(self.unit("unattached"), "book", book).status_code == 400
        with patch("apps.utilisateurs.api.UtilisateursViewSet.get_queryset", return_value=type(self.teacher).objects.none()):
            assert self.client.get(f"{UNITS}references/", {"kind": "user"}).data["count"] == 0
            assert self.attach(unit, "user", self.teacher).status_code == 400
        if self.secondary:
            second_class = self.create(
                "classes.Classe", etablissement=self.tenant, niveau=self.classe.niveau,
                annee_scolaire=self.year, nom="6B",
            )
            group = self.create(
                "classes.Groupe", etablissement=self.tenant, annee_scolaire=self.year, nom="TD commun", type="td",
            )
            group.classes.add(self.classe, second_class)
            assert self.attach(unit, "group", group).status_code == 201
            url = f"{UNITS}{unit.pk}/attached-object/"
            first_relations = self.client.get(url, {"kind": "group", "object_id": group.pk, "page_size": 1})
            second_relations = self.client.get(url, {"kind": "group", "object_id": group.pk, "page_size": 1, "page": 2})
            assert first_relations.data["relation_pages"][0]["count"] == 2
            assert first_relations.data["relation_pages"][0]["next"]
            assert first_relations.data["relations"][0]["id"] == self.classe.pk
            assert second_relations.data["relations"][0]["id"] == second_class.pk

    def test_failed_audit_rolls_back_both_direct_and_foreign_key_bindings(self):
        unit = self.unit("atomic")
        course = self.classe if self.secondary else self.formation
        with patch("sis_common.hierarchy_api.record_workflow_event", side_effect=RuntimeError("audit unavailable")):
            for kind, item in (("user", self.teacher), ("course", course)):
                with pytest.raises(RuntimeError):
                    self.attach(unit, kind, item)
        course.refresh_from_db()
        assert course.organisation_unit_id is None
        assert apps.get_model("core.OrganizationAttachment").objects.count() == 0
        with pytest.raises(IntegrityError), transaction.atomic():
            apps.get_model("core.OrganizationAttachment").objects.bulk_create([
                apps.get_model("core.OrganizationAttachment")(unit=unit, created_by=self.admin),
            ])

    def test_indirect_foreign_ownership_is_rejected_even_inside_the_active_schema(self):
        unit = self.unit("nested-owners")
        foreign = self.foreign()
        foreign_year = self.create(self.year_model, **{self.owner_field: foreign}, **self.year_values)
        if self.secondary:
            target = self.create(
                "classes.Classe", etablissement=self.tenant, annee_scolaire=foreign_year,
                niveau=self.classe.niveau, nom="Foreign year",
            )
        else:
            faculty = self.create("structure.Faculte", universite=foreign, nom="Foreign", code="FOR")
            department = self.create("structure.Departement", faculte=faculty, nom="Foreign", code="FOR")
            target = self.create("formations.Formation", departement=department, nom="Foreign", code="FOR", type="licence")
        assert self.attach(unit, "course", target).status_code == 400
        assert target.pk not in [
            row["id"] for row in self.client.get(f"{UNITS}references/", {"kind": "course"}).data["results"]
        ]
        target.refresh_from_db()
        assert target.organisation_unit_id is None

    def test_native_deletion_of_attached_objects_is_refused_without_losing_data_or_audit(self):
        unit = self.unit("protected")
        book = self.create("bibliotheque.Livre", titre="Livre protégé", auteurs="Auteur")
        cases = [("book", book, "/api/v1/bibliotheque/livres/")]
        if self.secondary:
            cases.extend([
                ("level", self.classe.niveau, "/api/v1/etablissement/niveaux/"),
                ("activity", self.activity(), "/api/v1/edt/creneaux/"),
            ])
        else:
            faculty = self.create("structure.Faculte", universite=self.tenant, nom="Faculté", code="KEEP")
            department = self.create("structure.Departement", faculte=faculty, nom="Département", code="KEEP")
            school = self.create("structure.EcoleDoctorale", universite=self.tenant, nom="École", code="KEEP")
            cases.extend([
                ("faculty", faculty, "/api/v1/structure/facultes/"),
                ("department", department, "/api/v1/structure/departements/"),
                ("school", school, "/api/v1/structure/ecoles-doctorales/"),
            ])
        for kind, item, _endpoint in cases:
            assert self.attach(unit, kind, item).status_code == 201
        events = apps.get_model("core.WorkflowEvent").objects.count()
        for kind, item, endpoint in cases:
            response = self.client.delete(f"{endpoint}{item.pk}/")
            assert response.status_code == 400, response.data
            assert type(item).objects.filter(pk=item.pk).exists()
            assert self.detail(unit, kind, item).status_code == 200
        assert apps.get_model("core.WorkflowEvent").objects.count() == events

    def test_additive_migration_preserves_preexisting_units_publications_and_academic_records(self):
        before_course = self.classe if self.secondary else self.formation
        before = type(before_course).objects.values().get(pk=before_course.pk)
        old_target = [("core", "0007_immutable_document_archives")]
        new_target = [("core", "0008_organizationunit_category_label_and_more")]
        executor = MigrationExecutor(connection)
        executor.migrate(old_target)
        try:
            old_apps = executor.loader.project_state(old_target).apps
            old_unit = old_apps.get_model("core.OrganizationUnit").objects.create(
                etablissement_id=self.tenant.pk, code="pre-migration", nom="Campus antérieur", kind="campus",
            )
            old_revision = old_apps.get_model("core.ConfigurationRevision").objects.create(
                etablissement_id=self.tenant.pk, unit_id=old_unit.pk, revision=1,
                values={OFFERING_SETTING: offering("secondary")}, locks=[OFFERING_SETTING],
                effective_from=timezone.now(), reason="Avant migration", published_by_id=self.admin.pk,
            )
            saved_revision = old_apps.get_model("core.ConfigurationRevision").objects.values().get(pk=old_revision.pk)
        finally:
            # FastTenantTestCase holds an outer transaction; flush its deferred FK checks before DDL.
            connection.check_constraints()
            MigrationExecutor(connection).migrate(new_target)
        persisted = apps.get_model("core.OrganizationUnit").objects.get(pk=old_unit.pk)
        assert persisted.topology_version == 1
        assert persisted.code == "pre-migration"
        assert persisted.nom == "Campus antérieur"
        assert apps.get_model("core.ConfigurationRevision").objects.values().get(pk=old_revision.pk) == saved_revision
        assert type(before_course).objects.values().get(pk=before_course.pk) == before
        child = self.unit("after-migration", "service", persisted)
        assert resolve_configuration(self.tenant, child)["locks"][OFFERING_SETTING]["unit"] == persisted.pk
