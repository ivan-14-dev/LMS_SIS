"""Bounded, independent local SIS cookie sessions; no application dependencies."""

import argparse
import hashlib
import http.client
import json
import math
import re
import ssl
import threading
import time
import uuid
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from http.cookiejar import CookieJar
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import HTTPCookieProcessor, Request

try:
    from .safety import ConfigurationError, api_path, check_isolation, opener, read_seed
except ImportError:
    from safety import ConfigurationError, api_path, check_isolation, opener, read_seed


SESSION_PATH = "/api/v1/auth/session/"
IDENTITY_PATH = "/api/v1/utilisateurs/comptes/me/"
VARIABLE = re.compile(r"\{\{([a-z][a-z0-9_]*)\}\}")
LABEL = re.compile(r"[a-z][a-z0-9_-]{0,47}")
RESERVED = {"username", "role", "user_id", "tenant_id", "iteration", "run_id"}


class ScenarioFailure(Exception):
    """Deliberately contains no response body, credentials, or remote error."""


def transport_category(error):
    cause = error.reason if isinstance(error, URLError) else error
    if isinstance(cause, ssl.SSLCertVerificationError):
        return "tls_verification"
    if isinstance(cause, TimeoutError):
        message = str(cause).lower()
        if "handshake" in message:
            return "tls_handshake_timeout"
        if "read" in message:
            return "response_read_timeout"
        return "socket_timeout"
    if isinstance(cause, ConnectionRefusedError):
        return "connection_refused"
    if isinstance(cause, ConnectionResetError):
        return "connection_reset"
    if isinstance(cause, ssl.SSLError):
        return "tls_error"
    return "network_or_protocol_error"


def render(value, context):
    if isinstance(value, str):
        match = VARIABLE.fullmatch(value)
        if match:
            return context[match[1]]
        return VARIABLE.sub(lambda match: str(context[match[1]]), value)
    if isinstance(value, list):
        return [render(item, context) for item in value]
    if isinstance(value, dict):
        return {key: render(item, context) for key, item in value.items()}
    return value


def field(data, path):
    for part in path.split("."):
        data = data[int(part)] if isinstance(data, list) else data[part]
    return data


def expect(data, expected):
    try:
        return all(field(data, path) == value for path, value in expected.items())
    except (KeyError, IndexError, TypeError, ValueError):
        return False


def context_for(account, run_id):
    return {
        **account["variables"],
        **{key: account[key] for key in ("username", "role", "user_id", "tenant_id")},
        "iteration": 0,
        "run_id": run_id,
    }


def validate_step(step, context, owned, names):
    if not isinstance(step, dict) or not LABEL.fullmatch(str(step.get("name", ""))):
        raise ConfigurationError("Every step needs a short non-sensitive slug name.")
    if step["name"] in names:
        raise ConfigurationError("Step names must be unique within a scenario.")
    names.add(step["name"])
    method = step.get("method", "GET")
    status = step.get("status", 200)
    negative = step.get("negative", False)
    if type(status) is not int or type(negative) is not bool:
        raise ConfigurationError("status must be an integer and negative must be a boolean.")
    if method not in ("GET", "POST", "PATCH", "PUT"):
        raise ConfigurationError("Scenario methods are limited to GET/POST/PATCH/PUT.")
    if negative:
        if negative is not True or method != "GET" or status not in (403, 404):
            raise ConfigurationError("Explicit negative cases must be GET with an exact 403 or 404.")
    elif status not in (200, 201, 204):
        raise ConfigurationError("Positive cases require an explicit successful status.")
    if method == "GET" and "json" in step:
        raise ConfigurationError("GET steps cannot have request bodies.")
    if (negative or status == 204) and step.get("capture"):
        raise ConfigurationError("Denials and empty responses cannot provide captured variables.")
    path = api_path(render(step["path"], context))
    if not isinstance(step.get("equals", {}), dict) or not isinstance(step.get("capture", {}), dict):
        raise ConfigurationError("equals and capture must be objects.")
    render(step.get("json"), context)
    render(step.get("equals", {}), context)
    if method != "GET":
        if negative or not isinstance(step.get("json"), dict):
            raise ConfigurationError("Writes require a JSON object.")
        verify = step.get("verify", {})
        verify_path = api_path(render(verify["path"], context))
        if verify_path not in owned or not path.startswith(verify_path):
            raise ConfigurationError("Writes and read-back must stay within an exclusively owned seeded record.")
        expected = render(verify.get("equals", {}), context)
        if not isinstance(expected, dict) or "id" not in expected or len(expected) < 2:
            raise ConfigurationError("Write read-back must assert the record id and at least one persisted field.")
        if "?" in path or "?" in verify_path:
            raise ConfigurationError("Write ownership paths cannot contain a query.")
    for name, response_field in step.get("capture", {}).items():
        if not re.fullmatch(r"[a-z][a-z0-9_]{0,47}", name) or name in RESERVED or name in context.get("_fixture_variables", ()):
            raise ConfigurationError("Captures cannot replace identity or fixture variables.")
        if not isinstance(response_field, str) or not response_field:
            raise ConfigurationError("Captures need a dotted JSON field path.")
        context[name] = 1


