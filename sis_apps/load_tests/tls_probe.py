"""Bounded verified TLS handshakes only: no HTTP, authentication or UI qualification."""

import argparse
import json
import math
import os
import socket
import ssl
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

if __package__:
    from .safety import ConfigurationError, check_isolation, read_seed
else:
    from safety import ConfigurationError, check_isolation, read_seed


def validate_configuration(args, seed):
    target = check_isolation(args.target, args.acknowledge_isolated_target, seed)
    parsed = urlsplit(target)
    if (
        parsed.scheme != "https" or parsed.hostname != "load-secondaire.localhost"
        or seed["environment"]["id"] != "sis-load-d0c25c75"
        or not 1 <= args.connections <= 500 or not 0.1 <= args.timeout <= 10
        or not 1 <= args.max_p95_ms <= 2000
    ):
        raise ConfigurationError("TLS diagnostic requires the named HTTPS fixture and bounded parameters.")
    return parsed


def probe(args, seed):
    target = validate_configuration(args, seed)
    context = ssl.create_default_context(cafile=args.ca_file)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    addresses = socket.getaddrinfo(target.hostname, target.port or 443, type=socket.SOCK_STREAM)
    if not addresses or any(address[4][0] not in ("127.0.0.1", "::1") for address in addresses):
        raise ConfigurationError("Named fixture must resolve exclusively to loopback.")
    # This fixture publishes specifically on IPv4 loopback. DNS may list ::1
    # first even though no listener is bound there; do not probe another endpoint.
    addresses = [address for address in addresses if address[4][0] == "127.0.0.1"]
    if not addresses:
        raise ConfigurationError("Named fixture must resolve to its published IPv4 loopback address.")
    barrier = threading.Barrier(args.connections + 1)
    retained, outcomes = [], []
    lock = threading.Lock()

    def handshake():
        connection = None
        stage = "startup"
        started = time.monotonic()
        try:
            barrier.wait(timeout=15)
            started = time.monotonic()
            stage = "tcp"
            family, socktype, proto, _, address = addresses[0]
            connection = socket.socket(family, socktype, proto)
            connection.settimeout(args.timeout)
            connection.connect(address)
            stage = "tls"
            connection = context.wrap_socket(connection, server_hostname=target.hostname, do_handshake_on_connect=False)
            connection.settimeout(max(0.001, args.timeout - (time.monotonic() - started)))
            connection.do_handshake()
            elapsed = (time.monotonic() - started) * 1000
            with lock:
                retained.append(connection)
            connection = None
            return {"ok": True, "elapsed_ms": elapsed}
        except (OSError, ValueError, threading.BrokenBarrierError) as exc:
            return {"ok": False, "stage": stage, "category": type(exc).__name__,
                    "elapsed_ms": (time.monotonic() - started) * 1000}
        finally:
            if connection:
                connection.close()

    started_at = datetime.now(UTC).isoformat()
    start = time.monotonic()
    try:
        with ThreadPoolExecutor(max_workers=args.connections) as executor:
            futures = [executor.submit(handshake) for _ in range(args.connections)]
            barrier.wait(timeout=15)
            outcomes = [future.result() for future in futures]
        latencies = sorted(item["elapsed_ms"] for item in outcomes)
        p95 = latencies[math.ceil(len(latencies) * 0.95) - 1]
        return {
            "kind": "sis-tls-handshake-diagnostic", "started_at": started_at,
            "target": args.target, "connections_requested": args.connections,
            "connected_address": "127.0.0.1",
            "simultaneous_verified_tls_sockets_retained": len(retained),
            "http_requests": 0, "authenticated_sessions": 0, "api_or_ui_qualification": False,
            "timeout_seconds": args.timeout, "max_p95_ms": args.max_p95_ms,
            "duration_seconds": round(time.monotonic() - start, 3),
            "handshake_latency_ms": {
                "p50": round(latencies[math.ceil(len(latencies) * 0.5) - 1], 3),
                "p95": round(p95, 3), "p99": round(latencies[math.ceil(len(latencies) * 0.99) - 1], 3),
                "max": round(max(latencies), 3),
            },
            "errors": dict(Counter(f"{item['stage']}:{item['category']}" for item in outcomes if not item["ok"])),
            "passed": len(retained) == args.connections and p95 <= args.max_p95_ms,
        }
    finally:
        for connection in retained:
            connection.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", required=True)
    parser.add_argument("--acknowledge-isolated-target", required=True)
    parser.add_argument("--seed", required=True)
    parser.add_argument("--ca-file", required=True)
    parser.add_argument("--connections", type=int, default=500)
    parser.add_argument("--timeout", type=float, default=5)
    parser.add_argument("--max-p95-ms", type=float, default=2000)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    try:
        seed = read_seed(args.seed)
        validate_configuration(args, seed)
        # Reserve the output before any network activity; never overwrite evidence.
        with Path(args.output).open("x", encoding="utf-8") as stream:
            os.chmod(args.output, 0o600)
            report = probe(args, seed)
            json.dump(report, stream, indent=2)
            stream.write("\n")
        print(json.dumps(report))
        return 0 if report["passed"] else 1
    except (ConfigurationError, OSError, ValueError, threading.BrokenBarrierError):
        parser.exit(2, "Refused or incomplete: inspect configuration/resources; no diagnostic pass recorded.\n")


if __name__ == "__main__":
    raise SystemExit(main())
