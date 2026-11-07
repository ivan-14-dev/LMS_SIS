"""10.7: native search/detail reads through two migrated, populated tenant hosts.

Run separately with each SIS's settings and PostgreSQL. Django force_login
sessions pass through the real middleware/router, without force_authenticate
or flush. The five business types include existing official documents and
mapped SIS evaluations, not a native LMS catalogue; no PDF rendering is needed.
"""

import json
from uuid import uuid4

from apps.integration.tests.tenant_test_case import TenantTestCase
from django.apps import apps
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.db import connection
from django.test import SimpleTestCase, override_settings
from django_tenants.utils import (
    get_tenant_domain_model,
    get_tenant_model,
    schema_context,
    schema_exists,
    tenant_context,
)
from rest_framework.test import APIClient

SEARCH = "/api/v1/core/recherche-academique/"
BACKEND = "sis_common.group_backends.ActiveGroupModelBackend"
# BUL- also matches the secondary document's real, PK-derived PDF reference.
TERM = "BUL-"
SHARED_OWNERS = {
    "anneescolaire": "etablissement_id",
    "periode": "annee_scolaire__etablissement_id",
    "niveau": "etablissement_id",
    "anneeuniversitaire": "universite_id",
    "semestre": "annee_universitaire__universite_id",
}


