"""Read-only postmortem of the named synthetic fixture; never repair/delete data."""

import argparse
import json
import os
from collections import Counter
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", required=True)
    parser.add_argument("--seed", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    if os.environ.get("SIS_LOAD_FIXTURE") != "sis-load-d0c25c75" or os.environ.get("DB_HOST") != "sis-load-d0c25c75-postgres":
        raise SystemExit("Refused: only the named disposable fixture may be examined.")
    report = json.loads(Path(args.report).read_text())
    seed = json.loads(Path(args.seed).read_text())
    if report["environment_id"] != "sis-load-d0c25c75" or seed["environment"]["id"] != report["environment_id"]:
        raise SystemExit("Refused: report/seed environment mismatch.")
    import django

    django.setup()

    from apps.core.models import Reclamation, ReclamationEntry
    from apps.eleves.models import Inscription
    from apps.notes.models import Note
    from django.contrib.auth import get_user_model
    from django.contrib.sessions.models import Session
    from django.db import connection, transaction
    from django_tenants.utils import schema_context

    prefix = "synthetic-" + report["run_id"] + "-"
    findings = []
    violations = []
    with schema_context("load_d0c25c75"), transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
        complaints = {str(item.pk): item for item in Reclamation.objects.all()}
        entries = {}
        for item in ReclamationEntry.objects.filter(action="message").order_by("created_at", "id"):
            entries.setdefault(str(item.reclamation_id), []).append(item)
        notes = {item.pk: item for item in Note.objects.select_related("evaluation__enseignant")}
        users = {item.pk: item for item in get_user_model().objects.filter(username__startswith="synthetic-")}
        for index, account in enumerate(seed["accounts"]):
            outcome = report["users"][index]
            if outcome["user_index"] != index:
                raise SystemExit("Report ordering mismatch.")
            user = users.get(account["user_id"])
            identity_ok = bool(user and user.role == account["role"] and user.etablissement_id == account["tenant_id"])
            if not identity_ok:
                violations.append({"user_index": index, "kind": "identity_mismatch"})
            if account["role"] == "eleve":
                record = complaints[account["variables"]["complaint_id"]]
                history = entries.get(str(record.pk), [])
                current = [item for item in history if item.message.startswith(prefix)]
                iterations = [int(item.message.removeprefix(prefix)) for item in current]
                actual = max(iterations, default=0)
                if (
                    record.demandeur_id != account["user_id"]
                    or record.version != len(history) + 1
                    or sorted(iterations) != list(range(1, actual + 1))
                    or any(item.auteur_id != account["user_id"] for item in current)
                ):
                    violations.append({"user_index": index, "kind": "complaint_history_or_ownership"})
            else:
                record = notes[account["variables"]["note_id"]]
                actual = int(record.appreciation.removeprefix(prefix)) if record.appreciation.startswith(prefix) else 0
                if record.valeur != Decimal("12.00") or (
                    account["role"] == "enseignant" and record.evaluation.enseignant.user_id != account["user_id"]
                ):
                    violations.append({"user_index": index, "kind": "grade_or_assignment_changed"})
            if not outcome["cycles"] <= actual <= outcome["cycles"] + 1:
                violations.append({"user_index": index, "kind": "confirmed_cycle_not_preserved_or_extra_iteration"})
            findings.append({
                "user_index": index, "role": account["role"], "confirmed_cycles": outcome["cycles"],
                "persisted_last_iteration": actual, "additional_partial_iteration": actual > outcome["cycles"],
                "http_logout_verified": outcome["logged_out"],
            })
        by_id = {str(account["user_id"]): index for index, account in enumerate(seed["accounts"])}
        remaining = [
            by_id.get(str(item.get_decoded().get("_auth_user_id")), "outside_seed")
            for item in Session.objects.all()
        ]
        counts = {
            "synthetic_users": len(users), "enrollments": Inscription.objects.count(),
            "validated_enrollments": Inscription.objects.filter(statut="validee").count(),
            "notes": len(notes), "complaints": len(complaints),
            "committed_complaint_messages_this_run": sum(
                item.message.startswith(prefix) for history in entries.values() for item in history
            ),
            "session_rows_remaining": len(remaining),
        }
    result = {
        "observed_at": datetime.now(UTC).isoformat(), "read_only_transaction": True,
        "run_id": report["run_id"], "original_qualification_passed": report["passed"],
        "original_report_not_modified": True, "counts": counts,
        "users_with_confirmed_cycles": sum(item["confirmed_cycles"] > 0 for item in findings),
        "users_with_extra_partial_write": sum(item["additional_partial_iteration"] for item in findings),
        "confirmed_business_cycles": sum(item["confirmed_cycles"] for item in findings),
        "violations": violations,
        "http_errors": dict(Counter(error for item in report["users"] for error in item["errors"])),
        "remaining_session_user_indices": remaining, "users": findings,
        "limitations": [
            "Only declared synthetic records and confirmed-cycle markers are checked.",
            "Postmortem database consistency does not turn a failed latency/logout campaign into a pass.",
            "Transport failures before receiving a write response do not establish a committed write.",
        ],
    }
    with Path(args.output).open("x", encoding="utf-8") as stream:
        os.chmod(args.output, 0o600)
        json.dump(result, stream, indent=2)
        stream.write("\n")
    print(json.dumps({key: value for key, value in result.items() if key not in ("users", "remaining_session_user_indices")}))


if __name__ == "__main__":
    main()
