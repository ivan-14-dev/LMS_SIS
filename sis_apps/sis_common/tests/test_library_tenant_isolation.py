"""Real migrated schemas with colliding book/user IDs and distinct private bytes."""

import shutil
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from apps.bibliotheque.models import Livre
from apps.integration.tests.tenant_test_case import TenantTestCase
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

from sis_common.library_files import PrivateLibraryStorage


class LibraryTenantIsolationTests(SimpleTestCase):
    databases = {"default"}

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        assert connection.vendor == "postgresql"
        cls.prefix = f"library_isolation_{uuid4().hex[:16]}"
        cls.owned = []
        cls.addClassCleanup(cls.remove_owned_schemas)
        hosts = [f"{cls.prefix.replace('_', '-')}-{side}.example.test" for side in ("a", "b")]
        cls.enterClassContext(
            override_settings(
                ALLOWED_HOSTS=[*settings.ALLOWED_HOSTS, *hosts],
                CACHES={
                    "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": cls.prefix}
                },
            )
        )
        cls.folder = (Path.cwd() / ".library-test-files" / cls.prefix).resolve()
        cls.folder.mkdir(parents=True)
        cls.addClassCleanup(shutil.rmtree, cls.folder)
        cls.storage = PrivateLibraryStorage(location=cls.folder)
        cls.enterClassContext(patch.object(Livre._meta.get_field("ressource_numerique"), "storage", cls.storage))
        cls.sides = []
        for suffix, host in zip(("a", "b"), hosts):
            with schema_context("public"):
                tenant = get_tenant_model()(schema_name=f"{cls.prefix}_{suffix}")
                if schema_exists(tenant.schema_name) or get_tenant_domain_model().objects.filter(domain=host).exists():
                    raise RuntimeError("Refusing to reuse a tenant fixture.")
                TenantTestCase.setup_tenant(tenant)
                tenant.save(verbosity=0)
                cls.owned.append((tenant, host))
                get_tenant_domain_model().objects.create(tenant=tenant, domain=host, is_primary=True)
            with tenant_context(tenant):
                user = get_user_model().objects.create_user(
                    f"{cls.prefix}-{suffix}", pk=8101, role="enseignant", etablissement=tenant
                )
                user.user_permissions.add(
                    *Permission.objects.filter(
                        content_type__app_label="bibliotheque",
                        codename__in=("consulter_ressource_numerique", "change_livre"),
                    )
                )
                content = f"%PDF-1.4\nPrivate library {suffix}\n%%EOF\n".encode()
                book = Livre.objects.create(
                    pk=8201,
                    titre=f"Titre privé {suffix}",
                    auteurs="Auteur",
                    licence_active=True,
                    licence_reference=f"Licence locale {suffix}",
                    ressource_numerique=SimpleUploadedFile(f"{suffix}.pdf", content, content_type="application/pdf"),
                )
                cls.sides.append({"tenant": tenant, "host": host, "user": user, "book": book, "content": content})

    @classmethod
    def remove_owned_schemas(cls):
        connection.set_schema_to_public()
        for tenant, host in reversed(cls.owned):
            if tenant.schema_name not in {f"{cls.prefix}_a", f"{cls.prefix}_b"}:
                raise RuntimeError("Refusing cleanup outside owned library schemas.")
            with schema_context("public"):
                registry = get_tenant_model().objects.filter(pk=tenant.pk, schema_name=tenant.schema_name)
                if not registry.exists():
                    raise AssertionError("Owned registry row disappeared.")
                tenant._drop_schema(force_drop=True)
                get_tenant_domain_model().objects.filter(tenant_id=tenant.pk, domain=host).delete()
                registry._raw_delete(using=connection.alias)

    def test_colliding_objects_do_not_share_metadata_bytes_or_writes(self):
        for own, other in (self.sides, self.sides[::-1]):
            client = APIClient(SERVER_NAME=own["host"])
            client.force_authenticate(own["user"])
            base = f"/api/v1/bibliotheque/livres/{own['book'].pk}/"
            detail = client.get(base)
            assert detail.status_code == 200
            assert detail.data["titre"] == own["book"].titre
            result = client.get(f"{base}numerique/")
            assert result.status_code == 200
            assert b"".join(result.streaming_content) == own["content"]
            with patch.object(self.storage, "open", side_effect=AssertionError("Foreign file opened")):
                assert client.get(f"/media/{other['book'].ressource_numerique.name}").status_code == 404
            client.force_authenticate(other["user"])
            with patch.object(self.storage, "open", side_effect=AssertionError("Foreign actor opened bytes")):
                for url in (base, f"{base}numerique/", f"/media/{own['book'].ressource_numerique.name}"):
                    assert client.get(url).status_code == 403
            assert client.patch(base, {"licence_active": False}, format="json").status_code == 403
            assert (
                client.post(
                    "/api/v1/bibliotheque/livres/", {"titre": "Étranger", "auteurs": "Interdit"}, format="json"
                ).status_code
                == 403
            )
            with tenant_context(own["tenant"]):
                own["book"].refresh_from_db()
                assert own["book"].licence_active is True
                assert Livre.objects.count() == 1
