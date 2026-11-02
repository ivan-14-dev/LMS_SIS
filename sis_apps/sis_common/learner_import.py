import hashlib
import secrets

from django.db import IntegrityError, transaction
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from sis_common.spreadsheets import load_learner_rows, template_response

BASE_COLUMNS = [
    "username",
    "email",
    "first_name",
    "last_name",
    "date_naissance",
    "lieu_naissance",
    "sexe",
    "adresse",
    "code_postal",
    "ville",
]


class LearnerImportMixin:
    learner_create_serializer = None
    learner_model = None
    import_extra_columns = ()

    @action(detail=False, methods=["get"], url_path="modele-import")
    def modele_import(self, request):
        return template_response([*BASE_COLUMNS, *self.import_extra_columns], "modele_apprenants.xlsx")

    @action(detail=False, methods=["post"])
    def importer(self, request):
        uploaded = request.FILES.get("file")
        if uploaded is None:
            raise ValidationError({"file": "Sélectionnez un fichier."})
        if uploaded.size > 5 * 1024 * 1024:
            raise ValidationError({"file": "La taille maximale est de 5 Mo."})
        digest = hashlib.sha256(uploaded.read()).hexdigest()
        uploaded.seek(0)
        rows = load_learner_rows(uploaded, [*BASE_COLUMNS, *self.import_extra_columns])
        applying = request.data.get("apply") == "true"
        if applying and request.data.get("digest") != digest:
            raise ValidationError({"file": "Prévisualisez ce fichier avant de confirmer son import."})
        errors, pending, skipped, seen = [], [], 0, set()
        with transaction.atomic():
            for line_number, values in rows:
                username = values.get("username")
                if username in seen:
                    errors.append(
                        {
                            "line": line_number,
                            "errors": {"username": "Identifiant répété dans le fichier."},
                        }
                    )
                    continue
                seen.add(username)
                existing = self.get_queryset().select_related("user").filter(user__username=username).first()
                if existing:
                    matches = all(
                        str(
                            getattr(
                                (
                                    existing.user
                                    if key in ("username", "email", "first_name", "last_name")
                                    else existing
                                ),
                                key,
                                "",
                            )
                            or ""
                        )
                        == str(value or "")
                        for key, value in values.items()
                    )
                    if matches:
                        skipped += 1
                    else:
                        errors.append(
                            {
                                "line": line_number,
                                "errors": {"username": "Ce dossier existe avec des données différentes."},
                            }
                        )
                    continue
                serializer = self.learner_create_serializer(
                    data={**values, "password": secrets.token_urlsafe(32)},
                    context={
                        **self.get_serializer_context(),
                        "unusable_password": True,
                    },
                )
                if serializer.is_valid():
                    pending.append(serializer)
                else:
                    errors.append({"line": line_number, "errors": serializer.errors})
            if applying and errors:
                raise ValidationError({"rows": errors})
            if applying:
                try:
                    with transaction.atomic():
                        for serializer in pending:
                            serializer.save()
                except IntegrityError as exc:
                    raise ValidationError(
                        {"file": "Les données ont changé. Prévisualisez à nouveau le fichier."}
                    ) from exc
        return Response(
            {
                "digest": digest,
                "total": len(rows),
                "to_create": len(pending),
                "skipped": skipped,
                "errors": errors,
                "created": len(pending) if applying else 0,
                "applied": applying,
            }
        )