def validate_seed(seed, users):
    accounts = seed.get("accounts")
    scenarios = seed.get("scenarios")
    if not isinstance(accounts, list) or len(accounts) != users or not isinstance(scenarios, dict):
        raise ConfigurationError("Provide exactly --users accounts and a scenarios object; no account recycling.")
    seen_usernames, seen_ids, seen_resources, selected_roles = set(), set(), set(), set()
    try:
        for account in accounts:
            if not isinstance(account, dict) or account.get("synthetic") is not True:
                raise ConfigurationError("Every account must be explicitly synthetic.")
            if not all(
                isinstance(account.get(key), str) and 0 < len(account[key]) <= 512
                for key in ("username", "password", "role")
            ):
                raise ConfigurationError("Each account needs nonempty username, password and role.")
            if not LABEL.fullmatch(account["role"]):
                raise ConfigurationError("Role must be a short non-sensitive slug.")
            if not all(type(account.get(key)) is int and account[key] > 0 for key in ("user_id", "tenant_id")):
                raise ConfigurationError("Each account needs positive numeric user_id and tenant_id.")
            if account["username"].casefold() in seen_usernames or account["user_id"] in seen_ids:
                raise ConfigurationError("Each virtual user needs a different username and SIS user id.")
            seen_usernames.add(account["username"].casefold())
            seen_ids.add(account["user_id"])
            selected_roles.add(account["role"])
            variables = account.get("variables", {})
            if (
                not isinstance(variables, dict)
                or RESERVED.intersection(variables)
                or any(not re.fullmatch(r"[a-z][a-z0-9_]{0,47}", key) for key in variables)
                or any(
                    not isinstance(value, (str, int, float, bool))
                    or (isinstance(value, float) and not math.isfinite(value))
                    or len(str(value)) > 512
                    for value in variables.values()
                )
            ):
                raise ConfigurationError("Account variables must be scalar values, not reserved identity names.")
            account["variables"] = variables
            context = context_for(account, "validation")
            context["_fixture_variables"] = set(variables)
            resources = account.get("owned_resources", [])
            if not isinstance(resources, list):
                raise ConfigurationError("owned_resources must be a list.")
            owned = [api_path(render(path, context)) for path in resources]
            for path in owned:
                if (
                    not path.endswith("/")
                    or "?" in path
                    or not re.fullmatch(r"(?:[1-9][0-9]*|[0-9a-fA-F-]{36})", path.split("/")[-2])
                    or any(path.startswith(other) or other.startswith(path) for other in seen_resources)
                ):
                    raise ConfigurationError("Seeded write records must be uniquely owned, concrete detail paths.")
                seen_resources.add(path)
            scenario = scenarios[account["scenario"]]
            if not LABEL.fullmatch(account["scenario"]) or account["role"] not in scenario["roles"]:
                raise ConfigurationError("Scenario must explicitly permit the account's role.")
            steps = scenario["steps"]
            if not isinstance(steps, list) or not 1 <= len(steps) <= 12:
                raise ConfigurationError("Each scenario needs 1–12 bounded steps.")
            names = set()
            for step in steps:
                validate_step(step, context, owned, names)
            if not any(step.get("method", "GET") == "GET" and not step.get("negative") for step in steps):
                raise ConfigurationError("Every scenario needs a positive business read.")
        if users >= 500 and len(selected_roles) < 2:
            raise ConfigurationError("A 500-session qualification must exercise at least two roles.")
        used = {account["scenario"] for account in accounts}
        if not any(step.get("method", "GET") != "GET" for name in used for step in scenarios[name]["steps"]):
            raise ConfigurationError("Campaign must exercise at least one verified business write.")
    except (KeyError, TypeError, AttributeError, ValueError) as exc:
        if isinstance(exc, ConfigurationError):
            raise
        raise ConfigurationError("Invalid seed structure, placeholder, scenario, or verification.") from None
    return accounts


