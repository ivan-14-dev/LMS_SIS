"""Offline contract tests of the load harness, never evidence of server capacity."""

# Stdlib unittest intentionally keeps this offline suite independent of pytest.
# ruff: noqa: PT009, PT027

import io
import json
import shutil
import sys
import time
import unittest
import uuid
from argparse import Namespace
from http.cookiejar import Cookie
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from urllib.request import Request

from sis_apps.load_tests import (
    cleanup_fixture_sessions,
    provision_fixture,
    run,
    sessions,
    tls_probe,
    transport_diagnostic,
)
from sis_apps.load_tests.safety import ConfigurationError, NoRedirects, check_isolation

TARGET = "http://secondaire.load.localhost:55285"


def fixture(users=2):
    return {
        "environment": {"id": "offline-fixture", "origin": TARGET, "isolated": True, "synthetic": True},
        "scenarios": {
            "teacher": {
                "roles": ["enseignant"],
                "steps": [
                    {"name": "read-note", "path": "/api/v1/notes/notes/{{note_id}}/", "equals": {"id": "{{note_id}}"}},
                    {
                        "name": "write-note", "method": "PATCH", "path": "/api/v1/notes/notes/{{note_id}}/",
                        "json": {"appreciation": "synthetic-{{run_id}}-{{iteration}}"},
                        "verify": {
                            "path": "/api/v1/notes/notes/{{note_id}}/",
                            "equals": {"id": "{{note_id}}", "appreciation": "synthetic-{{run_id}}-{{iteration}}"},
                        },
                    },
                    {"name": "denied-note", "path": "/api/v1/notes/notes/99999/", "status": 403, "negative": True},
                ],
            },
        },
        "accounts": [
            {
                "synthetic": True, "username": f"synthetic-{index}", "password": f"NEVER-LOG-SECRET-{index}",
                "role": "enseignant", "user_id": index + 1, "tenant_id": 1, "scenario": "teacher",
                "variables": {"note_id": index + 1},
                "owned_resources": ["/api/v1/notes/notes/{{note_id}}/"],
            }
            for index in range(users)
        ],
    }


def options(users=2):
    return Namespace(
        target=TARGET, users=users, ramp_seconds=0.01, duration_seconds=0.04, timeout=0.1,
        startup_timeout_seconds=1, cleanup_timeout_seconds=1, think_seconds=0.002, max_p95_ms=1000,
    )


class Response(io.BytesIO):
    def __init__(self, data, status=200):
        super().__init__(json.dumps(data).encode())
        self.code = status


class MemoryServer:
    """Deliberately small fake transport: tests orchestration, not SIS semantics."""

    def __init__(
        self, seed, failure_status=None, lose_write=False, login_failure=False, duplicate_cookie=False,
        failure_user=None, write_transport_failure=False, auxiliary_cookie=False, missing_session_cookie=False,
        final_readback_failure=False,
    ):
        self.accounts = {account["username"]: account for account in seed["accounts"]}
        self.notes = {account["variables"]["note_id"]: {"id": account["variables"]["note_id"], "appreciation": ""}
                      for account in seed["accounts"]}
        self.failure_status, self.lose_write = failure_status, lose_write
        self.login_failure, self.duplicate_cookie = login_failure, duplicate_cookie
        self.failure_user, self.write_transport_failure = failure_user, write_transport_failure
        self.auxiliary_cookie, self.missing_session_cookie = auxiliary_cookie, missing_session_cookie
        self.final_readback_failure = final_readback_failure
        self.clients = []
        self.requests = []

    def opener(self, handler):
        client = MemoryTransport(self, handler.cookiejar)
        self.clients.append(client)
        return client


