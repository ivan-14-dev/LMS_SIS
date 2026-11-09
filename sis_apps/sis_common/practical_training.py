"""Versioned practical commands and scoped, tenant-local read services.

Writers lock programme (when involved), learner, convention, dossier, then
children. The learner lock serializes even an empty cross-dossier hours ledger.
Read projections lock only their aggregate and never acquire a learner lock.
"""

import logging
from contextlib import contextmanager
from copy import deepcopy
from pathlib import PurePosixPath
from zoneinfo import ZoneInfo

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.db.models import Max
from django.utils import timezone
from django.utils.text import get_valid_filename
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from sis_common import practical_serializers as wire
from sis_common.exam_files import hash_uploaded_file, validate_exam_copy
from sis_common.practical_access import (
    can_decide,
    can_record,
    manages,
    permission,
    readable,
    refresh_context,
    scoped,
)
from sis_common.practical_bindings import (
    actor,
    binding_status,
    convention_binding,
    curriculum_dto,
    curriculum_identity,
    curriculum_model,
    local_user,
    model,
    secondary,
    stamp,
)
from sis_common.practical_models import practical_command
from sis_common.practical_rules import (
    LIVE_STATES,
    PERMISSIONS,
    PracticalRuleError,
    canonical_hash,
    constraints,
    criteria,
    wall_interval,
)

logger = logging.getLogger(__name__)


class PracticalConflict(PracticalRuleError):
    def __init__(self, detail, code="etat_incompatible", *, current_version=None, errors=None, unmet=None):
        super().__init__(detail, code=code, status=409)
        self.current_version = current_version
        self.errors = errors or {}
        self.unmet = unmet or []


def require(allowed):
    if not allowed:
        raise PermissionDenied("Cette action pratique n'est pas autorisée.")


def validate(command, data):
    serializer = command(data=data)
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data


def compare_version(aggregate, version, *, programme=False):
    if aggregate.version != version:
        raise PracticalConflict(
            "Le programme a été modifié. Rechargez sa version." if aggregate._meta.model_name == "programmepratique"
            else "Le dossier a été modifié. Rechargez sa version.",
            "version_perimee",
            current_version=aggregate.version,
            errors={"programme_version": ["current_version désigne la version du programme."]} if programme else {},
        )


def programme_queryset(request):
    return scoped(
        model("ProgrammePratique").objects.all(), request.user, "manage", request.tenant
    )


def get_programme(request, programme_id, *, locked=False):
    queryset = programme_queryset(request)
    if locked:
        queryset = queryset.select_for_update()
    programme = queryset.filter(pk=programme_id).first()
    if programme is None:
        raise NotFound()
    try:
        curriculum_identity(programme.curriculum, request.tenant, active=False)
    except (PracticalRuleError, ObjectDoesNotExist) as error:
        raise NotFound() from error
    return programme


def get_dossier(request, dossier_id, *, locked=False):
    queryset = model("DossierPratique").objects.filter(etablissement_id=request.tenant.pk)
    if locked:
        queryset = queryset.select_for_update()
    dossier = queryset.filter(pk=dossier_id).first()
    if dossier is None or not readable(request, dossier):
        raise NotFound()
    return dossier


def get_hour(dossier, heure_id, *, locked=False):
    queryset = dossier.heures.all()
    if locked:
        queryset = queryset.select_for_update()
    hour = queryset.filter(pk=heure_id).first()
    if hour is None:
        raise NotFound()
    return hour


def authorize_hour(request, dossier, action, hour=None):
    original = hour is not None and hour.saisi_par_id == request.user.pk
    if action == "creation":
        require(can_record(request, dossier))
    elif action in ("soumission", "remplacement"):
        require(original and can_record(request, dossier))
    elif action == "annulation":
        require(manages(request, dossier) or (original and can_record(request, dossier)))
    elif action in ("validation", "rejet", "invalidation"):
        require(can_decide(request, dossier, "validate", hour))
    else:
        raise NotFound()


def assert_open(dossier):
    if dossier.statut != "ouvert":
        raise PracticalConflict("Le dossier n'est plus ouvert.")