class Stats:
    def __init__(self, progress=None):
        self.lock = threading.Lock()
        self.progress = progress
        self.groups = {}
        self.inflight = self.peak_inflight = 0
        self.authenticated = self.peak_authenticated = 0
        self.session_fingerprints = set()
        self.authenticated_total = 0
        self.first_departure = None
        self.last_departure = None
        self.samples = []

    def enter(self):
        with self.lock:
            self.inflight += 1
            self.peak_inflight = max(self.peak_inflight, self.inflight)

    def record(self, phase, role, name, status, elapsed_ms, reason, negative, index, transport_error=None):
        with self.lock:
            self.inflight -= 1
            key = (phase, role, name)
            group = self.groups.setdefault(key, {
                "count": 0, "failures": 0, "expected_denials": 0,
                "statuses": Counter(), "reasons": Counter(), "histogram": Counter(),
                "transport_errors": Counter(),
                "sum_ms": 0, "max_ms": 0,
            })
            group["count"] += 1
            group["failures"] += bool(reason)
            group["expected_denials"] += bool(negative and not reason)
            group["statuses"][str(status)] += 1
            if reason:
                group["reasons"][reason] += 1
                if transport_error:
                    group["transport_errors"][transport_error] += 1
                if len(self.samples) < 20:
                    self.samples.append({
                        "user_index": index, "step": name, "phase": phase, "reason": reason, "status": status,
                        **({"transport_error": transport_error} if transport_error else {}),
                    })
            group["histogram"][math.ceil(elapsed_ms)] += 1
            group["sum_ms"] += elapsed_ms
            group["max_ms"] = max(group["max_ms"], elapsed_ms)

    def joined(self, fingerprint):
        with self.lock:
            if fingerprint in self.session_fingerprints:
                return False
            self.session_fingerprints.add(fingerprint)
            self.authenticated += 1
            self.authenticated_total += 1
            self.peak_authenticated = max(self.peak_authenticated, self.authenticated)
            if self.progress:
                self.progress({"phase": "authentication", "authenticated_users": self.authenticated_total})
            return True

    def departed(self):
        with self.lock:
            self.authenticated -= 1

    def workload_departure(self):
        with self.lock:
            self.last_departure = time.monotonic()
            if self.first_departure is None:
                self.first_departure = self.last_departure

    @staticmethod
    def latency(groups):
        histogram = Counter()
        count = sum(group["count"] for group in groups)
        for group in groups:
            histogram.update(group["histogram"])
        def quantile(fraction):
            seen = 0
            for value, frequency in sorted(histogram.items()):
                seen += frequency
                if seen >= math.ceil(count * fraction):
                    return value
            return 0
        return {
            "mean": round(sum(group["sum_ms"] for group in groups) / count, 2) if count else 0,
            "p50": quantile(0.5), "p95": quantile(0.95), "p99": quantile(0.99),
            "max": round(max((group["max_ms"] for group in groups), default=0), 2),
        }

    def summary(self, load_seconds):
        groups = list(self.groups.values())
        load = [value for key, value in self.groups.items() if key[0] == "load"]
        requests = sum(group["count"] for group in groups)
        failures = sum(group["failures"] for group in groups)
        statuses = Counter()
        for group in groups:
            statuses.update(group["statuses"])
        return {
            "requests": requests,
            "failures": failures,
            "success_rate": round((requests - failures) / requests, 6) if requests else 0,
            "statuses": dict(statuses),
            "expected_denials": sum(group["expected_denials"] for group in groups),
            "load_requests_per_second": round(sum(group["count"] for group in load) / load_seconds, 2) if load_seconds else 0,
            "load_successful_requests_per_second": (
                round(sum(group["count"] - group["failures"] for group in load) / load_seconds, 2)
                if load_seconds else 0
            ),
            "load_latency_ms": self.latency(load),
            "all_phases_latency_ms": self.latency(groups),
            "peak_inflight_http_requests": self.peak_inflight,
            "failure_samples": self.samples,
            "steps": [
                {
                    "phase": phase, "role": role, "name": name,
                    **{key: value[key] for key in (
                        "count", "failures", "expected_denials", "statuses", "reasons", "transport_errors",
                    )},
                    "latency_ms": self.latency([value]),
                }
                for (phase, role, name), value in sorted(self.groups.items())
            ],
        }


