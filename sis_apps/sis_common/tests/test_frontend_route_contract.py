import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase
from django.urls import resolve


class FrontendRouteContractTest(SimpleTestCase):
    def test_frontend_resource_hooks_resolve_to_collections_not_detail_routes(self):
        source = Path(__file__).resolve().parents[2] / "frontend-app-sis/src/services/api.js"
        for resource, variant in re.findall(r"createResourceHooks\('([^']+)', '([^']+)'\)", source.read_text()):
            if variant not in (settings.SIS_VARIANT, "admin"):
                continue
            with self.subTest(resource=resource):
                match = resolve(f"/api/v1/{resource}/")
                assert match.func.actions["get"] == "list"

    def test_explicit_collection_urls_resolve_to_list_actions(self):
        source = (Path(__file__).resolve().parents[2] / "frontend-app-sis/src/services/api.js").read_text()
        getter = "getSecondaireApiUrl" if settings.SIS_VARIANT == "secondaire" else "getSuperieurApiUrl"
        paths = re.findall(r"fetchCollection\(`\$\{" + getter + r"\(\)\}([^`]+)`", source)
        for path in paths:
            path = path.split("?")[0]
            if "${" in path:
                continue
            with self.subTest(path=path):
                assert resolve(f"/api/v1{path}").func.actions["get"] == "list"