class MemoryTransport:
    def __init__(self, server, cookies):
        self.server, self.cookies = server, cookies
        self.account = None
        self.csrf = "before-login"

    def open(self, request, timeout):
        path, method = request.selector, request.method
        self.server.requests.append((path, method, bool(self.account)))
        if path == "/csrf/api/v1/token":
            return Response({"csrfToken": self.csrf})
        if method != "GET":
            assert request.get_header("X-csrftoken") == self.csrf
        if path == sessions.SESSION_PATH:
            if method == "POST":
                credentials = json.loads(request.data)
                self.account = self.server.accounts[credentials["username"]]
                assert credentials["password"] == self.account["password"]
                if self.server.login_failure and self.account["user_id"] == 2:
                    self.account = None
                    return Response({"detail": "NEVER-LOG-RESPONSE"}, 401)
                self.csrf = "after-login"
                value = "duplicate" if self.server.duplicate_cookie else self.account["username"]
                cookies = []
                if not self.server.missing_session_cookie:
                    cookies.append(("sessionid", value))
                if self.server.auxiliary_cookie:
                    cookies.append(("visitor", self.account["username"]))
                for name, cookie_value in cookies:
                    self.cookies.set_cookie(Cookie(
                        0, name, cookie_value, None, False, "secondaire.load.localhost", False, False,
                        "/", True, False, None, True, None, None, {}, False,
                    ))
            elif method == "DELETE":
                self.account = None
                self.cookies.clear()
            return Response({
                "authenticated": bool(self.account),
                **({key: self.account[key] for key in ("username", "role")} if self.account else {}),
            })
        if not self.account:
            return Response({"detail": "unauthorized"}, 401)
        if path == sessions.IDENTITY_PATH:
            return Response({
                "id": self.account["user_id"], "username": self.account["username"], "role": self.account["role"],
                "etablissement": self.account["tenant_id"], "is_active": True,
            })
        if path == "/api/v1/notes/notes/99999/":
            return Response({"detail": "NEVER-LOG-RESPONSE"}, 403)
        if self.server.failure_status and self.server.failure_user in (None, self.account["user_id"]):
            return Response({"detail": "NEVER-LOG-RESPONSE"}, self.server.failure_status)
        note_id = int(path.rstrip("/").split("/")[-1])
        assert note_id == self.account["variables"]["note_id"]
        if method == "GET" and self.server.final_readback_failure and self.server.notes[note_id]["appreciation"]:
            raise URLError(TimeoutError("The read operation timed out NEVER-LOG-TRANSPORT"))
        if method == "PATCH" and not self.server.lose_write:
            self.server.notes[note_id].update(json.loads(request.data))
        if method == "PATCH" and self.server.write_transport_failure:
            raise URLError(TimeoutError("The read operation timed out NEVER-LOG-TRANSPORT"))
        return Response(self.server.notes[note_id])