class Client:
    def __init__(self, target, timeout, account, index, stats):
        self.target, self.timeout = target, timeout
        self.account, self.index, self.stats = account, index, stats
        self.cookies = CookieJar()
        self.http = opener(HTTPCookieProcessor(self.cookies))
        self.csrf = ""
        self.phase = "authentication"
        self.deadline = float("inf")

    def request(
        self, name, path, method="GET", body=None, status=200, equals=None, capture=None,
        negative=False, unconfirmed_write=False,
    ):
        started = time.monotonic()
        self.stats.enter()
        actual_status, reason, data = 0, "", None
        stage, transport_error = "connect_tls_or_headers", None
        try:
            remaining = self.deadline - started
            if remaining <= 0:
                raise TimeoutError()
            headers = {"Accept": "application/json", "Referer": self.target + "/", "Origin": self.target}
            if method != "GET":
                headers.update({"Content-Type": "application/json", "X-CSRFToken": self.csrf})
            payload = json.dumps(body).encode("utf-8") if body is not None else None
            request = Request(self.target + path, data=payload, headers=headers, method=method)
            try:
                response = self.http.open(request, timeout=min(self.timeout, remaining))
            except HTTPError as exc:
                response = exc
            with response:
                actual_status = response.code
                stage = "response_body"
                raw = response.read(2 * 1024 * 1024 + 1)
                if len(raw) > 2 * 1024 * 1024:
                    reason = "response_too_large"
                elif actual_status != status:
                    reason = "unexpected_status"
                elif not negative and status != 204:
                    try:
                        data = json.loads(raw)
                    except (ValueError, UnicodeError):
                        reason = "invalid_json"
                    if not reason and unconfirmed_write:
                        if equals and "id" in equals and not expect(data, {"id": equals["id"]}):
                            reason = "assertion_failed"
                        elif not equals or len(equals) < 2:
                            reason = "unconfirmed_write_outcome"
                        elif expect(data, equals):
                            reason = "unconfirmed_write_matches_expected"
                        else:
                            reason = "unconfirmed_write_differs_from_expected"
                    elif not reason and not expect(data, equals or {}):
                        reason = "assertion_failed"
                    if not reason and capture:
                        try:
                            for response_field in capture.values():
                                value = field(data, response_field)
                                if not isinstance(value, (str, int, float, bool)) or len(str(value)) > 512:
                                    raise ValueError()
                        except (KeyError, IndexError, TypeError, ValueError):
                            reason = "capture_failed"
        except (TimeoutError, URLError, OSError, http.client.HTTPException) as exc:
            reason = "transport_error"
            transport_error = f"{stage}:{transport_category(exc)}"
        except Exception:
            reason = "harness_error"
        finally:
            self.stats.record(
                self.phase, self.account["role"], name, actual_status,
                (time.monotonic() - started) * 1000, reason, negative, self.index, transport_error,
            )
        if reason:
            raise ScenarioFailure(reason)
        return data

    def authenticate(self):
        data = self.request("csrf", "/csrf/api/v1/token", capture={"csrf": "csrfToken"})
        self.csrf = data["csrfToken"]
        self.request(
            "login", SESSION_PATH, method="POST",
            body={"username": self.account["username"], "password": self.account["password"]},
            equals={"authenticated": True, "username": self.account["username"], "role": self.account["role"]},
        )
        # Django rotates CSRF on login; the pre-login token must not be reused.
        data = self.request("csrf-after-login", "/csrf/api/v1/token", capture={"csrf": "csrfToken"})
        self.csrf = data["csrfToken"]
        self.request("identity", IDENTITY_PATH, equals={
            "id": self.account["user_id"], "username": self.account["username"],
            "role": self.account["role"], "etablissement": self.account["tenant_id"], "is_active": True,
        })
        session_cookies = [cookie.value for cookie in self.cookies if cookie.name == "sessionid"]
        if not session_cookies:
            raise ScenarioFailure("missing_session_cookie")
        if len(session_cookies) != 1:
            raise ScenarioFailure("ambiguous_session_cookie")
        return hashlib.sha256(session_cookies[0].encode()).hexdigest()