def assert_work_bindings(request, dossier):
    assert_open(dossier)
    if dossier.fuseau_horaire != request.tenant.fuseau_horaire:
        raise PracticalConflict("Le fuseau institutionnel a changé.", "fuseau_modifie")
    if not binding_status(dossier, request.tenant, active=False):
        raise PracticalConflict("Les liaisons du dossier ont changé.", "liaison_modifiee")
    if not binding_status(dossier, request.tenant):
        raise PermissionDenied("Les acteurs ou le curriculum sont inactifs.", code="contexte_inactif")


@contextmanager
def locked_dossier(request, dossier_id):
    initial = get_dossier(request, dossier_id)
    with transaction.atomic(), practical_command():
        learner_model = model("DossierPratique")._meta.get_field("apprenant").remote_field.model
        learner_model.objects.select_for_update().get(pk=initial.apprenant_id)
        model("ConventionStage").objects.select_for_update().get(pk=initial.convention_id)
        dossier = get_dossier(request, dossier_id, locked=True)
        refresh_context(request)
        # Drop related-object caches loaded during the pre-lock authorization.
        dossier = get_dossier(request, dossier_id)
        yield dossier


@contextmanager
def consistent_dossier(request, dossier_id):
    with transaction.atomic():
        refresh_context(request)
        yield get_dossier(request, dossier_id, locked=True)


@contextmanager
def consistent_programme(request, programme_id):
    with transaction.atomic():
        refresh_context(request)
        yield get_programme(request, programme_id, locked=True)


def audit(request, aggregate, action, **metadata):
    field = "programme" if aggregate._meta.model_name == "programmepratique" else "dossier"
    return model("AuditPratique").objects.create(
        **{field: aggregate},
        version=aggregate.version,
        action=action,
        acteur=request.user,
        acteur_nom=actor(request.user)["nom"],
        metadata=metadata,
    )


def advance(aggregate):
    aggregate.version += 1
    fields = ["version"]
    if aggregate._meta.model_name == "programmepratique":
        fields.append("updated_at")
    aggregate.save(update_fields=fields)


def programme_envelope(programme, request):
    return {"version": programme.version, "programme": wire.programme_dto(programme, request)}


def dossier_envelope(dossier, request, cancelled=None):
    report = wire.report_dto(dossier, request)
    return {
        "version": dossier.version,
        "dossier": wire.dossier_dto(dossier, request, report),
        "rapport": report,
        "heures_annulees": cancelled or [],
    }


def _permitted_somewhere(request, name):
    user, tenant = request.user, request.tenant
    if not local_user(user, tenant) or not user.has_perm(PERMISSIONS[name]):
        return False
    limits = {} if user.is_superuser else constraints(user.attributs_acces, PERMISSIONS[name])
    return limits is not None and ("etablissement_id" not in limits or tenant.pk in limits["etablissement_id"])


def capabilities(request):
    now = timezone.now().astimezone(ZoneInfo(request.tenant.fuseau_horaire))
    manager = _permitted_somewhere(request, "manage")
    programme_manager = programme_queryset(request).exists() if manager else False
    # A new programme has neither programme_id nor dossier_id to satisfy a scope.
    create = manages(request)
    limits = {} if request.user.is_superuser else constraints(
        request.user.attributs_acces, PERMISSIONS["manage"]
    )
    list_programmes = manager and limits is not None and "dossier_id" not in limits
    return {
        "contract_version": 1,
        "variant": "secondaire" if secondary() else "superieur",
        "module": "sis.practical_training",
        "fuseau_horaire": request.tenant.fuseau_horaire,
        "date_locale": now.date().isoformat(),
        "heure_locale": now.strftime("%H:%M"),
        "permissions": [value for key, value in PERMISSIONS.items() if _permitted_somewhere(request, key)],
        "actions": {
            "can_create_programme": create,
            "can_list_programmes": list_programmes,
            "can_open_dossier": list_programmes and (create or programme_manager),
            "can_list_dossiers": any(_permitted_somewhere(request, key) for key in PERMISSIONS),
        },
        "limits": {
            "max_competences": 100,
            "max_pdf_bytes": getattr(settings, "EXAM_COPY_MAX_SIZE", 26214400),
            "max_activite_length": 4000,
            "max_contexte_length": 4000,
            "max_motif_length": 4000,
        },
    }


