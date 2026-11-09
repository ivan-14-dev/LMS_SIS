"""Strict command inputs and the pinned practical v2 wire projection."""

import re
from copy import deepcopy

from rest_framework import serializers

from sis_common.practical_access import (
    can_decide,
    can_record,
    effective_permissions,
    manages,
    usable,
)
from sis_common.practical_bindings import actor, binding_status, curriculum_dto, offering, secondary, stamp
from sis_common.practical_rules import CODE_PATTERN, PracticalRuleError, clock, criteria

BASE = "/api/v1/stages/pratique/"


class Integer(serializers.IntegerField):
    def __init__(self, **kwargs):
        super().__init__(min_value=kwargs.pop("min_value", 1), max_value=kwargs.pop("max_value", 9007199254740991), **kwargs)

    def to_internal_value(self, data):
        if type(data) is not int:
            self.fail("invalid")
        return super().to_internal_value(data)


class Text(serializers.CharField):
    def to_internal_value(self, data):
        if not isinstance(data, str):
            self.fail("invalid")
        return super().to_internal_value(data)


class Code(Text):
    def to_internal_value(self, data):
        if not isinstance(data, str) or not re.fullmatch(CODE_PATTERN, data):
            raise serializers.ValidationError("Un code stable de 1 à 64 caractères est requis.")
        return data


class Fingerprint(Text):
    def to_internal_value(self, data):
        if not isinstance(data, str) or not re.fullmatch(r"[0-9a-f]{64}", data):
            raise serializers.ValidationError("Une empreinte SHA256 hexadécimale est requise.")
        return data


