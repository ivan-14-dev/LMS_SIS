"""Explicit practical API commands, strict envelopes and authenticated evidence."""

import json
import logging
import re

from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import FileResponse, Http404
from django.urls import re_path
from rest_framework import status
from rest_framework.exceptions import (
    APIException,
    NotFound,
    ParseError,
    ValidationError,
)
from rest_framework.parsers import JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from sis_common import practical_serializers as wire
from sis_common import practical_training as service
from sis_common.pagination import SISPagination
from sis_common.practical_access import can_decide, manages, refresh_context
from sis_common.practical_rules import PracticalRuleError

logger = logging.getLogger(__name__)

QUERY_FIELDS = {
    "capacites": {},
    "curriculums": {"q": "text", "page": "page", "page_size": "size"},
    "programmes": {
        "q": "text",
        "curriculum": "id",
        "statut": ("brouillon", "publie", "archive"),
        "page": "page",
        "page_size": "size",
    },
    "programme": {},
    "revisions": {"page": "page", "page_size": "size"},
    "programme_history": {"page": "page", "page_size": "size"},
    "conventions": {"revision": "id", "q": "text", "page": "page", "page_size": "size"},
    "partenaires": {"revision": "id", "q": "text", "page": "page", "page_size": "size"},
    "dossiers": {
        "q": "text",
        "programme": "id",
        "statut": ("ouvert", "clos", "annule"),
        "page": "page",
        "page_size": "size",
    },
    "dossier": {},
    "rapport": {},
    "dossier_history": {"page": "page", "page_size": "size"},
    "heures": {
        "statut": ("brouillon", "soumise", "validee", "rejetee", "annulee"),
        "page": "page",
        "page_size": "size",
    },
    "heure": {},
    "decisions": {"page": "page", "page_size": "size"},
    "hour_evidence": {},
    "evaluations": {"code": "code", "page": "page", "page_size": "size"},
    "assessment_evidence": {},
}
PROGRAMME_ACTIONS = {
    "configurer": "configuration",
    "publier": "publication",
    "reviser": "revision",
    "archiver": "archivage",
}
DOSSIER_ACTIONS = {"clore": "cloture", "annuler_dossier": "annulation", "revoquer": "partenaire_revocation"}
HOUR_ACTIONS = {
    "soumettre": "soumission",
    "remplacer": "remplacement",
    "annuler_heure": "annulation",
    "valider": "validation",
    "rejeter": "rejet",
    "invalider": "invalidation",
}
UPLOAD_ENDPOINTS = {"heures", "remplacer", "evaluer"}


def _integer(value, field, maximum=9007199254740991):
    if not isinstance(value, str) or not re.fullmatch(r"[1-9][0-9]*", value) or len(value) > 16:
        raise ValidationError({field: ["Un entier positif canonique est requis."]})
    result = int(value)
    if result > maximum:
        raise ValidationError({field: [f"La valeur maximale est {maximum}."]})
    return result


def query_parameters(request, endpoint):
    spec = QUERY_FIELDS.get(endpoint, {}) if request.method in ("GET", "HEAD") else {}
    unknown = set(request.query_params) - set(spec)
    if unknown:
        raise ValidationError({key: ["Paramètre non autorisé."] for key in sorted(unknown)})
    result = {}
    for key in request.query_params:
        values = request.query_params.getlist(key)
        if len(values) != 1:
            raise ValidationError({key: ["Un seul paramètre est accepté."]})
        value, rule = values[0], spec[key]
        if rule in ("id", "page", "size"):
            result[key] = _integer(value, key, 100 if rule == "size" else 9007199254740991)
        elif rule == "text":
            value = value.strip()
            if len(value) > 200:
                raise ValidationError({key: ["Au maximum 200 caractères."]})
            result[key] = value
        elif rule == "code":
            if not re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", value):
                raise ValidationError({key: ["Code de compétence invalide."]})
            result[key] = value
        elif value not in rule:
            raise ValidationError({key: ["Valeur non autorisée."]})
        else:
            result[key] = value
    if endpoint in ("conventions", "partenaires") and "revision" not in result:
        raise ValidationError({"revision": ["Ce paramètre est requis."]})
    return result


def _json_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Champ JSON répété.")
        result[key] = value
    return result


def _invalid_constant(value):
    raise ValueError("Nombre JSON non fini.")


