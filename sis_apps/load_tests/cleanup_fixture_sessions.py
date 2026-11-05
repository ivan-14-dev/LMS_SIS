"""Delete only the 218 synthetic sessions identified by the preserved postmortem."""

import argparse
import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path

PREFIX = "sis-load-d0c25c75"
EXPECTED_COUNT = 218


def verify_session_owners(seed, postmortem, session_user_ids):
    accounts = seed.get("accounts", [])
    expected = postmortem.get("remaining_session_user_indices", [])
    if (
        len(accounts) != 500
        or any(account.get("synthetic") is not True for account in accounts)
        or len({str(account["user_id"]) for account in accounts}) != 500
        or len(expected) != EXPECTED_COUNT
        or any(type(index) is not int or not 0 <= index < 500 for index in expected)
        or postmortem.get("counts", {}).get("session_rows_remaining") != EXPECTED_COUNT
    ):
        raise ValueError("Refused: incomplete synthetic ownership evidence.")
    by_id = {str(account["user_id"]): index for index, account in enumerate(accounts)}
    observed = [by_id.get(str(user_id), -1) for user_id in session_user_ids]
    if sorted(observed) != sorted(expected):
        raise ValueError("Refused: session owners/count differ from the preserved postmortem.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", required=True)
    parser.add_argument("--postmortem", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--acknowledge-delete-218-synthetic-sessions", action="store_true", required=True)
    args = parser.parse_args()
    if (
        os.environ.get("SIS_LOAD_FIXTURE") != PREFIX
        or os.environ.get("DB_HOST") != PREFIX + "-postgres"
        or os.environ.get("DB_NAME") != "sis_load_d0c25c75"
    ):
        raise SystemExit("Refused: only the named disposable database may be changed.")
    seed_path, evidence_path, report_path = map(Path, (args.seed, args.postmortem, args.report))
    if seed_path.stat().st_mode & 0o077 or Path(args.output).exists():
        raise SystemExit("Refused: seed must be private and receipt must be new.")
    seed = json.loads(seed_path.read_text())
    evidence, report = json.loads(evidence_path.read_text()), json.loads(report_path.read_text())
    environment = seed.get("environment", {})
    if (
        environment.get("id") != PREFIX or environment.get("isolated") is not True
        or environment.get("synthetic") is not True
        or report.get("environment_id") != PREFIX or report.get("passed") is not False
        or evidence.get("run_id") != report.get("run_id")
        or evidence.get("read_only_transaction") is not True or evidence.get("violations")
    ):
        raise SystemExit("Refused: missing preserved failed-campaign evidence.")
    import django

    django.setup()
    from django.contrib.auth import get_user_model
    from django.contrib.sessions.models import Session
    from django.db import transaction
    from django_tenants.utils import schema_context

    with schema_context("load_d0c25c75"), transaction.atomic():
        users = {user.pk: user for user in get_user_model().objects.filter(
            pk__in=[account["user_id"] for account in seed["accounts"]],
        ).select_for_update()}
        for account in seed["accounts"]:
            user = users.get(account["user_id"])
            if not (
                user and user.username == account["username"] and user.is_active
                and user.role == account["role"] and user.etablissement_id == account["tenant_id"]
            ):
                raise SystemExit("Refused: a synthetic identity changed.")
        rows = list(Session.objects.select_for_update())
        verify_session_owners(seed, evidence, [row.get_decoded().get("_auth_user_id") for row in rows])
        deleted, _ = Session.objects.filter(session_key__in=[row.session_key for row in rows]).delete()
        remaining = Session.objects.count()
        if deleted != EXPECTED_COUNT or remaining:
            raise SystemExit("Refused: unexpected cleanup outcome; transaction rolled back.")
        receipt = {
            "completed_at": datetime.now(UTC).isoformat(), "environment_id": PREFIX,
            "deleted_session_rows": deleted, "remaining_session_rows": remaining,
            "business_records_changed": False, "matched_preserved_session_owners": True,
            "postmortem_sha256": hashlib.sha256(evidence_path.read_bytes()).hexdigest(),
            "original_report_sha256": hashlib.sha256(report_path.read_bytes()).hexdigest(),
        }
        # Reserve the receipt before commit, so an unwritable/existing path cannot
        # turn a committed deletion into an operation without an audit artifact.
        with Path(args.output).open("x", encoding="utf-8") as stream:
            os.chmod(args.output, 0o600)
            json.dump(receipt, stream, indent=2)
            stream.write("\n")
    print(json.dumps(receipt))


if __name__ == "__main__":
    main()
