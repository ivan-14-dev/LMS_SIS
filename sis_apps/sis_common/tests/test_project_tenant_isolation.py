"""Two migrated schemas, not two registry rows sharing one schema.

Run with either SIS test settings. This class deliberately avoids FastTenantTestCase's
shared schema and TransactionTestCase's flush: only its UUID-named schemas and their
own registry/domain rows are removed. Runtime requires PostgreSQL and CREATE SCHEMA.
"""

import json
import shutil
from hashlib import sha256
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from apps.integration.tests.tenant_test_case import TenantTestCase
from django.apps import apps
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.files.uploadedfile import SimpleUploadedFile
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

from sis_common.exam_files import PrivateExamStorage

BASE = "/api/v1/core/projets/"
PROJECT_MODELS = (
    "PedagogicalProject",
    "ProjectTeam",
    "ProjectMembership",
    "ProjectMilestone",
    "ProjectDelivery",
    "ProjectEvaluation",
    "ProjectContribution",
    "WorkflowEvent",
)


class ProjectTenantIsolationTests(SimpleTestCase):
    databases = {"default"}

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if connection.vendor != "postgresql":
            raise RuntimeError("Project tenant isolation requires PostgreSQL, never a schema-less substitute.")
        cls.prefix = f"project_isolation_{uuid4().hex[:16]}"
        cls.owned = []
        cls.addClassCleanup(cls.remove_owned_schemas)
        hosts = [f"{cls.prefix.replace('_', '-')}-{suffix}.example.test" for suffix in ("a", "b")]
        cls.enterClassContext(override_settings(ALLOWED_HOSTS=[*settings.ALLOWED_HOSTS, *hosts]))
        cls.folder = (Path.cwd() / ".project-test-files" / cls.prefix).resolve()
        cls.folder.mkdir(parents=True)
        cls.addClassCleanup(shutil.rmtree, cls.folder)
        field = apps.get_model("core.ProjectDelivery")._meta.get_field("fichier")
        cls.storage = PrivateExamStorage(location=cls.folder)
        cls.enterClassContext(patch.object(field, "storage", cls.storage))
        cls.sides = []
        for suffix, host in zip(("a", "b"), hosts):
            with schema_context("public"):
                tenant = get_tenant_model()(schema_name=f"{cls.prefix}_{suffix}")
                if schema_exists(tenant.schema_name) or get_tenant_domain_model().objects.filter(domain=host).exists():
                    raise RuntimeError("Isolation fixture name already exists; refusing to reuse it.")
                TenantTestCase.setup_tenant(tenant)
                tenant.nom = f"Project isolation {suffix}"
                # TenantMixin.save creates AND migrates the real schema.
                tenant.save(verbosity=0)
                cls.owned.append((tenant, host))
                assert schema_exists(tenant.schema_name)
                get_tenant_domain_model().objects.create(tenant=tenant, domain=host, is_primary=True)
            cls.sides.append(cls.populate(tenant, host, suffix))

    @classmethod
    def remove_owned_schemas(cls):
        connection.set_schema_to_public()
        for tenant, host in reversed(cls.owned):
            if tenant.schema_name not in {f"{cls.prefix}_a", f"{cls.prefix}_b"} or tenant.schema_name == "public":
                raise RuntimeError("Refusing to remove a schema not owned by this test class.")
            with schema_context("public"):
                registry = get_tenant_model().objects.filter(pk=tenant.pk, schema_name=tenant.schema_name)
                if not registry.exists():
                    raise AssertionError("Owned tenant disappeared; refusing unqualified cleanup.")
                tenant._drop_schema(force_drop=True)
                get_tenant_domain_model().objects.filter(tenant_id=tenant.pk, domain=host).delete()
                # No collector: its tenant-local PROTECT relations no longer exist.
                # The exact, newly created registry row has no other shared children.
                registry._raw_delete(using=connection.alias)

    @staticmethod
    def client_for(side, role="manager"):
        client = APIClient(SERVER_NAME=side["host"])
        client.force_authenticate(side[role])
        return client

    @staticmethod
    def wire(response, status=200):
        assert response.status_code == status, response.status_code
        return json.loads(response.content)

    @classmethod
    def populate(cls, tenant, host, suffix):
        side = {"tenant": tenant, "host": host}
        with tenant_context(tenant):
            users = get_user_model()
            role = "eleve" if settings.SIS_VARIANT == "secondaire" else "etudiant"
            # Deliberate cross-schema integer collisions, different identities.
            for key, pk, user_role, permission in (
                ("manager", 8101, "enseignant", "gerer_projet_pedagogique"),
                ("evaluator", 8102, "enseignant", "evaluer_projet_pedagogique"),
                ("learner", 8103, role, None),
                ("other", 8104, role, None),
            ):
                user = users.objects.create_user(
                    f"{cls.prefix}-{suffix}-{key}",
                    password="project-schema-test-only",
                    pk=pk,
                    etablissement=tenant,
                    role=user_role,
                    is_staff=False,
                    is_superuser=False,
                )
                if permission:
                    user.user_permissions.add(
                        Permission.objects.get(content_type__app_label="core", codename=permission)
                    )
                side[key] = user
            client = cls.client_for(side)
            assert client.get(BASE).status_code == 403
            apps.get_model("core.ModuleConfiguration").objects.create(
                etablissement=tenant, enabled={"sis.projects": True}
            )
            project = cls.wire(
                client.post(
                    BASE,
                    {
                        "titre": f"Private project {suffix}",
                        "mode": "individuel",
                        "responsable": side["manager"].pk,
                        "evaluateurs": [side["evaluator"].pk],
                    },
                    format="json",
                ),
                201,
            )
            side["path"] = f"{BASE}{project['id']}/"

            def command(tail, data, actor=client, multipart=False):
                result = cls.wire(
                    actor.post(
                        f"{side['path']}{tail}",
                        {"version": project["version"], **data},
                        format="multipart" if multipart else "json",
                    ),
                    201,
                )
                project["version"] = result["version"]
                return result

            side["milestone"] = command(
                "jalons/",
                {
                    "titre": f"Private milestone {suffix}",
                    "ordre": 1,
                    "echeance": "2035-01-01T00:00:00Z",
                    "bareme": "20",
                },
            )["jalon"]
            side["team"] = command("equipes/", {"nom": f"Private team {suffix}", "membres": [side["learner"].pk]})[
                "equipe"
            ]
            side["other_team"] = command("equipes/", {"nom": f"Other team {suffix}", "membres": [side["other"].pk]})[
                "equipe"
            ]
            side["team_path"] = f"{side['path']}equipes/{side['team']['id']}/"
            side["pdf"] = f"%PDF-1.4\nPrivate evidence {suffix}\n%%EOF\n".encode()
            side["delivery"] = command(
                f"equipes/{side['team']['id']}/livrables/",
                {
                    "jalon": side["milestone"]["id"],
                    "fichier": SimpleUploadedFile("evidence.pdf", side["pdf"], content_type="application/pdf"),
                },
                cls.client_for(side, "learner"),
                multipart=True,
            )["livrable"]
            side["file_path"] = f"{side['team_path']}livrables/{side['delivery']['id']}/telecharger/"
            side["project"] = cls.wire(client.get(side["path"]))
        return side

    def snapshots(self):
        snapshots = []
        for side in self.sides:
            with tenant_context(side["tenant"]):
                models = [apps.get_model("core", name) for name in PROJECT_MODELS]
                models.append(apps.get_model("core.PedagogicalProject").evaluateurs.through)
                snapshots.append([list(model.objects.order_by("pk").values()) for model in models])
        return snapshots

    def denied(self, response, status, foreign):
        self.assertEqual(response.status_code, status)
        body = response.content.decode()
        for private in (foreign["project"]["titre"], foreign["team"]["nom"], foreign["milestone"]["titre"]):
            self.assertNotIn(private, body)
        self.assertNotIn("%PDF-", body)

    def test_hosts_select_populated_schemas_and_cross_objects_never_read_or_write(self):
        for local, foreign in (self.sides, self.sides[::-1]):
            manager = self.client_for(local)
            evaluator = self.client_for(local, "evaluator")
            learner = self.client_for(local, "learner")
            self.assertEqual(local["manager"].pk, foreign["manager"].pk)
            self.assertNotEqual(local["tenant"].pk, foreign["tenant"].pk)
            self.assertEqual(self.wire(manager.get(BASE))["results"], [local["project"]])
            self.assertEqual(connection.schema_name, local["tenant"].schema_name)
            for client, manage, evaluate in ((manager, True, False), (evaluator, False, True), (learner, False, False)):
                own = self.wire(client.get(local["path"]))
                self.assertEqual(own["actions"]["can_manage"], manage)
                self.assertEqual(own["actions"]["can_evaluate"], evaluate)
                self.assertIsNone(own["cours"])
                self.assertIsNone(own["competences"])
                file = client.get(local["file_path"])
                self.assertEqual(file.status_code, 200)
                try:
                    self.assertEqual(sha256(b"".join(file.streaming_content)).hexdigest(), local["delivery"]["sha256"])
                finally:
                    file.close()
                before_denied_reads = self.snapshots()
                with patch.object(self.storage, "open", side_effect=AssertionError("Foreign file opened")):
                    for path in (foreign["path"], foreign["team_path"] + "livrables/", foreign["file_path"]):
                        self.denied(client.get(path), 404, foreign)
                self.assertEqual(self.snapshots(), before_denied_reads)
            # Successful downloads legitimately append workflow audit events.
            # The denied-command baseline starts after those positive controls.
            before = self.snapshots()
            for kind, expected in (
                ("responsable", {local["manager"].pk}),
                ("evaluateur", {local["evaluator"].pk}),
                ("membre", {local["learner"].pk, local["other"].pk}),
            ):
                path = f"{BASE}candidats/?type={kind}&q={self.prefix}&projet={local['project']['id']}"
                candidates = self.wire(manager.get(path))["results"]
                self.assertEqual({candidate["id"] for candidate in candidates}, expected)
                self.assertTrue(all(f"-{local['host'].split('.')[0][-1]}-" in item["nom"] for item in candidates))
                self.denied(manager.get(path.replace(local["project"]["id"], foreign["project"]["id"])), 404, foreign)
            version = local["project"]["version"]
            attacks = (
                (foreign["path"] + "configurer/", {"version": foreign["project"]["version"], "titre": "Intrusion"}),
                (
                    foreign["path"] + "equipes/",
                    {"version": foreign["project"]["version"], "nom": "Intrusion", "membres": [local["learner"].pk]},
                ),
                (local["path"] + f"equipes/{foreign['team']['id']}/membres/", {"version": version, "membres": []}),
            )
            for path, data in attacks:
                self.denied(manager.post(path, data, format="json"), 404, foreign)
            for suffix in ("livrables/", "evaluations/"):
                self.denied(
                    learner.post(foreign["team_path"] + suffix, {"version": version}, format="json"), 404, foreign
                )
            with patch.object(self.storage, "open", side_effect=AssertionError("Foreign file opened")):
                nested_file = local["team_path"] + f"livrables/{foreign['delivery']['id']}/telecharger/"
                self.denied(manager.get(nested_file), 404, foreign)
            self.denied(
                learner.post(
                    local["team_path"] + "livrables/",
                    {
                        "version": version,
                        "jalon": foreign["milestone"]["id"],
                        "fichier": SimpleUploadedFile("cross.pdf", b"%PDF-1.4\ncross", content_type="application/pdf"),
                    },
                    format="multipart",
                ),
                404,
                foreign,
            )
            self.assertEqual(self.snapshots(), before)

    def test_foreign_actor_integer_collision_and_module_switch_are_not_authority(self):
        a, b = self.sides
        before = self.snapshots()
        foreign = APIClient(SERVER_NAME=b["host"])
        foreign.force_authenticate(a["manager"])
        with patch.object(self.storage, "open", side_effect=AssertionError("Foreign actor opened a file")):
            for path in (BASE, b["path"], b["file_path"], f"{BASE}candidats/?type=membre&q={self.prefix}"):
                self.denied(foreign.get(path), 403, b)
            self.denied(
                foreign.post(
                    BASE, {"titre": "Intrusion", "mode": "individuel", "responsable": b["manager"].pk}, format="json"
                ),
                403,
                b,
            )
            self.denied(
                foreign.post(
                    b["path"] + "configurer/", {"version": b["project"]["version"], "titre": "Intrusion"}, format="json"
                ),
                403,
                b,
            )
        with tenant_context(b["tenant"]):
            configuration = apps.get_model("core.ModuleConfiguration").objects.get(etablissement=b["tenant"])
            configuration.enabled = {"sis.projects": False}
            configuration.save(update_fields=["enabled"])
        try:
            client = self.client_for(b)
            self.denied(client.get(b["path"]), 403, b)
            self.denied(client.get(b["file_path"]), 403, b)
            self.denied(client.post(BASE, {"titre": "Intrusion"}, format="json"), 403, b)
            self.assertEqual(self.wire(self.client_for(a).get(a["path"])), a["project"])
        finally:
            with tenant_context(b["tenant"]):
                configuration.enabled = {"sis.projects": True}
                configuration.save(update_fields=["enabled"])
        self.assertEqual(self.snapshots(), before)

    def test_real_session_cookie_replayed_on_peer_host_cannot_adopt_colliding_user(self):
        a, b = self.sides
        before = self.snapshots()
        source = APIClient(SERVER_NAME=a["host"])
        peer = APIClient(SERVER_NAME=b["host"])
        backend = "sis_common.group_backends.ActiveGroupModelBackend"
        with tenant_context(a["tenant"]):
            source.force_login(a["manager"], backend=backend)
        self.assertEqual(self.wire(source.get(a["path"])), a["project"])
        peer.cookies.update(source.cookies)
        response = peer.get(b["path"])
        self.assertIn(response.status_code, (401, 403))
        self.assertNotIn(b["project"]["titre"], response.content.decode())
        response = peer.post(
            BASE, {"titre": "Intrusion", "mode": "individuel", "responsable": b["manager"].pk}, format="json"
        )
        self.assertIn(response.status_code, (401, 403))
        peer.cookies.clear()
        with tenant_context(b["tenant"]):
            peer.force_login(b["manager"], backend=backend)
        self.assertEqual(self.wire(peer.get(b["path"])), b["project"])
        self.assertEqual(self.snapshots(), before)