def command_payload(request, endpoint):
    content_type = request.content_type.split(";", 1)[0].strip().lower()
    if content_type == "multipart/form-data":
        if endpoint not in UPLOAD_ENDPOINTS:
            raise ValidationError({"fichier": ["Cette commande n'accepte pas de fichier."]})
        data = request.data
        if set(data) - {"payload", "fichier"} or set(request.FILES) - {"fichier"}:
            raise ValidationError({"non_field_errors": ["Seuls payload et fichier sont acceptés."]})
        if len(data.getlist("payload")) != 1 or "payload" in request.FILES:
            raise ValidationError({"payload": ["Un unique objet JSON UTF-8 est requis."]})
        if len(data.getlist("fichier")) > 1 or len(request.FILES.getlist("fichier")) > 1:
            raise ValidationError({"fichier": ["Un seul fichier PDF est accepté."]})
        if "fichier" in data and "fichier" not in request.FILES:
            raise ValidationError({"fichier": ["Un fichier PDF binaire est requis."]})
        try:
            payload = json.loads(data["payload"], object_pairs_hook=_json_object, parse_constant=_invalid_constant)
        except (ValueError, TypeError, UnicodeError) as error:
            raise ValidationError({"payload": ["Un objet JSON UTF-8 valide est requis."]}) from error
        if not isinstance(payload, dict):
            raise ValidationError({"payload": ["Un objet JSON est requis."]})
        return payload, request.FILES.get("fichier")
    # Accessing request.data invokes the configured parser and rejects other MIME types.
    return request.data, None


def _field_errors(detail, prefix=""):
    errors = {}
    if isinstance(detail, dict):
        for field, value in detail.items():
            path = f"{prefix}.{field}" if prefix else str(field)
            errors.update(_field_errors(value, path))
    elif isinstance(detail, (list, tuple)):
        if any(isinstance(value, (dict, list, tuple)) for value in detail):
            for index, value in enumerate(detail):
                errors.update(_field_errors(value, f"{prefix}.{index}" if prefix else str(index)))
        else:
            errors[prefix or "non_field_errors"] = [str(value) for value in detail]
    else:
        errors[prefix or "non_field_errors"] = [str(detail)]
    return errors