def curriculums(request, query=""):
    require(manages(request))
    rows = []
    for source in curriculum_model().objects.order_by("pk"):
        try:
            dto = curriculum_dto(source, request.tenant)
        except (PracticalRuleError, ObjectDoesNotExist, ValueError, TypeError):
            continue
        if not query or query.casefold() in f"{dto['libelle']} {dto['code'] or ''}".casefold():
            rows.append(dto)
    return sorted(rows, key=lambda row: (row["libelle"], row["id"]))


def programmes(request, query):
    require(capabilities(request)["actions"]["can_list_programmes"])
    queryset = programme_queryset(request).order_by("-updated_at", "pk")
    if "curriculum" in query:
        queryset = queryset.filter(curriculum_id=query["curriculum"])
    result = []
    for programme in queryset:
        try:
            curriculum_identity(programme.curriculum, request.tenant, active=False)
        except (PracticalRuleError, ObjectDoesNotExist):
            continue
        latest = programme.revisions.order_by("-numero").first()
        if latest is None or ("statut" in query and latest.statut != query["statut"]):
            continue
        if query.get("q") and query["q"].casefold() not in f"{programme.code} {latest.titre}".casefold():
            continue
        result.append(programme)
    return result


def dossiers(request, query):
    require(any(_permitted_somewhere(request, key) for key in PERMISSIONS))
    queryset = model("DossierPratique").objects.filter(etablissement_id=request.tenant.pk).order_by("-created_at", "pk")
    if "programme" in query:
        queryset = queryset.filter(programme_revision__programme_id=query["programme"])
    if "statut" in query:
        queryset = queryset.filter(statut=query["statut"])
    result = []
    for dossier in queryset:
        if not readable(request, dossier):
            continue
        if query.get("q"):
            snapshot = dossier.snapshot
            labels = f"{snapshot['apprenant']['utilisateur']['nom']} {snapshot['apprenant']['matricule']} {snapshot['entreprise']['nom']}"
            if query["q"].casefold() not in labels.casefold():
                continue
        result.append(dossier)
    return result


def _prospective_permissions(user, programme, tenant):
    return {
        "can_consult": permission(user, "consult", tenant, programme=programme),
        "can_validate": permission(user, "validate", tenant, programme=programme),
        "can_evaluate": permission(user, "evaluate", tenant, programme=programme),
    }


def eligible_convention(convention, programme, request):
    binding = convention_binding(convention, programme, request.tenant)
    tutor = get_user_model().objects.get(pk=binding["tutor"].pk)
    permissions = _prospective_permissions(tutor, programme, request.tenant)
    if not permissions["can_validate"] and not permissions["can_evaluate"]:
        raise PracticalRuleError("Le tuteur doit être habilité à valider ou évaluer.", field="convention")
    binding["dto"]["habilitations_tuteur"] = {
        "can_validate": permissions["can_validate"], "can_evaluate": permissions["can_evaluate"]
    }
    if binding["partner"]:
        partner = get_user_model().objects.get(pk=binding["partner"].pk)
        if not any(_prospective_permissions(partner, programme, request.tenant).values()):
            binding["partner"] = None
            binding["dto"]["partenaire_lie"] = None
    return binding


def _convention_context(convention, programme, tenant):
    """Resolve visibility without treating active-work prerequisites as permission."""
    try:
        learner = convention.eleve if secondary() else convention.etudiant
        tenant_id = learner.etablissement_id if secondary() else learner.universite_id
        if tenant_id != tenant.pk or not local_user(learner.user, tenant, active=False):
            raise NotFound()
        if secondary():
            registrations = learner.inscriptions.filter(
                classe_id=programme.curriculum_id, annee_scolaire__etablissement_id=tenant.pk,
            )
        else:
            if (
                convention.offre.formation_id != programme.curriculum_id
                or convention.offre.entreprise_id != convention.entreprise_id
            ):
                raise NotFound()
            registrations = learner.inscriptions_admin.filter(
                formation_id=programme.curriculum_id, annee_universitaire__universite_id=tenant.pk,
            )
        if not registrations.exists():
            raise NotFound()
    except ObjectDoesNotExist as error:
        raise NotFound() from error


