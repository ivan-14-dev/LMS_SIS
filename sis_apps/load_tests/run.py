"""Dependency-free HTTP load checks for SIS exam and grade integration endpoints."""

import argparse
import hashlib
import hmac
import json
import os
import statistics
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def grade_request(url, index, timeout):
    secret = os.environ.get("SIS_LOAD_WEBHOOK_SECRET", "")
    if not secret:
        raise RuntimeError("SIS_LOAD_WEBHOOK_SECRET is required for grade-webhook")
    payload = {
        "user": {"id": index, "username": f"load-user-{index}"},
        "course": {
            "course_id": "course-v1:load+test+2026",
            "course_key": "course-v1:load+test+2026",
        },
        "subsection_id": "block-v1:load+test+2026+type@sequential+block@qcm",
        "score": index % 20,
        "max_score": 20,
        "timestamp": datetime.now(UTC).isoformat(),
    }
    body = json.dumps(payload, separators=(",", ":")).encode()
    signature = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    event_id = str(uuid.uuid4())
    return (
        Request(
            url,
            data=body,
            headers={
                "Content-Type": "application/json",
                "X-Event-ID": event_id,
                "X-Event-Type": "org.openedx.learning.course.assessment.grade.changed.v1",
                "X-Signature": f"sha256={signature}",
            },
            method="POST",
        ),
        timeout,
    )


def read_request(url, _index, timeout):
    token = os.environ.get("SIS_LOAD_BEARER_TOKEN", "")
    headers = {"Authorization": "Bearer " + token} if token else {}
    return Request(url, headers=headers, method="GET"), timeout


def execute(request_factory, url, index, timeout):
    started = time.perf_counter()
    try:
        request, request_timeout = request_factory(url, index, timeout)
        with urlopen(request, timeout=request_timeout) as response:
            response.read()
            success = 200 <= response.status < 300
            status = response.status
    except HTTPError as exc:
        success, status = False, exc.code
    except (TimeoutError, URLError, OSError):
        success, status = False, 0
    return success, status, (time.perf_counter() - started) * 1000


def percentile(values, quantile):
    ordered = sorted(values)
    return ordered[min(round((len(ordered) - 1) * quantile), len(ordered) - 1)]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("scenario", choices=("exam-list", "grade-webhook"))
    parser.add_argument("--url", required=True)
    parser.add_argument("--requests", type=int, default=1000)
    parser.add_argument("--concurrency", type=int, default=20)
    parser.add_argument("--timeout", type=float, default=10)
    parser.add_argument("--max-p95-ms", type=float, default=1000)
    parser.add_argument("--min-success-rate", type=float, default=0.99)
    args = parser.parse_args()
    if args.requests < 1 or args.concurrency < 1:
        parser.error("--requests and --concurrency must be positive")

    factory = grade_request if args.scenario == "grade-webhook" else read_request
    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=args.concurrency) as executor:
        results = list(
            executor.map(
                lambda index: execute(factory, args.url, index, args.timeout),
                range(args.requests),
            )
        )
    duration = time.perf_counter() - started
    latencies = [result[2] for result in results]
    successes = sum(result[0] for result in results)
    report = {
        "scenario": args.scenario,
        "requests": args.requests,
        "success_rate": round(successes / args.requests, 4),
        "requests_per_second": round(args.requests / duration, 2),
        "latency_ms": {
            "mean": round(statistics.fmean(latencies), 2),
            "p50": round(percentile(latencies, 0.50), 2),
            "p95": round(percentile(latencies, 0.95), 2),
            "max": round(max(latencies), 2),
        },
        "statuses": {
            str(response_status): sum(item[1] == response_status for item in results)
            for response_status in sorted({item[1] for item in results})
        },
    }
    print(json.dumps(report, indent=2))
    passed = (
        report["success_rate"] >= args.min_success_rate
        and report["latency_ms"]["p95"] <= args.max_p95_ms
    )
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