class PracticalView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser, MultiPartParser]
    endpoint = ""
    http_method_names = ["get", "head", "post", "options"]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        refresh_context(request)
        for key in ("programme_id", "dossier_id", "convention_id", "heure_id", "evaluation_id"):
            if key in kwargs:
                self.kwargs[key] = _integer(str(kwargs[key]), key)
        self.query = query_parameters(request, self.endpoint)

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "private, no-store"
        response["X-Content-Type-Options"] = "nosniff"
        return response

    def handle_exception(self, exc):
        if isinstance(exc, PracticalRuleError):
            errors = getattr(exc, "errors", {}) or ({exc.field: [str(exc)]} if exc.field else {})
            return Response(
                {
                    "detail": str(exc),
                    "code": exc.code,
                    "errors": errors,
                    "current_version": getattr(exc, "current_version", None),
                    "criteres_non_satisfaits": getattr(exc, "unmet", []),
                },
                status=exc.status,
            )
        if isinstance(exc, DjangoValidationError):
            exc = ValidationError(getattr(exc, "message_dict", None) or exc.messages)
        if not isinstance(exc, (APIException, Http404, DjangoPermissionDenied)):
            logger.error("Échec d'une requête pratique.", exc_info=exc)
            return Response(
                {
                    "detail": "La requête pratique n'a pas pu aboutir.",
                    "code": "internal_error",
                    "errors": {},
                    "current_version": None,
                    "criteres_non_satisfaits": [],
                },
                status=500,
            )
        response = super().handle_exception(exc)
        if isinstance(exc, (ValidationError, ParseError)):
            detail, code = "Données invalides.", "validation_error"
            errors = _field_errors(exc.detail)
        else:
            raw = getattr(exc, "detail", "La requête a échoué.")
            detail = str(raw) if not isinstance(raw, (dict, list)) else "La requête a échoué."
            code = str(getattr(raw, "code", getattr(exc, "default_code", "error")))
            if response.status_code == status.HTTP_404_NOT_FOUND:
                code = "not_found"
            elif response.status_code == status.HTTP_403_FORBIDDEN and code not in (
                "module_disabled",
                "module_unavailable",
                "contexte_inactif",
                "not_authenticated",
            ):
                code = "permission_denied"
            errors = {}
        response.data = {
            "detail": detail,
            "code": code,
            "errors": errors,
            "current_version": None,
            "criteres_non_satisfaits": [],
        }
        return response

    def page(self, rows, serializer=None):
        pagination = SISPagination()
        selected = pagination.paginate_queryset(rows, self.request, view=self)
        data = [serializer(row) for row in selected] if serializer else selected
        return pagination.get_paginated_response(data)

    def _programme_item(self, programme):
        with service.consistent_programme(self.request, programme.pk) as locked:
            return wire.programme_dto(locked, self.request)

    def _dossier_item(self, dossier):
        with service.consistent_dossier(self.request, dossier.pk) as locked:
            return wire.dossier_dto(locked, self.request)

    def get(self, request, *args, **kwargs):
        endpoint = self.endpoint
        if endpoint == "capacites":
            return Response(service.capabilities(request))
        if endpoint == "curriculums":
            return self.page(service.curriculums(request, self.query.get("q", "")))
        if endpoint == "programmes":
            return self.page(service.programmes(request, self.query), self._programme_item)
        if endpoint == "dossiers":
            return self.page(service.dossiers(request, self.query), self._dossier_item)
        if "programme_id" in self.kwargs:
            with service.consistent_programme(request, self.kwargs["programme_id"]) as programme:
                return self._get_programme(programme)
        if "dossier_id" in self.kwargs:
            with service.consistent_dossier(request, self.kwargs["dossier_id"]) as dossier:
                return self._get_dossier(dossier)
        raise NotFound()

    def _get_programme(self, programme):
        endpoint, request = self.endpoint, self.request
        if endpoint == "programme":
            return Response(wire.programme_dto(programme, request))
        if endpoint == "revisions":
            return self.page(programme.revisions.order_by("-numero"), wire.revision_dto)
        if endpoint == "programme_history":
            return self.page(programme.historique.order_by("-version", "-pk"), wire.audit_dto)
        if endpoint == "conventions":
            return self.page(
                service.convention_candidates(request, programme, self.query["revision"], self.query.get("q", ""))
            )
        if endpoint == "partenaires":
            return self.page(
                service.partner_candidates(
                    request, programme, self.kwargs["convention_id"], self.query["revision"], self.query.get("q", "")
                )
            )
        raise NotFound()

    def _get_dossier(self, dossier):
        endpoint, request = self.endpoint, self.request
        if endpoint == "dossier":
            return Response(wire.dossier_dto(dossier, request))
        if endpoint == "rapport":
            return Response(wire.report_dto(dossier, request))
        if endpoint == "dossier_history":
            return self.page(dossier.historique.order_by("-version", "-pk"), wire.audit_dto)
        if endpoint == "heures":
            queryset = dossier.heures.order_by("-date", "-created_at", "pk")
            if "statut" in self.query:
                queryset = queryset.filter(statut=self.query["statut"])
            return self.page(queryset, lambda hour: wire.hour_dto(hour, dossier, request))
        if endpoint == "evaluations":
            queryset = dossier.evaluations_pratiques.order_by("code", "-revision")
            if "code" in self.query:
                service.assert_criterion(dossier, self.query["code"])
                queryset = queryset.filter(code=self.query["code"])
            return self.page(queryset, wire.assessment_dto)
        if "heure_id" in self.kwargs:
            hour = service.get_hour(dossier, self.kwargs["heure_id"])
            if endpoint == "heure":
                return Response(wire.hour_dto(hour, dossier, request))
            if endpoint == "decisions":
                return self.page(hour.decisions.order_by("sequence"), wire.decision_dto)
            if endpoint == "hour_evidence":
                return self._download(hour)
        if endpoint == "assessment_evidence":
            assessment = dossier.evaluations_pratiques.filter(pk=self.kwargs["evaluation_id"]).first()
            if assessment is None:
                raise NotFound()
            return self._download(assessment)
        raise NotFound()

    def _download(self, owner):
        if not owner.fichier:
            raise NotFound()
        try:
            stream = owner.fichier.storage.open(owner.fichier.name, "rb")
        except (FileNotFoundError, OSError) as error:
            raise NotFound() from error
        return FileResponse(
            stream,
            content_type="application/pdf",
            as_attachment=True,
            filename=owner.fichier_nom,
        )

    def _preflight(self):
        endpoint, request = self.endpoint, self.request
        if endpoint == "programmes":
            service.require(manages(request))
        elif endpoint == "dossiers":
            service.require(service.capabilities(request)["actions"]["can_open_dossier"])
        elif endpoint in PROGRAMME_ACTIONS:
            service.get_programme(request, self.kwargs["programme_id"])
        else:
            dossier = service.get_dossier(request, self.kwargs["dossier_id"])
            if endpoint in DOSSIER_ACTIONS:
                service.require(manages(request, dossier))
            elif endpoint == "evaluer":
                service.require(can_decide(request, dossier, "evaluate"))
            else:
                hour = service.get_hour(dossier, self.kwargs["heure_id"]) if "heure_id" in self.kwargs else None
                service.authorize_hour(
                    request, dossier, "creation" if endpoint == "heures" else HOUR_ACTIONS[endpoint], hour
                )

    def post(self, request, *args, **kwargs):
        self._preflight()
        data, upload = command_payload(request, self.endpoint)
        endpoint = self.endpoint
        if endpoint == "programmes":
            return Response(service.create_programme(request, data), status=201)
        if endpoint in PROGRAMME_ACTIONS:
            result = service.programme_command(request, self.kwargs["programme_id"], PROGRAMME_ACTIONS[endpoint], data)
            return Response(result, status=201 if endpoint == "reviser" else 200)
        if endpoint == "dossiers":
            return Response(service.open_dossier(request, data), status=201)
        if endpoint in DOSSIER_ACTIONS:
            return Response(
                service.dossier_command(request, self.kwargs["dossier_id"], DOSSIER_ACTIONS[endpoint], data)
            )
        if endpoint == "heures" or endpoint in HOUR_ACTIONS:
            result = service.hour_command(
                request,
                self.kwargs["dossier_id"],
                "creation" if endpoint == "heures" else HOUR_ACTIONS[endpoint],
                data,
                heure_id=self.kwargs.get("heure_id"),
                upload=upload,
            )
            return Response(result, status=201 if endpoint in ("heures", "remplacer") else 200)
        if endpoint == "evaluer":
            return Response(
                service.assess_competency(
                    request,
                    self.kwargs["dossier_id"],
                    self.kwargs["code"],
                    data,
                    upload=upload,
                ),
                status=201,
            )
        raise NotFound()