def selected_revision(programme, numero):
    revision = programme.revisions.filter(numero=numero, statut="publie").first()
    if revision is None:
        raise PracticalConflict("La révision sélectionnée n'est plus publiée.")
    return revision


def convention_candidates(request, programme, numero, query=""):
    require(manages(request, programme=programme))
    selected_revision(programme, numero)
    linked = model("DossierPratique").objects.values("convention_id")
    queryset = model("ConventionStage").objects.filter(statut="complete").exclude(pk__in=linked).order_by("-date_debut", "pk")
    rows = []
    for convention in queryset:
        try:
            dto = eligible_convention(convention, programme, request)["dto"]
        except (PracticalRuleError, ObjectDoesNotExist, ValueError, TypeError):
            continue
        if query and query.casefold() not in dto["libelle"].casefold():
            continue
        rows.append(dto)
    return rows


def partner_candidates(request, programme, convention_id, numero, query=""):
    if not secondary():
        raise NotFound()
    require(manages(request, programme=programme))
    selected_revision(programme, numero)
    convention = model("ConventionStage").objects.filter(pk=convention_id).first()
    if convention is None or model("DossierPratique").objects.filter(convention_id=convention_id).exists():
        raise NotFound()
    try:
        binding = eligible_convention(convention, programme, request)
    except (PracticalRuleError, ObjectDoesNotExist, ValueError, TypeError) as error:
        raise NotFound() from error
    candidates = get_user_model().objects.filter(etablissement_id=request.tenant.pk, is_active=True).exclude(
        pk__in=[binding["learner"].user_id, binding["tutor"].pk]
    )
    rows = []
    for user in candidates.order_by("pk"):
        grants = _prospective_permissions(user, programme, request.tenant)
        label = actor(user)
        if any(grants.values()) and (not query or query.casefold() in label["nom"].casefold()):
            rows.append({"utilisateur": label, **grants})
    return sorted(rows, key=lambda row: (row["utilisateur"]["nom"], row["utilisateur"]["id"]))


def create_programme(request, data):
    refresh_context(request)
    require(manages(request))
    data = validate(wire.CreateProgramme, data)
    try:
        with transaction.atomic(), practical_command():
            refresh_context(request)
            require(manages(request))
            source = curriculum_model().objects.select_for_update().filter(pk=data["curriculum"]).first()
            if source is None:
                raise NotFound()
            try:
                curriculum_dto(source, request.tenant)
            except PracticalRuleError as error:
                raise NotFound() from error
            if model("ProgrammePratique").objects.filter(
                etablissement=request.tenant, curriculum=source, code=data["code"]
            ).exists():
                raise PracticalConflict("Ce programme existe déjà.", "programme_existant")
            programme = model("ProgrammePratique").objects.create(
                etablissement=request.tenant, curriculum=source, code=data["code"], cree_par=request.user,
            )
            revision = model("RevisionProgrammePratique").objects.create(
                programme=programme, numero=1, cree_par=request.user,
                **{field: data[field] for field in ("titre", "minutes_requises", "competences")},
            )
            audit(request, programme, "programme_creation", revision_id=revision.pk)
            return programme_envelope(programme, request)
    except IntegrityError as error:
        if model("ProgrammePratique").objects.filter(
            etablissement=request.tenant, curriculum_id=data["curriculum"], code=data["code"]
        ).exists():
            raise PracticalConflict("Ce programme existe déjà.", "programme_existant") from error
        raise


PROGRAMME_COMMANDS = {
    "configuration": wire.ConfigureProgramme,
    "publication": wire.Version,
    "revision": wire.ReviseProgramme,
    "archivage": wire.ArchiveProgramme,
}