class Day(serializers.DateField):
    def to_internal_value(self, data):
        if not isinstance(data, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", data):
            raise serializers.ValidationError("Une date YYYY-MM-DD est requise.")
        return super().to_internal_value(data)


class Boolean(serializers.BooleanField):
    def to_internal_value(self, data):
        if type(data) is not bool:
            self.fail("invalid", input=data)
        return data


class Criteria(serializers.Field):
    def to_internal_value(self, data):
        return criteria(data)


class Command(serializers.Serializer):
    def to_internal_value(self, data):
        if not isinstance(data, dict):
            raise serializers.ValidationError({"non_field_errors": ["Un objet est requis."]})
        extra = set(data) - set(self.fields)
        if extra:
            raise serializers.ValidationError({key: ["Champ non autorisé."] for key in sorted(extra)})
        return super().to_internal_value(data)


class Version(Command):
    version = Integer()


class ConfigureProgramme(Version):
    titre = Text(max_length=200)
    minutes_requises = Integer(min_value=0, max_value=2147483647)
    competences = Criteria()


class CreateProgramme(ConfigureProgramme):
    version = Integer(min_value=0, max_value=0)
    curriculum = Integer()
    code = Code()


class ReviseProgramme(Version):
    revision_source = Integer()


class Reason(Version):
    motif = Text(max_length=4000)


class ArchiveProgramme(Reason):
    revision = Integer()


class OpenDossier(Command):
    version = Integer(min_value=0, max_value=0)
    programme = Integer()
    programme_version = Integer()
    revision = Integer()
    convention = Integer()
    convention_empreinte = Fingerprint()
    partenaire_utilisateur = Integer(allow_null=True, required=False, default=None)


class RecordHour(Version):
    date = Day()
    heure_debut = Text(max_length=5, trim_whitespace=False)
    heure_fin = Text(max_length=5, trim_whitespace=False)
    pause_minutes = Integer(min_value=0, max_value=1439)
    activite = Text(max_length=4000)


class ReplaceHour(RecordHour):
    motif = Text(max_length=4000)


class AssessCompetency(Version):
    acquise = Boolean()
    contexte_professionnel = Text(max_length=4000)
    date_observation = Day()
    motif_revision = Text(max_length=4000, required=False)


def revision_dto(revision):
    return {
        "id": revision.pk, "numero": revision.numero, "statut": revision.statut,
        "titre": revision.titre, "minutes_requises": revision.minutes_requises,
        "competences": revision.competences, "offre_source": revision.snapshot.get("offre_source"),
        "created_at": stamp(revision.created_at), "cree_par": actor(revision.cree_par),
        "published_at": stamp(revision.published_at), "publie_par": actor(revision.publie_par),
        "archived_at": stamp(revision.archived_at), "archive_par": actor(revision.archive_par),
    }


def programme_dto(programme, request):
    revisions = list(programme.revisions.order_by("-numero"))
    current = revisions[0]
    published = next((item for item in revisions if item.statut == "publie"), None)
    manager = manages(request, programme=programme)
    curriculum = curriculum_dto(programme.curriculum, request.tenant, active=False, validate_offering=False)
    try:
        curriculum["offre"] = offering(programme.curriculum)
    except PracticalRuleError:
        # A malformed live offering must not prevent historical reads or archival.
        # Creation, publication and convention selection still validate that offering.
        pass
    return {
        "id": programme.pk, "version": programme.version, "etablissement_id": programme.etablissement_id,
        "code": programme.code, "curriculum": curriculum,
        "revision_courante": revision_dto(current),
        "revision_publiee": revision_dto(published) if published else None,
        "created_at": stamp(programme.created_at), "updated_at": stamp(programme.updated_at),
        "permissions": effective_permissions(request, programme=programme),
        "actions": {
            "can_configure": manager and current.statut == "brouillon",
            "can_publish": manager and current.statut == "brouillon" and current.minutes_requises > 0 and bool(current.competences),
            "can_revise": manager and current.statut in ("publie", "archive"),
            "can_archive": manager and any(item.statut != "archive" for item in revisions),
            "can_open_dossier": manager and published is not None,
        },
    }


def evidence_dto(owner):
    if not owner.fichier:
        return None
    kind = "heures" if owner._meta.model_name == "heurepratique" else "evaluations"
    return {
        "nom": owner.fichier_nom, "taille": owner.fichier_taille, "sha256": owner.fichier_sha256,
        "content_type": "application/pdf", "version_creation": owner.version_creation,
        "download_url": f"{BASE}dossiers/{owner.dossier_id}/{kind}/{owner.pk}/preuve/",
        "actions": {"can_download": True},
    }


def decision_dto(decision):
    return {
        "id": decision.pk, "heure_id": decision.heure_id, "sequence": decision.sequence,
        "action": decision.action, "etat_avant": decision.etat_avant, "etat_apres": decision.etat_apres,
        "motif": decision.motif, "acteur": actor(decision.acteur, decision.acteur_nom),
        "created_at": stamp(decision.created_at), "version_dossier": decision.version_dossier,
        "heure_remplacement_id": decision.heure_remplacement_id,
    }


def hour_dto(hour, dossier, request):
    active = usable(request, dossier)
    original = hour.saisi_par_id == request.user.pk and can_record(request, dossier)
    decider = can_decide(request, dossier, "validate", hour)
    replacement = type(hour).objects.filter(remplace_id=hour.pk).values_list("pk", flat=True).first()
    return {
        "id": hour.pk, "dossier_id": hour.dossier_id, "date": hour.date.isoformat(),
        "heure_debut": clock(hour.minute_debut), "heure_fin": clock(hour.minute_fin),
        "pause_minutes": hour.pause_minutes, "minutes": hour.minutes, "activite": hour.activite,
        "statut": hour.statut, "saisi_par": actor(hour.saisi_par), "created_at": stamp(hour.created_at),
        "version_creation": hour.version_creation, "remplace_id": hour.remplace_id, "remplacement_id": replacement,
        "preuve": evidence_dto(hour), "derniere_decision": decision_dto(hour.decisions.order_by("-sequence").first()),
        "actions": {
            "can_submit": active and original and hour.statut == "brouillon",
            "can_replace": active and original and hour.statut in ("brouillon", "rejetee", "annulee") and replacement is None,
            "can_cancel": active and (original or manages(request, dossier)) and hour.statut in ("brouillon", "soumise"),
            "can_validate": active and decider and hour.statut == "soumise",
            "can_reject": active and decider and hour.statut == "soumise",
            "can_invalidate": active and decider and hour.statut == "validee",
        },
    }


def assessment_dto(assessment):
    return {
        "id": assessment.pk, "dossier_id": assessment.dossier_id, "code": assessment.code,
        "revision": assessment.revision, "acquise": assessment.acquise,
        "contexte_professionnel": assessment.contexte_professionnel,
        "date_observation": assessment.date_observation.isoformat(), "motif_revision": assessment.motif_revision,
        "remplace_id": assessment.remplace_id,
        "evalue_par": actor(assessment.evalue_par, assessment.evaluateur_nom),
        "created_at": stamp(assessment.created_at), "version_creation": assessment.version_creation,
        "preuve": evidence_dto(assessment),
        "effective": not type(assessment).objects.filter(
            dossier_id=assessment.dossier_id, code=assessment.code, revision__gt=assessment.revision
        ).exists(),
    }


def report_dto(dossier, request):
    from django.db.models import Sum

    totals = {row["statut"]: row["total"] for row in dossier.heures.values("statut").annotate(total=Sum("minutes"))}
    required = dossier.programme_snapshot["minutes_requises"]
    validated = totals.get("validee", 0)
    remaining = max(required - validated, 0)
    unmet = []
    if remaining:
        unmet.append({"type": "minutes", "code": None, "minutes_manquantes": remaining,
                      "detail": f"{remaining} minutes validées manquantes."})
    current = {}
    for assessment in dossier.evaluations_pratiques.order_by("code", "-revision"):
        current.setdefault(assessment.code, assessment)
    acquired, criteria_rows = 0, []
    can_evaluate = usable(request, dossier) and can_decide(request, dossier, "evaluate")
    for criterion in dossier.programme_snapshot["competences"]:
        assessment = current.get(criterion["code"])
        passed = bool(assessment and assessment.acquise)
        acquired += int(passed)
        if not passed:
            unmet.append({"type": "competence", "code": criterion["code"], "minutes_manquantes": None,
                          "detail": f"Compétence non acquise : {criterion['label']}."})
        criteria_rows.append({
            **criterion, "statut": "acquise" if passed else ("non_acquise" if assessment else "non_evaluee"),
            "evaluation": assessment_dto(assessment) if assessment else None,
            "actions": {"can_evaluate": can_evaluate},
        })
    manager = manages(request, dossier)
    return {
        "dossier_id": dossier.pk, "version": dossier.version, "statut": dossier.statut,
        "programme": deepcopy(dossier.programme_snapshot),
        "heures": {
            "minutes_requises": required, "minutes_validees": validated, "minutes_restantes": remaining,
            "minutes_excedentaires": max(validated - required, 0),
            "minutes_brouillon": totals.get("brouillon", 0), "minutes_soumises": totals.get("soumise", 0),
            "minutes_rejetees": totals.get("rejetee", 0), "minutes_annulees": totals.get("annulee", 0),
        },
        "competences": criteria_rows, "competences_requises": len(criteria_rows), "competences_acquises": acquired,
        "criteres_non_satisfaits": unmet, "seuils_atteints": not unmet, "cloture_reussie": dossier.statut == "clos",
        "closed_at": stamp(dossier.closed_at), "clos_par": actor(dossier.clos_par),
        "cancelled_at": stamp(dossier.cancelled_at), "annule_par": actor(dossier.annule_par),
        "motif_annulation": dossier.motif_annulation,
        "actions": {"can_close": manager and usable(request, dossier) and not unmet,
                    "can_cancel": manager and usable(request, dossier)},
    }


def dossier_dto(dossier, request, report=None):
    report = report or report_dto(dossier, request)
    snapshot = dossier.snapshot
    active = usable(request, dossier)
    linked = binding_status(dossier, request.tenant, active=False)
    blockages = []
    if not linked:
        blockages.append("liaison_modifiee")
    elif dossier.statut == "ouvert" and not binding_status(dossier, request.tenant):
        curriculum_inactive = not secondary() and not dossier.programme_revision.programme.curriculum.actif
        blockages.append("curriculum_inactif" if curriculum_inactive else "acteur_inactif")
    if dossier.fuseau_horaire != request.tenant.fuseau_horaire:
        blockages.append("fuseau_modifie")
    return {
        "id": dossier.pk, "version": dossier.version, "statut": dossier.statut, "convention_id": dossier.convention_id,
        "programme": deepcopy(dossier.programme_snapshot), "apprenant": snapshot["apprenant"],
        "inscription": snapshot["inscription"], "entreprise": snapshot["entreprise"],
        "tuteur_interne": snapshot["tuteur_interne"], "partenaire": actor(dossier.partenaire_user),
        "partenaire_revoque_le": stamp(dossier.partenaire_revoque_le),
        "periode": {"date_debut": dossier.date_debut.isoformat(), "date_fin": dossier.date_fin.isoformat(),
                    "fuseau_horaire": dossier.fuseau_horaire},
        "missions": snapshot["missions"], "liaisons_valides": linked, "blocages": blockages,
        "created_at": stamp(dossier.created_at), "cree_par": actor(dossier.cree_par),
        "closed_at": stamp(dossier.closed_at), "clos_par": actor(dossier.clos_par),
        "cancelled_at": stamp(dossier.cancelled_at), "annule_par": actor(dossier.annule_par),
        "motif_annulation": dossier.motif_annulation,
        "permissions": effective_permissions(request, dossier=dossier),
        "actions": {
            "can_enter_hours": active and can_record(request, dossier),
            "can_evaluate": active and can_decide(request, dossier, "evaluate"),
            "can_close": report["actions"]["can_close"], "can_cancel": report["actions"]["can_cancel"],
            "can_revoke_partner": manages(request, dossier) and bool(dossier.partenaire_user_id) and not dossier.partenaire_revoque_le,
            "can_view_report": True, "can_view_history": True,
        },
    }


def audit_dto(event):
    return {
        "id": event.pk, "action": event.action, "version": event.version,
        "acteur": actor(event.acteur, event.acteur_nom), "created_at": stamp(event.created_at),
        "motif": event.metadata.get("motif"), "revision_id": event.metadata.get("revision_id"),
        "heure_id": event.metadata.get("heure_id"), "evaluation_id": event.metadata.get("evaluation_id"),
        "heures_annulees": event.metadata.get("heures_annulees", []),
    }
