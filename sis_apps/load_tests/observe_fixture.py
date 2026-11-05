"""Read-only, secret-free observations of the specifically named disposable fixture."""

import argparse
import json
import os
from datetime import UTC, datetime
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    if os.environ.get("SIS_LOAD_FIXTURE") != "sis-load-d0c25c75" or os.environ.get("DB_HOST") != "sis-load-d0c25c75-postgres":
        raise SystemExit("Refused: observation is restricted to the named disposable fixture.")
    import django

    django.setup()

    from apps.core.models import Reclamation, ReclamationEntry, WorkflowNotification
    from apps.eleves.models import Inscription
    from apps.notes.models import Note
    from django.conf import settings
    from django.contrib.auth import get_user_model
    from django.contrib.sessions.models import Session
    from django.core.cache import cache
    from django_tenants.utils import schema_context

    with schema_context("load_d0c25c75"):
        histories = [
            {"category": (
                "anonymous" if key.startswith("throttle_anon_")
                else "user" if key.removeprefix("throttle_user_").isdigit()
                else "anonymous_shared_user_bucket"
             ),
             "recorded_requests": len(cache.get(key) or [])}
            for key in cache.iter_keys("throttle_*")
        ]
        report = {
            "fixture": "sis-load-d0c25c75", "debug": settings.DEBUG,
            "observed_at": datetime.now(UTC).isoformat(),
            "password_hasher": settings.PASSWORD_HASHERS[0],
            "drf_throttles": settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"],
            "throttle_histories": histories,
            "synthetic_users": get_user_model().objects.filter(username__startswith="synthetic-").count(),
            "total_local_accounts": get_user_model().objects.count(),
            "users_with_last_login": get_user_model().objects.exclude(last_login=None).count(),
            "sessions_in_database": Session.objects.count(), "enrollments": Inscription.objects.count(),
            "notes": Note.objects.count(),
            "notes_with_load_feedback": Note.objects.filter(appreciation__startswith="synthetic-").count(),
            "complaints": Reclamation.objects.count(),
            "complaint_messages": ReclamationEntry.objects.filter(action="message").count(),
            "workflow_notifications": WorkflowNotification.objects.count(),
        }
    output = Path(args.output)
    with output.open("x", encoding="utf-8") as stream:
        os.chmod(output, 0o600)
        json.dump(report, stream, indent=2)
        stream.write("\n")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