def programme_command(request, programme_id, action, data):
    refresh_context(request)
    get_programme(request, programme_id)
    data = validate(PROGRAMME_COMMANDS[action], data)
    with transaction.atomic(), practical_command():
        programme = get_programme(request, programme_id, locked=True)
        refresh_context(request)
        programme = get_programme(request, programme_id)
        compare_version(programme, data["version"])
        current = programme.revisions.order_by("-numero").first()
        if action in ("configuration", "publication"):
            if current.statut != "brouillon":
                raise PracticalConflict("La révision courante n'est pas un brouillon.")
            if action == "configuration":
                for field in ("titre", "minutes_requises", "competences"):
                    setattr(current, field, deepcopy(data[field]))
                current.save(update_fields=["titre", "minutes_requises", "competences"])
            else:
                _publish(request, programme, current)
        elif action == "revision":
            source = programme.revisions.filter(
                numero=data["revision_source"], statut__in=["publie", "archive"]
            ).first()
            if source is None or programme.revisions.filter(statut="brouillon").exists():
                raise PracticalConflict("Une source publiée/archivée et l'absence de brouillon sont requises.")
            current = model("RevisionProgrammePratique").objects.create(
                programme=programme, numero=current.numero + 1, cree_par=request.user,
                titre=source.titre, minutes_requises=source.minutes_requises,
                competences=deepcopy(source.competences),
            )
        elif action == "archivage":
            current = programme.revisions.filter(numero=data["revision"]).first()
            if current is None or current.statut == "archive":
                raise PracticalConflict("Cette révision ne peut pas être archivée.")
            _archive_revision(current, request.user)
        advance(programme)
        audit(
            request, programme, f"programme_{action}", revision_id=current.pk, motif=data.get("motif")
        )
        return programme_envelope(programme, request)


def _archive_revision(revision, user):
    revision.statut = "archive"
    revision.archived_at = timezone.now()
    revision.archive_par = user
    revision.save(update_fields=["statut", "archived_at", "archive_par"])


def _publish(request, programme, revision):
    if revision.minutes_requises <= 0 or not revision.competences:
        raise PracticalRuleError(
            "Des minutes positives et au moins une compétence sont requises.", "programme_incomplet"
        )
    criteria(revision.competences, published=True)
    source = curriculum_model().objects.select_for_update().get(pk=programme.curriculum_id)
    curriculum = curriculum_dto(source, request.tenant)
    now = timezone.now()
    snapshot = {
        "programme_id": programme.pk, "revision_id": revision.pk, "revision": revision.numero,
        "code": programme.code, "titre": revision.titre, "curriculum": curriculum,
        "minutes_requises": revision.minutes_requises, "competences": deepcopy(revision.competences),
        "offre_source": curriculum["offre"], "published_at": stamp(now),
    }
    snapshot["sha256"] = canonical_hash(snapshot)
    for published in programme.revisions.filter(statut="publie").order_by("pk"):
        _archive_revision(published, request.user)
    revision.statut, revision.snapshot = "publie", snapshot
    revision.published_at, revision.publie_par = now, request.user
    revision.save(update_fields=["statut", "snapshot", "published_at", "publie_par"])