class AcademicSearchTenantIsolationTests(SimpleTestCase):
    databases = {"default"}

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if connection.vendor != "postgresql":
            raise RuntimeError("Search isolation requires PostgreSQL and two real migrated schemas.")
        cls.secondary = settings.SIS_VARIANT == "secondaire"
        cls.prefix = f"search_isolation_{uuid4().hex}"
        cls.owned = []
        cls.shared_owned = {}
        cls.learner_resource = "eleves" if cls.secondary else "etudiants"
        cls.learner_permission = "eleves.view_eleve" if cls.secondary else "etudiants.view_etudiant"
        cls.finance_permission = "paiements.change_paiement" if cls.secondary else "paiements.change_paiementfrais"
        cls.sources = {
            cls.learner_resource: f"/api/v1/{cls.learner_resource}/",
            "cours": "/api/v1/integration/mappings/courses/",
            "evaluations_lms": "/api/v1/notes/evaluations/",
            "factures": "/api/v1/paiements/factures/",
            **(
                {"bulletins": "/api/v1/notes/bulletins/"}
                if cls.secondary
                else {
                    "releves": "/api/v1/releves/",
                    "transcripts": "/api/v1/releves/transcripts/",
                    "attestations": "/api/v1/releves/attestations/",
                }
            ),
        }
        hosts = [f"{cls.prefix.replace('_', '-')}-{suffix}.example.test" for suffix in ("a", "b")]
        cls.enterClassContext(
            override_settings(
                ALLOWED_HOSTS=[*settings.ALLOWED_HOSTS, *hosts],
                # Private cache, not a disabled/cleared throttle. Colliding user PKs
                # share the normal rate limit; each scenario stays below 100 reads.
                CACHES={
                    "default": {
                        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
                        "LOCATION": cls.prefix,
                    }
                },
            )
        )
        cls.sides = []
        for suffix, host in zip(("a", "b"), hosts):
            with schema_context("public"):
                tenant = get_tenant_model()(schema_name=f"{cls.prefix}_{suffix}")
                if (
                    schema_exists(tenant.schema_name)
                    or get_tenant_model().objects.filter(schema_name=tenant.schema_name).exists()
                    or get_tenant_domain_model().objects.filter(domain=host).exists()
                ):
                    raise RuntimeError("Refusing to reuse an existing schema, registry row or domain.")
                TenantTestCase.setup_tenant(tenant)
                tenant.nom = f"Synthetic search isolation {suffix}"
                # TenantMixin.save creates and migrates the schema.
                tenant.save(verbosity=0)
                cls.owned.append((tenant.pk, tenant.schema_name, host))
                cls.shared_owned[tenant.schema_name] = []
                # Individual cleanups still run for A if B's setup/cleanup fails.
                cls.addClassCleanup(cls.remove_owned_schema, tenant, host)
                assert schema_exists(tenant.schema_name)
                get_tenant_domain_model().objects.create(tenant=tenant, domain=host, is_primary=True)
            cls.sides.append(cls.populate(tenant, host, suffix))

    @classmethod
    def remove_owned_schema(cls, tenant, host):
        connection.set_schema_to_public()
        if (tenant.pk, tenant.schema_name, host) not in cls.owned or tenant.schema_name not in {
            f"{cls.prefix}_a",
            f"{cls.prefix}_b",
        }:
            raise RuntimeError("Refusing cleanup outside the UUID-owned tenants.")
        with schema_context("public"):
            registry = get_tenant_model().objects.filter(pk=tenant.pk, schema_name=tenant.schema_name)
            if not registry.exists():
                raise AssertionError("Owned registry row disappeared; refusing unqualified cleanup.")
            tenant._drop_schema(force_drop=True)
            assert not schema_exists(tenant.schema_name)
            # etablissement is SHARED_APPS: years/periods/levels are in public.
            # Delete only recorded PKs with their tenant ownership, child first.
            # A collector would traverse tenant tables that no longer exist.
            for obj in reversed(cls.shared_owned[tenant.schema_name]):
                owner = SHARED_OWNERS[obj._meta.model_name]
                owned = type(obj).objects.filter(pk=obj.pk, **{owner: tenant.pk})
                if owned._raw_delete(using=connection.alias) != 1:
                    raise AssertionError(f"Owned shared fixture disappeared: {obj._meta.label}/{obj.pk}")
            get_tenant_domain_model().objects.filter(tenant_id=tenant.pk, domain=host).delete()
            if registry._raw_delete(using=connection.alias) != 1:
                raise AssertionError("Owned tenant registry was not removed.")
            assert not get_tenant_domain_model().objects.filter(tenant_id=tenant.pk, domain=host).exists()
            assert not registry.exists()

    @classmethod
    def shared(cls, side, model, **values):
        with schema_context("public"):
            obj = apps.get_model("etablissement", model).objects.create(**values)
        cls.shared_owned[side["tenant"].schema_name].append(obj)
        return obj

    @classmethod
    def populate(cls, tenant, host, suffix):
        side = {"tenant": tenant, "host": host, "entries": {resource: [] for resource in cls.sources}}
        document_permissions = (
            ["notes.view_bulletin"]
            if cls.secondary
            else ["releves.view_relevenotes", "releves.view_transcript", "releves.view_attestation"]
        )
        with tenant_context(tenant):
            side["permissions"] = [
                Permission.objects.get(content_type__app_label=app, codename=codename)
                for app, codename in (
                    name.split(".")
                    for name in [
                        cls.learner_permission,
                        cls.finance_permission,
                        "notes.view_evaluation",
                        "integration.view_edxcoursemapping",
                        *document_permissions,
                    ]
                )
            ]
            # Separate real actors keep each scenario within unchanged throttles.
            # Every actor has the same username AND PK in A and B, no superuser.
            for index, key in enumerate(("reader", "revocable", "replay")):
                user = get_user_model().objects.create_user(
                    f"{cls.prefix}-{key}",
                    pk=84101 + index,
                    etablissement=tenant,
                    role="bibliothecaire" if cls.secondary else "autre",
                    is_staff=True,
                    is_superuser=False,
                )
                user.user_permissions.add(*side["permissions"])
                side[key] = user
            teacher = get_user_model().objects.create_user(
                f"{cls.prefix}-teacher", pk=84104, etablissement=tenant, role="enseignant"
            )
            if cls.secondary:
                teacher = apps.get_model("enseignants.Personnel").objects.create(
                    pk=84200, user=teacher, matricule="TEACHER-COLLISION", date_embauche="2026-09-01"
                )
            cls.populate_calendar(side)
            # First row: identical PK/code/name. Further rows: foreign-only
            # sentinels. Different A/B counts detect aggregation across schemas.
            rows = [(83200, "COLLISION"), (83210 if suffix == "a" else 83220, f"ONLY-{suffix}-1")]
            if suffix == "b":
                rows.append((83221, "ONLY-b-2"))
            for index, (pk, code) in enumerate(rows):
                private = f"SyntheticPrivate-{suffix}-{index}"
                learner_user = get_user_model().objects.create_user(
                    f"{cls.prefix}-learner-{index}",
                    pk=84300 + index,
                    etablissement=tenant,
                    role="eleve" if cls.secondary else "etudiant",
                    first_name=f"{TERM}{code}",
                    last_name="Synthetic",
                    email=f"{private}@example.test",
                )
                if index == 0:
                    side["learner"] = learner_user
                    learner_user.user_permissions.add(
                        *[
                            permission
                            for permission in side["permissions"]
                            if permission.codename in (cls.learner_permission.split(".")[1], "view_edxcoursemapping")
                        ]
                    )
                learner = apps.get_model("eleves.Eleve" if cls.secondary else "etudiants.Etudiant").objects.create(
                    pk=pk,
                    user=learner_user,
                    matricule=f"{TERM}LEARNER-{code}",
                    ine=private,
                    date_naissance="2010-01-01" if cls.secondary else "2003-01-01",
                    lieu_naissance="Synthetic",
                    sexe="F",
                    **(
                        {"etablissement": tenant, "date_inscription": "2026-09-01"}
                        if cls.secondary
                        else {"universite": tenant}
                    ),
                )
                cls.record(
                    side, cls.learner_resource, learner, learner.matricule, learner_user.get_full_name(), ine=private
                )
                course = cls.populate_course(side, pk, code, private)
                cls.record(
                    side,
                    "cours",
                    course,
                    course.course_id,
                    course.course_name,
                    **{"matiere_nom" if cls.secondary else "ecue_nom": private},
                )
                evaluation = apps.get_model("notes.Evaluation").objects.create(
                    pk=pk,
                    titre=f"{TERM}ACTIVITY-{code}",
                    description=private,
                    enseignant=teacher,
                    date="2026-11-15",
                    **(
                        {"matiere": course.matiere, "classe": course.classe, "periode": side["period"]}
                        if cls.secondary
                        else {"ecue": course.ecue, "semestre": side["period"], "modalite": "cc"}
                    ),
                )
                mapping = apps.get_model("integration.EdxAssessmentMapping").objects.create(
                    pk=pk,
                    course=course,
                    evaluation=evaluation,
                    subsection_id=f"block-v1:SIS+{TERM}{code}+2026+type@sequential+block@assessment",
                )
                cls.record(
                    side, "evaluations_lms", evaluation, mapping.subsection_id, evaluation.titre, description=private
                )
                invoice_model = apps.get_model("paiements.Facture" if cls.secondary else "paiements.FactureFrais")
                invoice = invoice_model.objects.create(
                    pk=pk,
                    type_frais=side["fee"],
                    numero=f"{TERM}INVOICE-{code}",
                    date_emission="2026-09-01",
                    date_echeance="2026-10-01",
                    montant="100.00",
                    note=private,
                    **{"eleve" if cls.secondary else "etudiant": learner},
                )
                cls.record(side, "factures", invoice, invoice.numero, f"Facture {invoice.numero}", note=private)
                cls.populate_documents(side, learner, course, pk, code, private)
        return side

    @classmethod
    def populate_calendar(cls, side):
        tenant = side["tenant"]
        dates = {"date_debut": "2026-09-01", "date_fin": "2027-08-31"}
        year_field = "annee_scolaire" if cls.secondary else "annee_universitaire"
        side["year"] = cls.shared(
            side,
            "AnneeScolaire" if cls.secondary else "AnneeUniversitaire",
            libelle="2026-2027",
            **dates,
            **{"etablissement" if cls.secondary else "universite": tenant},
        )
        side["period"] = cls.shared(
            side,
            "Periode" if cls.secondary else "Semestre",
            numero=1,
            type="trimestre" if cls.secondary else "impair",
            **dates,
            **{year_field: side["year"]},
        )
        if cls.secondary:
            side["level"] = cls.shared(side, "Niveau", etablissement=tenant, code="6e", libelle="Synthetic level")
        else:
            faculty = apps.get_model("structure.Faculte").objects.create(
                universite=tenant, code="COLLISION", nom="Synthetic faculty"
            )
            department = apps.get_model("structure.Departement").objects.create(
                faculte=faculty, code="COLLISION", nom="Synthetic department"
            )
            formation = apps.get_model("formations.Formation").objects.create(
                departement=department, code="COLLISION", nom="Synthetic formation", type="licence"
            )
            side["curriculum"] = apps.get_model("formations.MaquetteFormation").objects.create(
                formation=formation, annee_universitaire=side["year"]
            )
        side["fee"] = apps.get_model(
            "paiements.TypeFrais" if cls.secondary else "paiements.TypeFraisInscription"
        ).objects.create(code="COLLISION", libelle="Synthetic fee", montant="100.00", **{year_field: side["year"]})

    @classmethod
    def populate_course(cls, side, pk, code, private):
        if cls.secondary:
            classroom = apps.get_model("classes.Classe").objects.create(
                pk=pk,
                etablissement=side["tenant"],
                annee_scolaire=side["year"],
                niveau=side["level"],
                nom=f"Synthetic class {code}",
            )
            subject = apps.get_model("classes.Matiere").objects.create(
                pk=pk, etablissement=side["tenant"], code=code, nom=private
            )
            relation = {"classe": classroom, "matiere": subject}
        else:
            unit = apps.get_model("ue_ecue.UE").objects.create(
                pk=pk,
                maquette=side["curriculum"],
                semestre=side["period"],
                code=code,
                nom=f"Synthetic unit {code}",
                credits_ects=6,
            )
            ecue = apps.get_model("ue_ecue.ECUE").objects.create(pk=pk, ue=unit, code=code, nom=private, credits_ects=3)
            relation = {"ecue": ecue}
        return apps.get_model("integration.EdxCourseMapping").objects.create(
            pk=pk,
            course_id=f"course-v1:SIS+{TERM}{code}+2026",
            course_name=f"{TERM}COURSE-{code}",
            **relation,
        )

    @classmethod
    def populate_documents(cls, side, learner, course, pk, code, private):
        pdf_path = f"synthetic/{private}.pdf"
        if cls.secondary:
            bulletin = apps.get_model("notes.Bulletin").objects.create(
                pk=pk, eleve=learner, classe=course.classe, periode=side["period"], publie=True, pdf_path=pdf_path
            )
            cls.record(side, "bulletins", bulletin, f"BUL-{pk}", f"Bulletin BUL-{pk}", pdf_path=pdf_path)
            return
        for resource, model, number_field, label, values in (
            ("releves", "ReleveNotes", "numero_serie", "Relevé", {"semestre": side["period"], "signe": True}),
            ("transcripts", "Transcript", "numero_serie", "Transcript", {"credits_total": 60, "credits_valides": 30}),
            ("attestations", "Attestation", "numero", "Attestation", {"type": "inscription"}),
        ):
            number = f"{TERM}{resource}-{code}"
            document = apps.get_model("releves", model).objects.create(
                pk=pk,
                etudiant=learner,
                signe_par=side["reader"],
                date_emission="2026-11-15",
                pdf_path=pdf_path,
                **{number_field: number},
                **values,
            )
            if resource == "transcripts":
                document.annees.add(side["year"])
            cls.record(side, resource, document, number, f"{label} {number}", pdf_path=pdf_path)

    @staticmethod
    def record(side, resource, obj, code, name, **detail):
        side["entries"][resource].append(
            {"row": {"id": obj.pk, "code": code, "nom": name}, "detail": {"id": obj.pk, **detail}}
        )

    @staticmethod
    def client_for(side, role):
        client = APIClient(SERVER_NAME=side["host"])
        with tenant_context(side["tenant"]):
            client.force_login(side[role], backend=BACKEND)
        return client

    def detail_path(self, resource, entry):
        return f"{self.sources[resource]}{entry['row']['id']}/"

    def search(self, client, resource):
        # Exactly these parameters are replayed for every role, host and revocation.
        return client.get(SEARCH, {"ressource": resource, "q": TERM}, secure=True)

    def assert_hidden(self, response, entries):
        body = json.dumps(response.json(), ensure_ascii=False)
        for entry in entries:
            for value in (entry["row"]["code"], entry["row"]["nom"], *entry["detail"].values()):
                if isinstance(value, str):
                    self.assertNotIn(value, body)

    def assert_results(self, client, side, resource, entries, foreign):
        response = self.search(client, resource)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(connection.schema_name, side["tenant"].schema_name)
        data = response.json()
        self.assertEqual(set(data), {"count", "next", "previous", "results"})
        self.assertEqual(data["count"], len(entries))
        self.assertEqual(data["results"], [entry["row"] for entry in entries])
        self.assertIsNone(data["next"])
        self.assertIsNone(data["previous"])
        # The first row deliberately has identical searchable identifiers.
        self.assert_hidden(response, foreign["entries"][resource][1:])
        self.assert_hidden(response, [entry for entry in side["entries"][resource] if entry not in entries])
        for own in [*side["entries"][resource], *foreign["entries"][resource]]:
            for field, private in own["detail"].items():
                if field != "id":
                    self.assertNotIn(private, json.dumps(data, ensure_ascii=False))

    def assert_detail(self, client, resource, entry, foreign):
        response = client.get(self.detail_path(resource, entry), secure=True)
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        for key, value in entry["detail"].items():
            self.assertEqual(data[key], value)
        for other in foreign["entries"][resource]:
            for field, private in other["detail"].items():
                if field != "id":
                    self.assertNotIn(private, json.dumps(data, ensure_ascii=False))

    def assert_denied(self, response, statuses, entries, search=False):
        self.assertIn(response.status_code, statuses, response.content)
        data = response.json()
        if search and response.status_code == 200:
            self.assertEqual(data, {"count": 0, "next": None, "previous": None, "results": []})
        else:
            self.assertNotIn("count", data)
            self.assertNotIn("results", data)
        self.assert_hidden(response, entries)

    def assert_all_visible(self, client, side, foreign):
        for resource, entries in side["entries"].items():
            with self.subTest(host=side["host"], resource=resource):
                self.assert_results(client, side, resource, entries, foreign)
                for entry in entries:
                    self.assert_detail(client, resource, entry, foreign)

    def test_native_actors_and_less_privileged_learners_use_their_own_populated_schema(self):
        a, b = self.sides
        self.assertNotEqual(a["tenant"].pk, b["tenant"].pk)
        for role in ("reader", "revocable", "replay", "learner"):
            self.assertEqual(a[role].pk, b[role].pk)
            self.assertEqual(a[role].username, b[role].username)
        for resource in self.sources:
            self.assertEqual(a["entries"][resource][0]["row"], b["entries"][resource][0]["row"])
        for local, foreign in (self.sides, self.sides[::-1]):
            manager = self.client_for(local, "reader")
            self.assert_all_visible(manager, local, foreign)
            learner = self.client_for(local, "learner")
            for resource, entries in local["entries"].items():
                with self.subTest(host=local["host"], resource=resource, role="learner"):
                    foreign_only = foreign["entries"][resource][-1]
                    self.assert_denied(
                        manager.get(self.detail_path(resource, foreign_only), secure=True), (404,), [foreign_only]
                    )
                    if resource in ("cours", "evaluations_lms"):
                        self.assert_denied(self.search(learner, resource), (403,), entries, search=True)
                        status = 403 if resource == "cours" else 404
                        self.assert_denied(
                            learner.get(self.detail_path(resource, entries[0]), secure=True), (status,), entries
                        )
                    else:
                        self.assert_results(learner, local, resource, entries[:1], foreign)
                        self.assert_detail(learner, resource, entries[0], foreign)
                        self.assert_denied(
                            learner.get(self.detail_path(resource, entries[-1]), secure=True), (404,), entries[1:]
                        )

    def test_effective_revocation_is_observed_by_the_same_session_without_affecting_peer(self):
        for local, foreign in (self.sides, self.sides[::-1]):
            client = self.client_for(local, "revocable")
            self.assert_all_visible(client, local, foreign)
            actor = local["revocable"]
            removed = [
                permission for permission in local["permissions"] if permission.codename != "view_edxcoursemapping"
            ]
            with tenant_context(local["tenant"]):
                actor.user_permissions.remove(*removed)
                # LMS read permission is deliberately retained: is_staff is the
                # native admin gate. Secondary learner detail additionally needs
                # a scope withdrawal: its read API does not require view_eleve.
                actor.is_staff = False
                actor.attributs_acces = (
                    {"permission_scopes": {self.learner_permission: {"eleves": []}}} if self.secondary else {}
                )
                actor.save(update_fields=["is_staff", "attributs_acces"])
            try:
                peer = self.client_for(foreign, "reader")
                for resource, entries in local["entries"].items():
                    with self.subTest(host=local["host"], resource=resource):
                        hidden = [*entries, *foreign["entries"][resource]]
                        search_status = (
                            403 if resource in (self.learner_resource, "cours", "evaluations_lms", "bulletins") else 200
                        )
                        self.assert_denied(self.search(client, resource), (search_status,), hidden, search=True)
                        detail_status = 403 if resource in ("cours", "bulletins") else 404
                        for entry in entries:
                            self.assert_denied(
                                client.get(self.detail_path(resource, entry), secure=True), (detail_status,), hidden
                            )
                        self.assert_results(peer, foreign, resource, foreign["entries"][resource], local)
            finally:
                with tenant_context(local["tenant"]):
                    actor.user_permissions.add(*removed)
                    actor.is_staff = True
                    actor.attributs_acces = {}
                    actor.save(update_fields=["is_staff", "attributs_acces"])

    def test_session_replay_on_peer_host_cannot_adopt_the_colliding_native_account(self):
        for local, foreign in (self.sides, self.sides[::-1]):
            source = self.client_for(local, "replay")
            self.assert_all_visible(source, local, foreign)
            peer = APIClient(SERVER_NAME=foreign["host"])
            for resource, entries in foreign["entries"].items():
                with self.subTest(source=local["host"], destination=foreign["host"], resource=resource):
                    hidden = [*entries, *local["entries"][resource]]
                    # SessionMiddleware may expire a rejected cookie. Replay the
                    # original cookie for EVERY route, not an anonymous follow-up.
                    peer.cookies.update(source.cookies)
                    self.assert_denied(self.search(peer, resource), (401, 403), hidden, search=True)
                    self.assertEqual(connection.schema_name, foreign["tenant"].schema_name)
                    peer.cookies.update(source.cookies)
                    self.assert_denied(
                        peer.get(self.detail_path(resource, entries[0]), secure=True), (401, 403), hidden
                    )
            peer.cookies.clear()
            with tenant_context(foreign["tenant"]):
                peer.force_login(foreign["replay"], backend=BACKEND)
            for resource, entries in foreign["entries"].items():
                self.assert_results(peer, foreign, resource, entries, local)
