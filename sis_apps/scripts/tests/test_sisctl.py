import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from scripts import sisctl


class CardReferencePreflightTests(unittest.TestCase):
    def test_scans_both_variants_and_reports_duplicate_ids_without_references(self):
        queries = []

        def fake_compose(_configuration, *arguments, **_kwargs):
            self.assertEqual(arguments[:2], ("exec", "-T"))
            self.assertIn("-w", arguments)
            service = arguments[2]
            sql = arguments[-1]
            queries.append((service, sql))
            if "FROM pg_catalog.pg_namespace" in sql:
                schemas = "school_a\nschool_b\n" if service == "postgres-secondaire" else "campus_a\n"
                return SimpleNamespace(stdout=schemas)
            if '"school_a"."paiements_paiement"' in sql:
                return SimpleNamespace(stdout='{"count": 0, "samples": []}\n')
            if '"school_b"."paiements_paiement"' in sql:
                return SimpleNamespace(stdout='{"count": 1, "samples": [[17, 22]]}\n')
            return SimpleNamespace(stdout='{"count": 1, "samples": [[7, 9]]}\n')

        with patch.object(sisctl, "compose", side_effect=fake_compose):
            with self.assertRaises(ValueError) as error:
                sisctl.preflight_card_references({"SIS_MODE": "dual"})
        self.assertIn("secondaire/school_b: 1", str(error.exception))
        self.assertIn("superieur/campus_a: 1", str(error.exception))
        self.assertIn("17, 22", str(error.exception))
        self.assertIn("7, 9", str(error.exception))
        self.assertNotIn("pi_", str(error.exception))
        self.assertIn("statut IN ('valide', 'rembourse')", queries[1][1])
        self.assertIn("reference_externe <> ''", queries[1][1])
        self.assertIn('"campus_a"."paiements_paiementfrais"', queries[-1][1])
        self.assertEqual(len(queries), 5)

    def test_empty_database_and_no_conflicts_pass(self):
        def fake_compose(_configuration, *arguments, **_kwargs):
            if "FROM pg_catalog.pg_namespace" in arguments[-1]:
                return SimpleNamespace(stdout="existing_tenant\n" if arguments[2] == "postgres-secondaire" else "")
            return SimpleNamespace(stdout='{"count": 0, "samples": []}\n')

        with patch.object(sisctl, "compose", side_effect=fake_compose):
            sisctl.preflight_card_references({"SIS_MODE": "dual"})

    def test_database_read_failure_is_not_treated_as_clean(self):
        with patch.object(
            sisctl, "compose",
            side_effect=subprocess.CalledProcessError(1, ["psql"]),
        ):
            with self.assertRaisesRegex(ValueError, "No migration was attempted"):
                sisctl.preflight_card_references({"SIS_MODE": "secondaire"})

    def test_init_aborts_before_bootstrap_on_duplicate_refs(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            institution = Path(directory) / "institution.json"
            institution.write_text(json.dumps({"schema_name": "school_a"}), encoding="utf-8")
            calls = []

            def fake_compose(_configuration, *arguments, **_kwargs):
                calls.append(arguments)
                if "FROM pg_catalog.pg_namespace" in arguments[-1]:
                    return SimpleNamespace(stdout="school_a\n")
                if arguments[:2] == ("exec", "-T"):
                    return SimpleNamespace(stdout='{"count": 1, "samples": [[17, 22]]}\n')
                return SimpleNamespace()

            with patch.object(sisctl, "compose", side_effect=fake_compose), patch.object(
                sisctl.getpass, "getpass", side_effect=AssertionError("Password prompt must not run"),
            ):
                with self.assertRaisesRegex(ValueError, "school_a"):
                    sisctl.initialize(
                        {"SIS_MODE": "secondaire"},
                        SimpleNamespace(variant="secondaire", institution=institution),
                    )

        self.assertEqual([call[:2] for call in calls[:3]], [
            ("config", "--quiet"), ("build", "api-secondaire"), ("up", "-d"),
        ])
        self.assertFalse(any(call[0] == "run" for call in calls))


if __name__ == "__main__":
    unittest.main()