def open_dossier(request, data):
    refresh_context(request)
    require(_permitted_somewhere(request, "manage"))
    if not secondary() and isinstance(data, dict) and "partenaire_utilisateur" in data:
        raise ValidationError({"partenaire_utilisateur": ["Champ réservé au secondaire."]})
    data = validate(wire.OpenDossier, data)
    programme = get_programme(request, data["programme"])
    require(manages(request, programme=programme))
    try:
        with transaction.atomic(), practical_command():
            programme = get_programme(request, programme.pk, locked=True)
            convention = model("ConventionStage").objects.filter(pk=data["convention"]).first()
            if convention is None:
                raise NotFound()
            _convention_context(convention, programme, request.tenant)
            learner_field = "eleve" if secondary() else "etudiant"
            learner_model = model("ConventionStage")._meta.get_field(learner_field).remote_field.model
            learner_id = getattr(convention, f"{learner_field}_id")
            learner_model.objects.select_for_update().get(pk=learner_id)
            convention = model("ConventionStage").objects.select_for_update().get(pk=convention.pk)
            refresh_context(request)
            programme = get_programme(request, programme.pk)
            require(manages(request, programme=programme))
            _convention_context(convention, programme, request.tenant)
            compare_version(programme, data["programme_version"], programme=True)
            if getattr(convention, f"{learner_field}_id") != learner_id:
                raise PracticalConflict("La convention a changé. Rechargez les choix.", "convention_modifiee")
            if model("DossierPratique").objects.filter(convention=convention).exists():
                raise PracticalConflict("La convention est déjà liée à un dossier.", "convention_deja_liee")
            revision = selected_revision(programme, data["revision"])
            try:
                binding = eligible_convention(convention, programme, request)
            except (PracticalRuleError, ObjectDoesNotExist, ValueError, TypeError) as error:
                raise PracticalConflict("La convention n'est plus éligible.", "convention_modifiee") from error
            if binding["dto"]["empreinte"] != data["convention_empreinte"]:
                raise PracticalConflict("La convention a changé. Rechargez les choix.", "convention_modifiee")
            partner = binding["partner"]
            if secondary() and data.get("partenaire_utilisateur") is not None:
                partner = get_user_model().objects.filter(pk=data["partenaire_utilisateur"]).first()
                if (
                    not local_user(partner, request.tenant)
                    or partner.pk in (binding["learner"].user_id, binding["tutor"].pk)
                    or not any(_prospective_permissions(partner, programme, request.tenant).values())
                ):
                    raise ValidationError({"partenaire_utilisateur": ["Partenaire local habilité requis."]})
            extra = {} if secondary() else {"contact_entreprise": binding["contact"]}
            dossier = model("DossierPratique").objects.create(
                etablissement=request.tenant, convention=convention, programme_revision=revision,
                apprenant=binding["learner"], inscription=binding["registration"],
                apprenant_user=binding["learner"].user, tuteur_interne_user=binding["tutor"],
                partenaire_user=partner, snapshot=deepcopy(binding["dto"]),
                programme_snapshot=deepcopy(revision.snapshot), identite=deepcopy(binding["identity"]),
                date_debut=convention.date_debut, date_fin=convention.date_fin,
                fuseau_horaire=request.tenant.fuseau_horaire, cree_par=request.user, **extra,
            )
            audit(request, dossier, "dossier_ouverture", revision_id=revision.pk)
            return dossier_envelope(dossier, request)
    except IntegrityError as error:
        if model("DossierPratique").objects.filter(convention_id=data["convention"]).exists():
            raise PracticalConflict("La convention est déjà liée à un dossier.", "convention_deja_liee") from error
        raise


def _decision(request, dossier, hour, action, state, *, reason=None, replacement=None, creation=False):
    before = None if creation else hour.statut
    sequence = (hour.decisions.aggregate(number=Max("sequence"))["number"] or 0) + 1
    decision = model("DecisionHeurePratique").objects.create(
        heure=hour, sequence=sequence, action=action, etat_avant=before, etat_apres=state,
        motif=reason, acteur=request.user, acteur_nom=actor(request.user)["nom"],
        version_dossier=dossier.version, heure_remplacement=replacement,
    )
    if hour.statut != state:
        hour.statut = state
        hour.save(update_fields=["statut"])
    return decision


def dossier_command(request, dossier_id, action, data):
    refresh_context(request)
    dossier = get_dossier(request, dossier_id)
    require(manages(request, dossier))
    data = validate(wire.Version if action == "cloture" else wire.Reason, data)
    with locked_dossier(request, dossier_id) as dossier:
        require(manages(request, dossier))
        compare_version(dossier, data["version"])
        cancelled = []
        if action == "partenaire_revocation":
            if not dossier.partenaire_user_id or dossier.partenaire_revoque_le is not None:
                raise PracticalConflict("Aucun accès partenaire non révoqué.")
            dossier.partenaire_revoque_le = timezone.now()
            dossier.partenaire_revoque_par = request.user
            dossier.motif_revocation = data["motif"]
            dossier.version += 1
            dossier.save(update_fields=[
                "version", "partenaire_revoque_le", "partenaire_revoque_par", "motif_revocation"
            ])
            audit(request, dossier, action, motif=data["motif"], heures_annulees=[])
            return dossier_envelope(dossier, request)
        assert_work_bindings(request, dossier)
        if action == "cloture":
            report = wire.report_dto(dossier, request)
            if not report["seuils_atteints"]:
                raise PracticalConflict(
                    "Les exigences pratiques ne sont pas atteintes.", "seuils_non_atteints",
                    unmet=report["criteres_non_satisfaits"],
                )
        elif action != "annulation":
            raise NotFound()
        dossier.version += 1
        for hour in dossier.heures.filter(statut__in=["brouillon", "soumise"]).order_by("pk").select_for_update():
            _decision(
                request, dossier, hour, "fermeture" if action == "cloture" else "annulation",
                "annulee", reason=data.get("motif"),
            )
            cancelled.append(hour.pk)
        if action == "cloture":
            dossier.statut, dossier.closed_at, dossier.clos_par = "clos", timezone.now(), request.user
            fields = ["statut", "closed_at", "clos_par"]
        else:
            dossier.statut, dossier.cancelled_at, dossier.annule_par = "annule", timezone.now(), request.user
            dossier.motif_annulation = data["motif"]
            fields = ["statut", "cancelled_at", "annule_par", "motif_annulation"]
        dossier.save(update_fields=["version", *fields])
        audit(request, dossier, f"dossier_{action}", motif=data.get("motif"), heures_annulees=cancelled)
        return dossier_envelope(dossier, request, cancelled)