class HarnessTests(unittest.TestCase):
    def test_transport_diagnostic_refuses_business_scale_and_foreign_targets(self):
        seed = fixture()
        target = "https://load-secondaire.localhost:60031"
        seed["environment"].update(id="sis-load-d0c25c75", origin=target)
        args = Namespace(target=target, acknowledge_isolated_target=target,
                         clients=32, requests_per_client=4, timeout=5, max_p95_ms=2000)
        self.assertEqual(transport_diagnostic.validate(args, seed), target)
        for name, value in (("clients", 500), ("requests_per_client", 5), ("timeout", 6),
                            ("max_p95_ms", 2001), ("target", TARGET), ("acknowledge_isolated_target", "")):
            changed = Namespace(**vars(args))
            setattr(changed, name, value)
            with self.subTest(name=name), self.assertRaises(ConfigurationError):
                transport_diagnostic.validate(changed, seed)

    def test_transport_trace_preserves_context_and_errors_without_logging_exception_text(self):
        import ssl
        from types import SimpleNamespace

        context = ssl.create_default_context()
        state = SimpleNamespace(row={})

        class Connection:
            def __init__(self, *, context):
                self._context = context
                self._create_connection = lambda: None

            def connect(self):
                self._create_connection()

            def request(self):
                self.connect()

            def getresponse(self):
                raise TimeoutError("NEVER-LOG-SECRET")

        with patch.object(transport_diagnostic.http.client, "HTTPSConnection", Connection), patch(
            "socket.socket", side_effect=AssertionError("No offline network"),
        ):
            traced = transport_diagnostic.traced_connection_class(state)(context=context)
            traced.request()
            with self.assertRaises(TimeoutError):
                traced.getresponse()
        self.assertIs(traced._context, context)
        self.assertTrue(state.row["verification_required"])
        self.assertIn("dns_tcp_ms", state.row)
        self.assertIn("tls_ms", state.row)
        self.assertIn("response_headers_ms", state.row)
        self.assertNotIn("NEVER-LOG", json.dumps(state.row))

    def test_transport_dispatch_instruments_without_replacing_stdlib_connection_class(self):
        import ssl
        from types import SimpleNamespace
        from urllib.request import HTTPSHandler

        context = ssl.create_default_context()
        state = SimpleNamespace(row={})
        original = transport_diagnostic.http.client.HTTPSConnection

        def construct_only(handler, connection_class, request, **kwargs):
            return connection_class(request.host, timeout=5, **kwargs)

        with patch.object(HTTPSHandler, "do_open", construct_only), transport_diagnostic.trace_https(state), patch(
            "socket.socket", side_effect=AssertionError("No offline network"),
        ):
            connection = HTTPSHandler(context=context).https_open(Request("https://load-secondaire.localhost:60031"))
            self.assertIs(transport_diagnostic.http.client.HTTPSConnection, original)
        self.assertIs(connection._context, context)
        self.assertTrue(state.row["verification_required"])

    def test_cleanup_requires_exact_preserved_synthetic_owners(self):
        seed = fixture(500)
        evidence = {"remaining_session_user_indices": list(range(218)), "counts": {"session_rows_remaining": 218}}
        cleanup_fixture_sessions.verify_session_owners(seed, evidence, list(range(1, 219)))
        for owners in (list(range(1, 218)), list(range(1, 220)), [99999] + list(range(2, 219)),
                       [2] + list(range(2, 219)), [None] + list(range(2, 219))):
            with self.subTest(count=len(owners)), self.assertRaises(ValueError):
                cleanup_fixture_sessions.verify_session_owners(seed, evidence, owners)
        seed["accounts"][0]["synthetic"] = False
        with self.assertRaises(ValueError):
            cleanup_fixture_sessions.verify_session_owners(seed, evidence, list(range(1, 219)))

    def test_tls_probe_requires_named_https_isolation_and_fixed_budget(self):
        seed = fixture()
        target = "https://load-secondaire.localhost:60031"
        seed["environment"].update(id="sis-load-d0c25c75", origin=target)
        args = Namespace(target=target, acknowledge_isolated_target=target,
                         connections=500, timeout=5, max_p95_ms=2000)
        self.assertEqual(tls_probe.validate_configuration(args, seed).hostname, "load-secondaire.localhost")
        for name, value in (("connections", 501), ("connections", 0), ("timeout", 11),
                            ("max_p95_ms", 2001), ("acknowledge_isolated_target", ""), ("target", TARGET)):
            with self.subTest(name=name, value=value):
                changed = Namespace(**vars(args))
                setattr(changed, name, value)
                with self.assertRaises(ConfigurationError):
                    tls_probe.validate_configuration(changed, seed)

    def test_tls_probe_retains_distinct_sockets_without_http_or_secret_errors(self):
        seed = fixture()
        target = "https://load-secondaire.localhost:60031"
        seed["environment"].update(id="sis-load-d0c25c75", origin=target)
        args = Namespace(target=target, acknowledge_isolated_target=target,
                         connections=2, timeout=5, max_p95_ms=2000, ca_file="unused")
        sockets = []

        class Socket:
            def __init__(self, *unused):
                self.closed = False
                sockets.append(self)

            def settimeout(self, timeout):
                pass

            def connect(self, address):
                assert address == ("127.0.0.1", 60031)

            def do_handshake(self):
                self.assert_open = all(not item.closed for item in sockets)

            def close(self):
                self.closed = True

        with patch.object(tls_probe.ssl, "create_default_context") as context, patch.object(
            tls_probe.socket, "getaddrinfo", return_value=[
                (10, 1, 6, "", ("::1", 60031, 0, 0)), (2, 1, 6, "", ("127.0.0.1", 60031)),
            ],
        ), patch.object(tls_probe.socket, "socket", Socket):
            context.return_value.wrap_socket.side_effect = lambda sock, **unused: sock
            report = tls_probe.probe(args, seed)
            self.assertTrue(report["passed"])
            self.assertEqual(report["simultaneous_verified_tls_sockets_retained"], 2)
            self.assertEqual(report["http_requests"], 0)
            self.assertTrue(all(item.closed and item.assert_open for item in sockets))
            context.return_value.wrap_socket.side_effect = TimeoutError("NEVER-LOG-SECRET")
            report = tls_probe.probe(args, seed)
            self.assertFalse(report["passed"])
            self.assertEqual(report["errors"], {"tls:TimeoutError": 2})
            self.assertNotIn("NEVER-LOG", json.dumps(report))

    def test_fixture_provisioning_refuses_an_unbound_or_foreign_database_before_django(self):
        for environment in ({}, {"SIS_LOAD_FIXTURE": "sis-load-d0c25c75", "DB_HOST": "active-database"}):
            with self.subTest(environment=environment), patch.dict("os.environ", environment, clear=True):
                with self.assertRaises(SystemExit) as failure:
                    provision_fixture.main()
                self.assertIn("restricted to the named disposable fixture", str(failure.exception))

    def campaign(self, seed=None, **server_options):
        seed = seed or fixture()
        sessions.validate_seed(seed, len(seed["accounts"]))
        server = MemoryServer(seed, **server_options)
        with patch.object(sessions, "opener", server.opener), patch(
            "socket.socket", side_effect=AssertionError("Offline harness test must not open sockets"),
        ):
            report = sessions.run_campaign(options(len(seed["accounts"])), seed)
        return report, server

    def test_independent_sessions_csrf_rotation_writes_negatives_final_integrity_and_logout(self):
        report, server = self.campaign()
        self.assertTrue(report["passed"], report["checks"])
        self.assertEqual(report["peak_authenticated_sessions"], 2)
        self.assertEqual(report["full_cohort_seconds"], 0.04)
        self.assertGreater(report["metrics"]["expected_denials"], 0)
        self.assertEqual(report["metrics"]["failures"], 0)
        self.assertEqual(report["data_integrity"]["checks_failed"], 0)
        self.assertGreaterEqual(report["data_integrity"]["checks_passed"], 4)
        self.assertEqual(len({id(client.cookies) for client in server.clients}), 2)
        self.assertTrue(all(not list(client.cookies) for client in server.clients))
        self.assertEqual(sum(path == sessions.IDENTITY_PATH and not authenticated
                             for path, _, authenticated in server.requests), 2)
        self.assertNotIn("NEVER-LOG", json.dumps(report))
        self.assertNotIn("synthetic-0", json.dumps(report))

    def test_unexpected_http_errors_are_not_suppressed(self):
        for status in (401, 403, 404, 429, 500, 503):
            with self.subTest(status=status):
                report, _ = self.campaign(failure_status=status)
                self.assertFalse(report["passed"])
                self.assertGreater(report["metrics"]["failures"], 0)
                self.assertIn(str(status), report["metrics"]["statuses"])
                self.assertNotIn("NEVER-LOG", json.dumps(report))

    def test_successful_http_write_without_persistence_fails_integrity(self):
        report, _ = self.campaign(lose_write=True)
        self.assertFalse(report["passed"])
        self.assertEqual(report["data_integrity"]["checks_failed"], 2)
        self.assertTrue(any(step["reasons"].get("assertion_failed") for step in report["metrics"]["steps"]))

    def test_unconfirmed_write_is_indeterminate_not_corruption_and_never_a_pass(self):
        for lose_write in (False, True):
            with self.subTest(lose_write=lose_write):
                report, _ = self.campaign(write_transport_failure=True, lose_write=lose_write)
                self.assertFalse(report["passed"])
                self.assertFalse(report["checks"]["final_integrity_passed"])
                self.assertEqual(report["data_integrity"]["checks_failed"], 0)
                self.assertEqual(report["data_integrity"]["checks_indeterminate"], 2)
                self.assertEqual(report["data_integrity"]["unconfirmed_writes"], 2)
                self.assertEqual(report["data_integrity"]["unconfirmed_matches"], 0 if lose_write else 2)
                self.assertEqual(report["data_integrity"]["unconfirmed_differs"], 2 if lose_write else 0)
                reason = (
                    "unconfirmed_write_differs_from_expected" if lose_write
                    else "unconfirmed_write_matches_expected"
                )
                self.assertTrue(any(step["reasons"].get(reason)
                                    for step in report["metrics"]["steps"]))
                self.assertNotIn("NEVER-LOG", json.dumps(report))

    def test_unavailable_uncertain_write_readback_is_not_reported_as_observed(self):
        report, _ = self.campaign(write_transport_failure=True, final_readback_failure=True)
        self.assertFalse(report["passed"])
        self.assertEqual(report["data_integrity"]["unconfirmed_writes"], 2)
        self.assertEqual(report["data_integrity"]["checks_indeterminate"], 2)
        self.assertEqual(report["data_integrity"]["unconfirmed_matches"], 0)
        self.assertEqual(report["data_integrity"]["unconfirmed_differs"], 0)
        self.assertTrue(any(
            step["phase"] == "integrity" and step["name"] == "write-note-final-readback"
            and step["reasons"].get("transport_error") == 2
            for step in report["metrics"]["steps"]
        ))
        self.assertNotIn("NEVER-LOG", json.dumps(report))

    def test_failed_user_waits_for_all_business_traffic_before_final_checks(self):
        seed = fixture()
        sessions.validate_seed(seed, 2)
        server = MemoryServer(seed, failure_status=503, failure_user=1)
        events = []

        class RecordingClient(sessions.Client):
            def request(self, *args, **kwargs):
                events.append((self.phase, time.monotonic()))
                return super().request(*args, **kwargs)

        with patch.object(sessions, "opener", server.opener):
            report = sessions.run_campaign(options(), seed, client_factory=RecordingClient)
        self.assertFalse(report["passed"])
        self.assertGreater(report["users"][1]["cycles"], 0)
        self.assertLessEqual(max(at for phase, at in events if phase == "load"),
                             min(at for phase, at in events if phase == "integrity"))
        self.assertLess(report["full_cohort_seconds"], report["configuration"]["duration_seconds"])

    def test_transport_diagnostics_distinguish_safe_categories_without_logging_exceptions(self):
        cases = [
            (URLError(TimeoutError("handshake operation timed out NEVER-LOG")), "tls_handshake_timeout"),
            (TimeoutError("read operation timed out NEVER-LOG"), "response_read_timeout"),
            (URLError(ConnectionRefusedError("NEVER-LOG")), "connection_refused"),
        ]
        for error, category in cases:
            with self.subTest(category=category), patch.object(sessions, "opener") as factory:
                factory.return_value.open.side_effect = error
                stats = sessions.Stats()
                client = sessions.Client(TARGET, 1, fixture(1)["accounts"][0], 0, stats)
                with self.assertRaises(sessions.ScenarioFailure):
                    client.request("read", "/api/v1/notes/notes/1/")
                summary = stats.summary(1)
                self.assertEqual(summary["steps"][0]["transport_errors"],
                                 {f"connect_tls_or_headers:{category}": 1})
                self.assertNotIn("NEVER-LOG", json.dumps(summary))

    def test_unconfirmed_write_does_not_mask_a_wrong_record_id(self):
        with patch.object(sessions, "opener") as factory:
            factory.return_value.open.return_value = Response({"id": 2})
            client = sessions.Client(TARGET, 1, fixture(1)["accounts"][0], 0, sessions.Stats())
            with self.assertRaises(sessions.ScenarioFailure) as failure:
                client.request("final-readback", "/api/v1/notes/notes/1/", equals={"id": 1}, unconfirmed_write=True)
            self.assertEqual(str(failure.exception), "assertion_failed")
            factory.return_value.open.return_value = Response({"id": 2})
            with self.assertRaises(sessions.ScenarioFailure) as failure:
                client.request("final-readback", "/api/v1/notes/notes/1/", unconfirmed_write=True)
            self.assertEqual(str(failure.exception), "unconfirmed_write_outcome")

    def test_failed_auth_aborts_cohort_before_business_requests(self):
        report, server = self.campaign(login_failure=True)
        self.assertFalse(report["checks"]["entire_cohort_authenticated"])
        self.assertEqual(report["business_cycles"], 0)
        self.assertFalse(any("/notes/" in path for path, _, _ in server.requests))
        self.assertTrue(all(client.account is None for client in server.clients))

    def test_duplicate_session_cookie_is_rejected(self):
        report, _ = self.campaign(duplicate_cookie=True)
        self.assertFalse(report["passed"])
        self.assertTrue(any("duplicate_session" in user["errors"] for user in report["users"]))

    def test_auxiliary_cookies_cannot_mask_shared_or_missing_auth_sessions(self):
        report, _ = self.campaign(duplicate_cookie=True, auxiliary_cookie=True)
        self.assertFalse(report["checks"]["entire_cohort_authenticated"])
        self.assertEqual(report["business_cycles"], 0)
        self.assertTrue(any("duplicate_session" in user["errors"] for user in report["users"]))

        report, _ = self.campaign(fixture(1), missing_session_cookie=True, auxiliary_cookie=True)
        self.assertFalse(report["checks"]["entire_cohort_authenticated"])
        self.assertEqual(report["business_cycles"], 0)
        self.assertIn("missing_session_cookie", report["users"][0]["errors"])

    def test_readback_supports_typed_values_captured_from_prior_response(self):
        seed = fixture(1)
        steps = seed["scenarios"]["teacher"]["steps"]
        steps[0]["capture"] = {"saved_id": "id"}
        steps[1]["verify"]["equals"]["id"] = "{{saved_id}}"
        report, _ = self.campaign(seed)
        self.assertTrue(report["passed"])

    def test_capture_is_updated_after_write_before_integrity_assertions(self):
        seed = fixture(1)
        steps = seed["scenarios"]["teacher"]["steps"]
        steps[0]["capture"] = {"saved_feedback": "appreciation"}
        steps[1]["capture"] = {"saved_feedback": "appreciation"}
        steps[1]["verify"]["equals"]["appreciation"] = "{{saved_feedback}}"
        report, _ = self.campaign(seed)
        self.assertTrue(report["passed"])

    def test_resource_exhaustion_produces_a_failed_machine_readable_report(self):
        seed = fixture(1)
        sessions.validate_seed(seed, 1)
        with patch.object(sessions.ThreadPoolExecutor, "submit", side_effect=RuntimeError("thread limit")):
            report = sessions.run_campaign(options(1), seed)
        self.assertFalse(report["passed"])
        self.assertEqual(report["authenticated_users"], 0)
        self.assertIn("worker_capacity_or_harness_failure", report["users"][0]["errors"])
        json.dumps(report)

    def test_seed_rejects_recycled_accounts_shared_records_and_unsafe_scenarios(self):
        changes = [
            lambda seed: seed["accounts"][1].update(username=seed["accounts"][0]["username"]),
            lambda seed: seed["accounts"][1].update(user_id=1),
            lambda seed: seed["accounts"][1]["variables"].update(note_id=1),
            lambda seed: seed["accounts"][0].update(synthetic=False),
            lambda seed: seed["scenarios"]["teacher"].update(roles=["direction"]),
            lambda seed: seed["scenarios"]["teacher"]["steps"][0].update(path="https://elsewhere.invalid/api/v1/notes/"),
            lambda seed: seed["scenarios"]["teacher"]["steps"][0].update(path="/api/v1/../../admin/"),
            lambda seed: seed["scenarios"]["teacher"]["steps"][0].update(capture={"user_id": "id"}),
            lambda seed: seed["scenarios"]["teacher"]["steps"][0].update(capture={"note_id": "id"}),
            lambda seed: seed["scenarios"]["teacher"]["steps"][1]["verify"].update(equals={"id": 1}),
            lambda seed: seed["scenarios"]["teacher"]["steps"][1].update(path="/api/v1/notes/notes/77/"),
            lambda seed: seed["scenarios"]["teacher"]["steps"][2].update(status=500),
            lambda seed: seed["scenarios"]["teacher"]["steps"][2].update(negative=False),
            lambda seed: seed["scenarios"]["teacher"]["steps"][2].update(negative="yes"),
        ]
        for change in changes:
            with self.subTest(change=changes.index(change)):
                seed = fixture()
                change(seed)
                with self.assertRaises(ConfigurationError):
                    sessions.validate_seed(seed, 2)

    def test_500_distinct_seed_accounts_validate_offline_with_multiple_roles(self):
        seed = fixture(500)
        seed["scenarios"]["teacher"]["roles"].append("direction")
        seed["accounts"][0]["role"] = "direction"
        self.assertEqual(len(sessions.validate_seed(seed, 500)), 500)
        seed["accounts"][0]["role"] = "enseignant"
        with self.assertRaises(ConfigurationError):
            sessions.validate_seed(seed, 500)

    def test_redirect_handler_never_follows_location(self):
        self.assertIsNone(NoRedirects().redirect_request(
            Request(TARGET), None, 302, "redirect", {}, "http://sis.validation.localhost:58623/",
        ))

    def test_client_counts_redirect_invalid_json_and_unexpected_negative_success(self):
        for status, body, negative in ((302, b"", False), (200, b"html", False), (200, b"{}", True)):
            with self.subTest(status=status, body=body):
                response = HTTPError(TARGET, status, "", {}, io.BytesIO(body))
                with patch.object(sessions, "opener") as factory:
                    factory.return_value.open.side_effect = response
                    stats = sessions.Stats()
                    client = sessions.Client(TARGET, 1, fixture(1)["accounts"][0], 0, stats)
                    with self.assertRaises(sessions.ScenarioFailure):
                        client.request("read", "/api/v1/notes/notes/1/", status=403 if negative else 200, negative=negative)
                    self.assertEqual(stats.summary(1)["failures"], 1)

    def test_isolation_refuses_active_targets_alias_ports_and_missing_attestations(self):
        seed = fixture()
        for target in (
            "http://sis.validation.localhost:55285", "http://127.0.0.1:58623",
            "http://alias.localhost:59080", "http://alias.localhost:59082",
            "http://user:password@secondaire.load.localhost:55285", "http://remote.invalid",
        ):
            with self.subTest(target=target), self.assertRaises(ConfigurationError):
                check_isolation(target, target, seed)
        for acknowledgement in ("", "http://other.localhost:55285"):
            with self.assertRaises(ConfigurationError):
                check_isolation(TARGET, acknowledgement, seed)
        seed["environment"]["isolated"] = False
        with self.assertRaises(ConfigurationError):
            check_isolation(TARGET, TARGET, seed)

    def test_cli_validation_is_offline_and_legacy_also_refuses_without_acknowledgement(self):
        root = Path("sis_apps/load_tests/.test-artifacts") / uuid.uuid4().hex
        root.mkdir(parents=True)
        try:
            seed_file, output = root / "seed.json", root / "summary.json"
            seed_file.write_text(json.dumps(fixture()), encoding="utf-8")
            seed_file.chmod(0o600)
            arguments = [
                "--target", TARGET, "--acknowledge-isolated-target", TARGET,
                "--seed", str(seed_file), "--users", "2", "--output", str(output), "--validate-only",
            ]
            with patch.object(sessions, "opener") as factory, patch("sys.stdout", new_callable=io.StringIO):
                self.assertEqual(sessions.main(arguments), 0)
                factory.assert_not_called()
            self.assertEqual(json.loads(output.read_text())["network_requests"], 0)
            seed_file.chmod(0o644)
            with patch("sys.stderr", new_callable=io.StringIO), self.assertRaises(SystemExit) as failure:
                sessions.main(arguments)
            self.assertEqual(failure.exception.code, 2)
            with patch.object(sys, "argv", ["run.py", "exam-list", "--url", TARGET + "/api/v1/notes/notes/"]):
                with patch("sys.stderr", new_callable=io.StringIO), self.assertRaises(SystemExit) as failure:
                    run.main()
                self.assertEqual(failure.exception.code, 2)
        finally:
            shutil.rmtree(root)
            try:
                root.parent.rmdir()
            except OSError:
                pass

    def test_cli_active_target_and_invalid_bounds_are_rejected_without_network(self):
        arguments = [
            "--target", "http://alias.localhost:58623",
            "--acknowledge-isolated-target", "http://alias.localhost:58623",
            "--seed", "not-read-from-disk.json", "--output", "not-written.json",
        ]
        with patch.object(sessions, "read_seed", return_value=fixture()), patch.object(sessions, "opener") as factory:
            for extra in ([], ["--duration-seconds", "nan"], ["--users", "501"], ["--ramp-seconds", "0"]):
                with self.subTest(extra=extra), patch("sys.stderr", new_callable=io.StringIO):
                    with self.assertRaises(SystemExit) as failure:
                        sessions.main(arguments + extra)
                    self.assertEqual(failure.exception.code, 2)
            factory.assert_not_called()

    def test_legacy_modes_refuse_live_target_even_with_an_acknowledgement(self):
        forbidden = "http://alias.localhost:58623"
        arguments = [
            "run.py", "exam-list", "--url", forbidden + "/api/v1/notes/notes/",
            "--acknowledge-isolated-target", forbidden, "--seed", "not-read-from-disk.json",
        ]
        with patch.object(sys, "argv", arguments), patch.object(run, "read_seed", return_value=fixture()):
            with patch.object(run, "opener") as factory, patch("sys.stderr", new_callable=io.StringIO):
                with self.assertRaises(SystemExit) as failure:
                    run.main()
                self.assertEqual(failure.exception.code, 2)
                factory.assert_not_called()

    def test_checked_in_example_has_valid_scenarios_but_no_usable_credentials_or_attestation(self):
        seed = json.loads(Path("sis_apps/load_tests/seed.example.json").read_text())
        self.assertFalse(seed["environment"]["isolated"])
        with self.assertRaises(ConfigurationError):
            sessions.validate_seed(seed, 2)
        for account in seed["accounts"]:
            account["password"] = "offline-only-not-a-real-credential"
        sessions.validate_seed(seed, 2)

    def test_slow_ramp_up_to_two_hours_validates_offline_but_longer_is_rejected(self):
        root = Path("sis_apps/load_tests/.test-artifacts") / uuid.uuid4().hex
        root.mkdir(parents=True)
        try:
            seed = fixture(500)
            seed["scenarios"]["teacher"]["roles"].append("direction")
            seed["accounts"][0]["role"] = "direction"
            seed_file = root / "seed.json"
            seed_file.write_text(json.dumps(seed))
            seed_file.chmod(0o600)
            with patch.object(sessions, "opener") as factory:
                for ramp in (3600, 7200, 7201):
                    arguments = [
                        "--target", TARGET, "--acknowledge-isolated-target", TARGET, "--seed", str(seed_file),
                        "--output", str(root / f"validation-{ramp}.json"), "--ramp-seconds", str(ramp), "--validate-only",
                    ]
                    with patch("sys.stdout", new_callable=io.StringIO), patch("sys.stderr", new_callable=io.StringIO):
                        if ramp <= 7200:
                            self.assertEqual(sessions.main(arguments), 0)
                        else:
                            with self.assertRaises(SystemExit) as failure:
                                sessions.main(arguments)
                            self.assertEqual(failure.exception.code, 2)
                factory.assert_not_called()
        finally:
            shutil.rmtree(root)
            try:
                root.parent.rmdir()
            except OSError:
                pass


if __name__ == "__main__":
    unittest.main()
