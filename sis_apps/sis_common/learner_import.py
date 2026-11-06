import csv
import hashlib
import secrets
from io import StringIO

from django.db import IntegrityError, transaction
from django.http import HttpResponse
from django.utils.crypto import constant_time_compare, salted_hmac
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

STUDENTS_SCHEMA_VERSION = 1
REQUIRED_COLUMNS = (
    "username",
    "email",
    "first_name",
    "last_name",
    "date_naissance",
    "lieu_naissance",
    "sexe",
)
SUPERIEUR_REQUIRED_COLUMNS = ("adresse", "code_postal", "ville", "matricule", "telephone")


class LearnerImportMixin:
    learner_create_serializer = None
    learner_model = None
    import_extra_columns = ()

    def import_schema(self):
        superior = "matricule" in self.import_extra_columns
        columns = [*BASE_COLUMNS, *self.import_extra_columns]
        required = set(REQUIRED_COLUMNS)
        if superior:
            required.update(SUPERIEUR_REQUIRED_COLUMNS)
        return {
            "schema_id": "sis.students.superieur" if superior else "sis.students.secondaire",
            "schema_version": STUDENTS_SCHEMA_VERSION,
            "identity_field": "username",
            "formats": ["csv", "xlsx"],
            "required_fields": [column for column in columns if column in required],
            "columns": [
                {
                    "id": column,
                    "required": column in required,
                    "type": "date" if column == "date_naissance" else "email" if column == "email" else "string",
                }
                for column in columns
            ],
        }

    @action(detail=False, methods=["get"])
    def schema_import(self, request):
        return Response(self.import_schema())

    @action(detail=False, methods=["get"], url_path="modele-import")
    def modele_import(self, request):
        schema = self.import_schema()
        headers = [field["id"] for field in schema["columns"]]
        output_format = request.query_params.get("type_fichier", "xlsx")
        if output_format == "csv":
            stream = StringIO()
            writer = csv.writer(stream)
            writer.writerow(headers)
            response = HttpResponse(stream.getvalue(), content_type="text/csv; charset=utf-8")
            response["Content-Disposition"] = 'attachment; filename="modele_apprenants.csv"'
        elif output_format == "xlsx":
            response = template_response(headers, "modele_apprenants.xlsx")
        else:
            raise ValidationError({"type_fichier": "Utilisez csv ou xlsx."})
        response["X-Import-Schema-Id"] = schema["schema_id"]
        response["X-Import-Schema-Version"] = str(schema["schema_version"])
        return response

    @action(detail=False, methods=["post"])
    def importer(self, request):
        schema = self.import_schema()
        supplied_id = request.data.get("schema_id")
        if supplied_id is not None and supplied_id != schema["schema_id"]:
            raise ValidationError({"schema_id": "Schéma Students non pris en charge."})
        supplied_version = request.data.get("schema_version")
        if supplied_version is not None and str(supplied_version) != str(schema["schema_version"]):
            raise ValidationError({"schema_version": "Version du schéma Students non prise en charge."})
        tenant = getattr(request, "tenant", None)
        if tenant is None or tenant.pk is None:
            raise ValidationError({"file": "Un établissement est requis pour importer des apprenants."})
        uploaded = request.FILES.get("file")
        if uploaded is None:
            raise ValidationError({"file": "Sélectionnez un fichier."})
        if uploaded.size > 5 * 1024 * 1024:
            raise ValidationError({"file": "La taille maximale est de 5 Mo."})
        file_digest = hashlib.sha256(uploaded.read()).hexdigest()
        digest = salted_hmac(
            "sis.students.import.v1",
            f"{tenant.pk}:{schema['schema_id']}:{schema['schema_version']}:{file_digest}",
            algorithm="sha256",
        ).hexdigest()
        uploaded.seek(0)
        rows = load_learner_rows(uploaded, [*BASE_COLUMNS, *self.import_extra_columns])
        applying = request.data.get("apply") == "true"
        if applying and not constant_time_compare(str(request.data.get("digest", "")), digest):
            raise ValidationError({"file": "Prévisualisez ce fichier avant de confirmer son import."})
        errors, pending, preview_rows, skipped, seen = [], [], [], 0, set()
        with transaction.atomic():
            for line_number, values in rows:
                username = values.get("username")
                row = {"line": line_number, "id": str(username or "")}
                if username in seen:
                    preview_rows.append({**row, "status": "error"})
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
                        preview_rows.append({**row, "status": "skip"})
                    else:
                        preview_rows.append({**row, "status": "error"})
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
                    preview_rows.append({**row, "status": "create"})
                else:
                    preview_rows.append({**row, "status": "error"})
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
                "schema_id": schema["schema_id"],
                "schema_version": schema["schema_version"],
                "digest": digest,
                "total": len(rows),
                "to_create": len(pending),
                "skipped": skipped,
                "rows": preview_rows,
                "errors": errors,
                "created": len(pending) if applying else 0,
                "applied": applying,
            }
        )