def _interval(request, dossier, data, *, replaced=None):
    left, right, amount = wall_interval(
        data["date"], data["heure_debut"], data["heure_fin"], data["pause_minutes"],
        dossier.fuseau_horaire, timezone.now(), dossier.date_debut, dossier.date_fin,
    )
    conflicts = model("HeurePratique").objects.filter(
        dossier__etablissement_id=request.tenant.pk, apprenant_id=dossier.apprenant_id,
        date=data["date"], statut__in=LIVE_STATES, minute_debut__lt=right, minute_fin__gt=left,
    )
    if replaced:
        conflicts = conflicts.exclude(pk=replaced.pk)
    if conflicts.exists():
        raise PracticalConflict("Cet intervalle est déjà occupé.", "intervalle_occupe")
    return left, right, amount


def _evidence_metadata(upload):
    if upload is None:
        return None
    try:
        validate_exam_copy(upload)
        name = get_valid_filename(PurePosixPath(upload.name.replace("\\", "/")).name)[:200]
        if not name or not upload.size:
            raise DjangoValidationError("Un PDF non vide est requis.")
        return {"fichier_nom": name, "fichier_taille": upload.size, "fichier_sha256": hash_uploaded_file(upload)}
    except (DjangoValidationError, ValueError, TypeError) as error:
        raise PracticalRuleError("Le justificatif PDF est invalide.", "pdf_invalide", "fichier") from error


@contextmanager
def evidence_transaction():
    # This outer scope also sees transaction commit/audit failures, not just save failures.
    written = []
    try:
        yield written
    except BaseException:
        for storage, key in reversed(written):
            try:
                storage.delete(key)
            except OSError:
                logger.exception("Échec du nettoyage d'une nouvelle preuve pratique.")
        raise


def _insert_evidenced(owner, upload, metadata, written):
    if upload is None:
        owner.save(force_insert=True)
        return owner
    for field, value in metadata.items():
        setattr(owner, field, value)
    field = owner._meta.get_field("fichier")
    key = field.generate_filename(owner, upload.name)
    upload.seek(0)
    stored_key = field.storage.save(key, upload, max_length=field.max_length)
    written.append((field.storage, stored_key))
    owner.fichier = stored_key
    owner.save(force_insert=True)
    return owner


HOUR_COMMANDS = {
    "creation": wire.RecordHour, "remplacement": wire.ReplaceHour,
    "soumission": wire.Version, "validation": wire.Version,
    "rejet": wire.Reason, "annulation": wire.Reason, "invalidation": wire.Reason,
}
HOUR_TRANSITIONS = {
    "soumission": (("brouillon",), "soumise"),
    "validation": (("soumise",), "validee"),
    "rejet": (("soumise",), "rejetee"),
    "annulation": (("brouillon", "soumise"), "annulee"),
    "invalidation": (("validee",), "annulee"),
}