def _route(pattern, endpoint, methods=("get",)):
    return re_path(
        f"^pratique/{pattern}$",
        PracticalView.as_view(
            endpoint=endpoint,
            http_method_names=[*methods, *(["head"] if "get" in methods else []), "options"],
        ),
        name=f"pratique-{endpoint}",
    )


P = r"programmes/(?P<programme_id>[1-9][0-9]*)/"
D = r"dossiers/(?P<dossier_id>[1-9][0-9]*)/"
H = D + r"heures/(?P<heure_id>[1-9][0-9]*)/"

practical_urlpatterns = [
    _route("capacites/", "capacites"),
    _route("curriculums/", "curriculums"),
    _route("programmes/", "programmes", ("get", "post")),
    _route(P, "programme"),
    _route(P + "revisions/", "revisions"),
    _route(P + "historique/", "programme_history"),
    _route(P + "configurer/", "configurer", ("post",)),
    _route(P + "publier/", "publier", ("post",)),
    _route(P + "reviser/", "reviser", ("post",)),
    _route(P + "archiver/", "archiver", ("post",)),
    _route(P + "conventions/", "conventions"),
    _route(P + r"conventions/(?P<convention_id>[1-9][0-9]*)/partenaires/", "partenaires"),
    _route("dossiers/", "dossiers", ("get", "post")),
    _route(D, "dossier"),
    _route(D + "rapport/", "rapport"),
    _route(D + "historique/", "dossier_history"),
    _route(D + "clore/", "clore", ("post",)),
    _route(D + "annuler/", "annuler_dossier", ("post",)),
    _route(D + "partenaire/revoquer/", "revoquer", ("post",)),
    _route(D + "heures/", "heures", ("get", "post")),
    _route(H, "heure"),
    _route(H + "decisions/", "decisions"),
    _route(H + "soumettre/", "soumettre", ("post",)),
    _route(H + "remplacer/", "remplacer", ("post",)),
    _route(H + "annuler/", "annuler_heure", ("post",)),
    _route(H + "valider/", "valider", ("post",)),
    _route(H + "rejeter/", "rejeter", ("post",)),
    _route(H + "invalider/", "invalider", ("post",)),
    _route(H + "preuve/", "hour_evidence"),
    _route(D + "evaluations/", "evaluations"),
    _route(D + r"competences/(?P<code>[^/]+)/evaluer/", "evaluer", ("post",)),
    _route(D + r"evaluations/(?P<evaluation_id>[1-9][0-9]*)/preuve/", "assessment_evidence"),
]
