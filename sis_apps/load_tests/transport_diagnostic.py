"""At most 32 clients/128 CSRF reads: transport timing, never business qualification."""

import argparse
import hashlib
import http.client
import json
import math
import os
import re
import ssl
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlsplit
from urllib.request import HTTPSHandler

if __package__:
    from .safety import ConfigurationError, check_isolation, read_seed
    from .sessions import Client, ScenarioFailure, Stats
else:
    from safety import ConfigurationError, check_isolation, read_seed
    from sessions import Client, ScenarioFailure, Stats

PATH = "/csrf/api/v1/token"


def resource_snapshot():
    try:
        group = Path("/proc/self/cgroup").read_text().strip().removeprefix("0::/")
        root = Path("/sys/fs/cgroup") / group
        return {
            key: (root / key).read_text().strip()
            for key in ("cpu.max", "cpu.stat", "memory.max", "memory.current", "memory.peak", "memory.events")
        }
    except OSError:
        return {"unavailable": True}


def validate(args, seed):
    target = check_isolation(args.target, args.acknowledge_isolated_target, seed)
    parsed = urlsplit(target)
    if (
        parsed.scheme != "https" or parsed.hostname != "load-secondaire.localhost"
        or seed["environment"]["id"] != "sis-load-d0c25c75"
        or not 1 <= args.clients <= 32 or not 1 <= args.requests_per_client <= 4
        or not 0.1 <= args.timeout <= 5 or not 1 <= args.max_p95_ms <= 2000
    ):
        raise ConfigurationError("Only the named HTTPS fixture and bounded transport parameters are permitted.")
    return target


def traced_connection_class(state):
    original = http.client.HTTPSConnection

    class TracedHTTPSConnection(original):
        def __init__(self, *args, **kwargs):
            started = time.perf_counter()
            super().__init__(*args, **kwargs)
            self.trace = state.row
            self.trace["connection_construct_ms"] = (time.perf_counter() - started) * 1000
            self.trace["context_identity"] = id(self._context)
            self.trace["verification_required"] = self._context.check_hostname and self._context.verify_mode == ssl.CERT_REQUIRED

        def connect(self):
            create = self._create_connection

            def timed_create(*args, **kwargs):
                start = time.perf_counter()
                try:
                    return create(*args, **kwargs)
                finally:
                    self.trace["dns_tcp_ms"] = (time.perf_counter() - start) * 1000

            self._create_connection = timed_create
            start = time.perf_counter()
            try:
                super().connect()
            finally:
                self.trace["connect_total_ms"] = (time.perf_counter() - start) * 1000
                self.trace["tls_ms"] = self.trace["connect_total_ms"] - self.trace.get("dns_tcp_ms", 0)

        def request(self, *args, **kwargs):
            start = time.perf_counter()
            try:
                return super().request(*args, **kwargs)
            finally:
                self.trace["request_send_including_connect_ms"] = (time.perf_counter() - start) * 1000

        def getresponse(self):
            start = time.perf_counter()
            try:
                response = super().getresponse()
                request_id = response.getheader("X-SIS-Load-Request-ID", "")
                if re.fullmatch("[0-9a-f]{32}", request_id):
                    self.trace["request_id"] = request_id
                return response
            finally:
                self.trace["response_headers_ms"] = (time.perf_counter() - start) * 1000

    return TracedHTTPSConnection


def trace_https(state):
    traced = traced_connection_class(state)
    original = HTTPSHandler.do_open

    def traced_open(handler, connection_class, request, **kwargs):
        if connection_class is http.client.HTTPSConnection:
            connection_class = traced
        return original(handler, connection_class, request, **kwargs)

    # Replacing http.client.HTTPSConnection itself breaks runtimes whose
    # constructor uses super(HTTPSConnection, self); inject only at dispatch.
    return patch.object(HTTPSHandler, "do_open", traced_open)