def hour_command(request, dossier_id, action, data, heure_id=None, upload=None):
    refresh_context(request)
    dossier = get_dossier(request, dossier_id)
    hour = get_hour(dossier, heure_id) if heure_id is not None else None
    authorize_hour(request, dossier, action, hour)
    data = validate(HOUR_COMMANDS[action], data)
    if upload is not None and action not in ("creation", "remplacement"):
        raise ValidationError({"fichier": ["Aucun fichier n'est accepté pour cette action."]})
    with evidence_transaction() as written:
        with locked_dossier(request, dossier_id) as dossier:
            hour = get_hour(dossier, heure_id, locked=True) if heure_id is not None else None
            authorize_hour(request, dossier, action, hour)
            compare_version(dossier, data["version"])
            assert_work_bindings(request, dossier)
            previous = None
            if action in ("creation", "remplacement"):
                if action == "remplacement":
                    if hour.statut not in ("brouillon", "rejetee", "annulee") or dossier.heures.filter(remplace=hour).exists():
                        raise PracticalConflict("Cette heure ne peut pas être remplacée.")
                    previous = hour
                left, right, amount = _interval(request, dossier, data, replaced=previous)
                metadata = _evidence_metadata(upload)
                dossier.version += 1
                hour = model("HeurePratique")(
                    dossier=dossier, apprenant_id=dossier.apprenant_id, date=data["date"],
                    minute_debut=left, minute_fin=right, pause_minutes=data["pause_minutes"],
                    minutes=amount, activite=data["activite"], saisi_par=request.user,
                    version_creation=dossier.version, remplace=previous,
                )
                _insert_evidenced(hour, upload, metadata, written)
                _decision(request, dossier, hour, "creation", "brouillon", creation=True)
                if previous:
                    _decision(
                        request, dossier, previous, "remplacement", "annulee",
                        reason=data["motif"], replacement=hour,
                    )
            else:
                allowed, state = HOUR_TRANSITIONS[action]
                if hour.statut not in allowed:
                    raise PracticalConflict("L'état de l'heure n'autorise pas cette action.")
                dossier.version += 1
                _decision(request, dossier, hour, action, state, reason=data.get("motif"))
            dossier.save(update_fields=["version"])
            audit(request, dossier, f"heure_{action}", heure_id=hour.pk, motif=data.get("motif"))
            return {
                "version": dossier.version, "heure": wire.hour_dto(hour, dossier, request),
                "heure_precedente": wire.hour_dto(previous, dossier, request) if previous else None,
            }


def assert_criterion(dossier, code):
    if code not in {criterion["code"] for criterion in dossier.programme_snapshot["competences"]}:
        raise PracticalRuleError("Compétence absente du programme publié.", "competence_inconnue", "code")


def assess_competency(request, dossier_id, code, data, upload=None):
    refresh_context(request)
    dossier = get_dossier(request, dossier_id)
    require(can_decide(request, dossier, "evaluate"))
    data = validate(wire.AssessCompetency, data)
    with evidence_transaction() as written:
        with locked_dossier(request, dossier_id) as dossier:
            require(can_decide(request, dossier, "evaluate"))
            compare_version(dossier, data["version"])
            assert_work_bindings(request, dossier)
            assert_criterion(dossier, code)
            day = data["date_observation"]
            if not dossier.date_debut <= day <= dossier.date_fin:
                raise PracticalRuleError("L'observation est hors convention.", "hors_periode", "date_observation")
            if day > timezone.now().astimezone(ZoneInfo(dossier.fuseau_horaire)).date():
                raise PracticalRuleError("L'observation ne peut être future.", "travail_futur", "date_observation")
            previous = dossier.evaluations_pratiques.filter(code=code).order_by("-revision").select_for_update().first()
            if bool(previous) != ("motif_revision" in data):
                raise ValidationError({
                    "motif_revision": ["Un motif est requis uniquement pour réviser une évaluation existante."]
                })
            metadata = _evidence_metadata(upload)
            dossier.version += 1
            assessment = model("EvaluationCompetencePratique")(
                dossier=dossier, code=code, revision=previous.revision + 1 if previous else 1,
                acquise=data["acquise"], contexte_professionnel=data["contexte_professionnel"],
                date_observation=day, motif_revision=data.get("motif_revision"), remplace=previous,
                evalue_par=request.user, evaluateur_nom=actor(request.user)["nom"],
                version_creation=dossier.version,
            )
            _insert_evidenced(assessment, upload, metadata, written)
            dossier.save(update_fields=["version"])
            audit(
                request, dossier, "competence_evaluation", evaluation_id=assessment.pk,
                motif=data.get("motif_revision"),
            )
            return {"version": dossier.version, "evaluation": wire.assessment_dto(assessment)}