def run_campaign(args, seed, client_factory=Client, progress=None):
    accounts = seed["accounts"]
    stats = Stats(progress=progress)
    abort = threading.Event()
    start = time.monotonic()
    started_at = datetime.now(UTC).isoformat()
    startup_deadline = start + args.ramp_seconds + args.startup_timeout_seconds
    hold = {"start": None, "end": None, "started_at": None, "cleanup_started_at": None}
    run_id = uuid.uuid4().hex

    def open_gate():
        hold["start"] = time.monotonic()
        hold["end"] = hold["start"] + args.duration_seconds
        hold["started_at"] = datetime.now(UTC).isoformat()
        if progress:
            progress({"phase": "plateau", "authenticated_users": args.users, "duration_seconds": args.duration_seconds})

    gate = threading.Barrier(args.users + 1, action=open_gate)

    def begin_cleanup():
        hold["cleanup_started_at"] = datetime.now(UTC).isoformat()
        if progress:
            progress({"phase": "integrity_and_logout", "authenticated_users": stats.authenticated_total})

    cleanup_gate = threading.Barrier(args.users, action=begin_cleanup)

    def worker(index, account):
        result = {
            "user_index": index, "role": account["role"], "scenario": account["scenario"],
            "authenticated": False, "cycles": 0, "integrity_checks": 0,
            "integrity_failures": 0, "integrity_indeterminate": 0, "unconfirmed_writes": 0,
            "unconfirmed_matches": 0, "unconfirmed_differs": 0,
            "last_attempted_iteration": 0, "failed_step": None, "errors": [], "logged_out": False,
        }
        client = client_factory(args.target, args.timeout, account, index, stats)
        context = context_for(account, run_id)
        owned = {render(path, context) for path in account.get("owned_resources", [])}
        last_writes = {}
        current_step = "authentication"
        try:
            due = start + index * args.ramp_seconds / max(1, args.users - 1)
            if abort.wait(max(0, due - time.monotonic())):
                return result
            client.deadline = startup_deadline
            fingerprint = client.authenticate()
            if not stats.joined(fingerprint):
                raise ScenarioFailure("duplicate_session")
            result["authenticated"] = True
            gate.wait(timeout=max(0.001, startup_deadline - time.monotonic()))
            client.phase = "load"
            client.deadline = hold["end"] + args.timeout * 2
            while time.monotonic() < hold["end"]:
                context["iteration"] += 1
                result["last_attempted_iteration"] = context["iteration"]
                complete = True
                for step in seed["scenarios"][account["scenario"]]["steps"]:
                    if time.monotonic() >= hold["end"]:
                        complete = False
                        break
                    resolved = render(step, context)
                    current_step = step["name"]
                    if step.get("method", "GET") != "GET":
                        verify = render(step["verify"], context)
                        if verify["path"] not in owned or not resolved["path"].startswith(verify["path"]):
                            raise ScenarioFailure("write_outside_owned_fixture")
                        # A failed write response may still have committed on the server.
                        last_writes[verify["path"]] = (step["name"], verify, False)
                    data = client.request(
                        resolved["name"], api_path(resolved["path"]), method=resolved.get("method", "GET"),
                        body=resolved.get("json"), status=resolved.get("status", 200),
                        equals=resolved.get("equals"), capture=step.get("capture"), negative=step.get("negative", False),
                    )
                    for name, response_field in step.get("capture", {}).items():
                        context[name] = field(data, response_field)
                    if step.get("method", "GET") != "GET":
                        verify = render(step["verify"], context)
                        last_writes[verify["path"]] = (step["name"], verify, True)
                        current_step = step["name"] + "-readback"
                        client.request(step["name"] + "-readback", api_path(verify["path"]), equals=verify["equals"])
                if complete:
                    result["cycles"] += 1
                abort.wait(min(args.think_seconds, max(0, hold["end"] - time.monotonic())))
        except threading.BrokenBarrierError:
            result["errors"].append("cohort_not_ready")
        except ScenarioFailure as exc:
            result["errors"].append(str(exc))
            result["failed_step"] = current_step
        except Exception:
            result["errors"].append("harness_error")
        finally:
            if hold["start"] is None:
                abort.set()
                gate.abort()
            else:
                stats.workload_departure()
                try:
                    # A failed user's diagnostic/cleanup traffic must not contaminate other users' plateau.
                    cleanup_gate.wait(timeout=max(0.001, hold["end"] + args.timeout * 2 - time.monotonic()))
                except threading.BrokenBarrierError:
                    result["errors"].append("cleanup_cohort_not_ready")
            client.phase = "integrity"
            client.deadline = (hold["end"] or time.monotonic()) + args.cleanup_timeout_seconds
            if result["authenticated"]:
                try:
                    client.request("final-identity", IDENTITY_PATH, equals={
                        "id": account["user_id"], "role": account["role"], "etablissement": account["tenant_id"],
                    })
                    result["integrity_checks"] += 1
                except ScenarioFailure as exc:
                    key = "integrity_failures" if str(exc) == "assertion_failed" else "integrity_indeterminate"
                    result[key] += 1
                for name, verify, confirmed in last_writes.values():
                    result["unconfirmed_writes"] += not confirmed
                    try:
                        client.request(
                            name + "-final-readback", api_path(verify["path"]),
                            equals=verify["equals"],
                            unconfirmed_write=not confirmed,
                        )
                        result["integrity_checks"] += 1
                    except ScenarioFailure as exc:
                        if str(exc) == "unconfirmed_write_matches_expected":
                            result["unconfirmed_matches"] += 1
                        elif str(exc) == "unconfirmed_write_differs_from_expected":
                            result["unconfirmed_differs"] += 1
                        key = "integrity_failures" if str(exc) == "assertion_failed" else "integrity_indeterminate"
                        result[key] += 1
                stats.departed()
            # Even a successful login followed by failed identity validation needs logout.
            if client.csrf:
                client.phase = "logout"
                try:
                    client.request("logout", SESSION_PATH, method="DELETE", equals={"authenticated": False})
                    client.request("logout-check", IDENTITY_PATH, status=401, negative=True)
                    result["logged_out"] = True
                except ScenarioFailure:
                    result["errors"].append("logout_failed")
        return result

    cohort_ready = False
    results = []
    with ThreadPoolExecutor(max_workers=args.users) as pool:
        futures = []
        try:
            for index, account in enumerate(accounts):
                futures.append(pool.submit(worker, index, account))
        except (RuntimeError, OSError):
            abort.set()
            gate.abort()
        try:
            gate.wait(timeout=max(0.001, startup_deadline - time.monotonic()))
            cohort_ready = True
        except threading.BrokenBarrierError:
            abort.set()
            gate.abort()
        for index, account in enumerate(accounts):
            try:
                results.append(futures[index].result())
            except Exception:
                results.append({
                    "user_index": index, "role": account["role"], "scenario": account["scenario"],
                    "authenticated": False, "cycles": 0, "integrity_checks": 0,
                    "integrity_failures": 0, "integrity_indeterminate": 0, "unconfirmed_writes": 0,
                    "unconfirmed_matches": 0, "unconfirmed_differs": 0,
                    "errors": ["worker_capacity_or_harness_failure"], "logged_out": False,
                })
    ended = time.monotonic()
    full_cohort_seconds = 0
    if cohort_ready and stats.first_departure:
        full_cohort_seconds = min(args.duration_seconds, max(0, stats.first_departure - hold["start"]))
    load_seconds = max(0, (stats.last_departure or ended) - hold["start"]) if cohort_ready else 0
    metrics = stats.summary(load_seconds)
    metrics["all_phases_requests_per_second"] = round(metrics["requests"] / max(ended - start, 0.001), 2)
    checks = {
        "entire_cohort_authenticated": cohort_ready and stats.authenticated_total == args.users,
        "full_cohort_held_for_duration": full_cohort_seconds >= args.duration_seconds,
        "every_user_completed_business_cycle": all(result["cycles"] > 0 for result in results),
        "no_unexpected_failures": metrics["failures"] == 0 and not any(result["errors"] for result in results),
        "final_integrity_passed": all(
            result["integrity_checks"] > 0 and not result["integrity_failures"] and not result["integrity_indeterminate"]
            for result in results
        ),
        "all_sessions_logged_out": all(result["logged_out"] for result in results),
        "load_p95_within_budget": metrics["load_latency_ms"]["p95"] <= args.max_p95_ms,
    }
    return {
        "schema_version": 2, "kind": "sis-authenticated-http-sessions",
        "run_id": run_id, "generated_at": datetime.now(UTC).isoformat(),
        "started_at": started_at, "plateau_started_at": hold["started_at"],
        "cleanup_started_at": hold["cleanup_started_at"],
        "environment_id": seed["environment"]["id"], "target_origin": args.target,
        "passed": all(checks.values()), "checks": checks,
        "configuration": {key: getattr(args, key) for key in (
            "users", "ramp_seconds", "duration_seconds", "think_seconds", "timeout",
            "startup_timeout_seconds", "cleanup_timeout_seconds", "max_p95_ms",
        )},
        "elapsed_seconds": round(ended - start, 3),
        "authenticated_users": stats.authenticated_total,
        "role_distribution": dict(Counter(account["role"] for account in accounts)),
        "scenario_distribution": dict(Counter(account["scenario"] for account in accounts)),
        "peak_authenticated_sessions": stats.peak_authenticated,
        "full_cohort_seconds": round(full_cohort_seconds, 3),
        "business_cycles": sum(result["cycles"] for result in results),
        "data_integrity": {
            "scope": "identity and configured per-write persisted-field readbacks; not a whole-database audit",
            "checks_passed": sum(result["integrity_checks"] for result in results),
            "checks_failed": sum(result["integrity_failures"] for result in results),
            "checks_indeterminate": sum(result["integrity_indeterminate"] for result in results),
            "unconfirmed_writes": sum(result["unconfirmed_writes"] for result in results),
            "unconfirmed_matches": sum(result["unconfirmed_matches"] for result in results),
            "unconfirmed_differs": sum(result["unconfirmed_differs"] for result in results),
        },
        "metrics": metrics, "users": results,
        "limitations": [
            "HTTP users, not browser contexts or guaranteed simultaneously open TCP connections.",
            "Only seeded scenarios are covered; Playwright full-form/button qualification is separate.",
            "Isolation is an operator attestation, not proof of separate infrastructure.",
            "Synthetic writes are retained: discard or restore the isolated fixture after the campaign.",
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", required=True, help="Isolated SIS API origin, not frontend or LMS origin")
    parser.add_argument("--acknowledge-isolated-target", required=True)
    parser.add_argument("--seed", required=True, help="0600 JSON synthetic credentials and fixtures")
    parser.add_argument("--users", type=int, default=500)
    parser.add_argument("--ramp-seconds", type=float, default=60)
    parser.add_argument("--duration-seconds", type=float, default=120, help="Full authenticated cohort hold")
    parser.add_argument("--startup-timeout-seconds", type=float, default=120, help="Grace after ramp")
    parser.add_argument("--cleanup-timeout-seconds", type=float, default=30)
    parser.add_argument("--think-seconds", type=float, default=1)
    parser.add_argument("--timeout", type=float, default=5)
    parser.add_argument("--max-p95-ms", type=float, default=2000)
    parser.add_argument("--output", required=True)
    parser.add_argument("--validate-only", action="store_true", help="Validate locally; make zero network calls")
    args = parser.parse_args(argv)
    try:
        limits = {
            "users": (1, 500), "ramp_seconds": (0, 7200), "duration_seconds": (1, 900),
            "startup_timeout_seconds": (1, 180), "cleanup_timeout_seconds": (1, 120),
            "think_seconds": (0.1, 30), "timeout": (0.1, 30), "max_p95_ms": (1, 60000),
        }
        for name, (minimum, maximum) in limits.items():
            if not minimum <= getattr(args, name) <= maximum:
                raise ConfigurationError("A load parameter is outside its documented finite safety bounds.")
        if args.users == 500 and args.ramp_seconds < 30:
            raise ConfigurationError("500 sessions require a ramp of at least 30 seconds.")
        seed = read_seed(args.seed)
        args.target = check_isolation(args.target, args.acknowledge_isolated_target, seed)
        validate_seed(seed, args.users)
        output = Path(args.output)
        if output.exists() or output.resolve() == Path(args.seed).resolve() or not output.parent.is_dir():
            raise ConfigurationError("Output must be a new file in an existing directory, never the seed.")
        # Check writability before any network call, without overwriting prior evidence.
        with output.open("x", encoding="utf-8") as stream:
            if args.validate_only:
                report = {
                    "schema_version": 1, "kind": "offline-seed-validation", "valid": True,
                    "network_requests": 0, "users": args.users,
                    "role_distribution": dict(Counter(account["role"] for account in seed["accounts"])),
                    "load_executed": False,
                }
            else:
                def progress(event):
                    count = event["authenticated_users"]
                    if event["phase"] != "authentication" or count == 1 or count % 25 == 0 or count == args.users:
                        print(json.dumps({
                            "kind": "load-progress", "timestamp": datetime.now(UTC).isoformat(), **event,
                        }), flush=True)

                print(json.dumps({
                    "kind": "load-start", "timestamp": datetime.now(UTC).isoformat(),
                    "users": args.users, "ramp_seconds": args.ramp_seconds, "duration_seconds": args.duration_seconds,
                }), flush=True)
                report = run_campaign(args, seed, progress=progress)
            json.dump(report, stream, indent=2)
            stream.write("\n")
        print(json.dumps({
            "kind": report["kind"], "passed": report.get("passed"),
            "validated": report.get("valid", False), "load_executed": not args.validate_only,
        }))
        return 0 if args.validate_only or report["passed"] else 1
    except ConfigurationError as exc:
        parser.exit(2, f"Refused: {exc}\n")
    except (OSError, ValueError):
        parser.exit(2, "Refused: unable to read configuration or persist the report.\n")


if __name__ == "__main__":
    raise SystemExit(main())