def measure(args, seed):
    validate(args, seed)
    if Path(ssl.get_default_verify_paths().cafile or "") != Path(args.ca_file).resolve():
        raise ConfigurationError("SSL_CERT_FILE must designate the same verified fixture CA as --ca-file.")
    stats = Stats()
    state = threading.local()
    rows = []
    contexts = set()
    factory = ssl._create_default_https_context
    wall_start, cpu_start = time.perf_counter(), time.process_time()
    started_at = datetime.now(UTC).isoformat()
    resources_before = resource_snapshot()
    with patch.object(ssl, "_create_default_https_context", wraps=factory) as made, trace_https(state):
        setup_start, setup_cpu = time.perf_counter(), time.process_time()
        clients = [Client(args.target, args.timeout, {"role": "transport-probe"}, i, stats) for i in range(args.clients)]
        setup_ms = (time.perf_counter() - setup_start) * 1000
        setup_cpu_ms = (time.process_time() - setup_cpu) * 1000
        release = {}
        gate = threading.Barrier(args.clients + 1, action=lambda: release.update(at=time.perf_counter()))

        def worker(index, client):
            gate.wait(timeout=15)
            result = []
            for iteration in range(args.requests_per_client):
                row = {"client_index": index, "iteration": iteration}
                state.row = row
                start, cpu = time.perf_counter(), time.thread_time()
                if iteration == 0:
                    row["cohort_start_lag_ms"] = (start - release["at"]) * 1000
                try:
                    client.request("csrf-transport", PATH, capture={"csrf": "csrfToken"})
                except ScenarioFailure as exc:
                    row["failure"] = str(exc)
                row["total_ms"] = (time.perf_counter() - start) * 1000
                row["thread_cpu_ms"] = (time.thread_time() - cpu) * 1000
                result.append(row)
            return result

        with ThreadPoolExecutor(max_workers=args.clients) as executor:
            futures = [executor.submit(worker, i, client) for i, client in enumerate(clients)]
            gate.wait(timeout=15)
            for future in futures:
                rows.extend(future.result())
        context_factory_calls = made.call_count
    elapsed, cpu = time.perf_counter() - wall_start, time.process_time() - cpu_start
    for row in rows:
        if "context_identity" in row:
            contexts.add(row.pop("context_identity"))
        for key, value in row.items():
            if key.endswith("_ms"):
                row[key] = round(value, 4)
    latencies = sorted(row["total_ms"] for row in rows)
    p95 = latencies[math.ceil(len(latencies) * 0.95) - 1]
    metrics = stats.summary(elapsed)
    verified = all(row.get("verification_required") for row in rows)
    return {
        "kind": "sis-bounded-http-transport-diagnostic", "started_at": started_at,
        "target": args.target, "path": PATH, "method": "GET",
        "clients": args.clients, "requests_per_client": args.requests_per_client,
        "requests": metrics["requests"], "statuses": metrics["statuses"], "failures": metrics["failures"],
        "context_factory_calls": context_factory_calls, "distinct_connection_contexts": len(contexts),
        "independent_cookie_jars": len({id(client.cookies) for client in clients}),
        "contexts_created_before_requests": True, "connection_policy": "urllib Connection: close; fresh TLS each request",
        "ca_sha256": hashlib.sha256(Path(args.ca_file).read_bytes()).hexdigest(), "tls_verification_required": verified,
        "timeout_seconds": args.timeout, "p95_budget_ms": args.max_p95_ms, "p95_ms": p95,
        "elapsed_seconds": round(elapsed, 4), "process_cpu_seconds": round(cpu, 4),
        "client_setup_wall_ms": round(setup_ms, 4), "client_setup_cpu_ms": round(setup_cpu_ms, 4),
        "resources_before": resources_before, "resources_after": resource_snapshot(),
        "requests_per_second": round(len(rows) / elapsed, 3), "peak_http_requests": metrics["peak_inflight_http_requests"],
        "authenticated_sessions": 0, "business_or_500_user_qualification": False,
        "diagnostic_passed": not metrics["failures"] and verified and p95 <= args.max_p95_ms,
        "requests_timing": rows,
        "limits": [
            "Instrumented timing has overhead; stage wall times include scheduling delays.",
            "This endpoint issues CSRF tokens only; it does not measure authenticated business capacity.",
            "Compare individual proxy request IDs, not differences between unpaired percentiles.",
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", required=True)
    parser.add_argument("--acknowledge-isolated-target", required=True)
    parser.add_argument("--seed", required=True)
    parser.add_argument("--ca-file", required=True)
    parser.add_argument("--clients", type=int, default=32)
    parser.add_argument("--requests-per-client", type=int, default=4)
    parser.add_argument("--timeout", type=float, default=5)
    parser.add_argument("--max-p95-ms", type=float, default=2000)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    try:
        seed = read_seed(args.seed)
        validate(args, seed)
        with Path(args.output).open("x", encoding="utf-8") as stream:
            os.chmod(args.output, 0o600)
            result = measure(args, seed)
            json.dump(result, stream, indent=2)
            stream.write("\n")
        print(json.dumps({key: value for key, value in result.items() if key != "requests_timing"}))
        return 0 if result["diagnostic_passed"] else 1
    except (ConfigurationError, OSError, ValueError, threading.BrokenBarrierError):
        parser.exit(2, "Diagnostic refused/incomplete; no pass recorded.\n")


if __name__ == "__main__":
    raise SystemExit(main())
