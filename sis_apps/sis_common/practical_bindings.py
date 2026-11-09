"""Local curriculum/convention adapters; no legacy stage permission reuse."""

from datetime import UTC

from django.apps import apps
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import ValidationError

from sis_common.hierarchy import unit_path
from sis_common.institutional_profiles import validate_learning_offering
from sis_common.practical_rules import PracticalRuleError, canonical_hash


def secondary():
    return settings.SIS_VARIANT == "secondaire"


def model(name):
    return apps.get_model("stages", name)


def curriculum_model():
    return apps.get_model("classes", "Classe") if secondary() else apps.get_model("formations", "Formation")


def actor(user, name=None):
    if user is None:
        return None
    return {"id": user.pk, "nom": name or user.get_full_name() or user.username}


def stamp(value):
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z") if value else None


def period(value):
    return {
        "id": value.pk, "libelle": value.libelle,
        "date_debut": value.date_debut.isoformat(), "date_fin": value.date_fin.isoformat(),
    }


def local_user(user, tenant, *, active=True):
    return bool(user and user.etablissement_id == tenant.pk and (not active or user.is_active))


def offering(source):
    value = source.offre_configuration
    if value is None or value == {}:
        return None
    try:
        validate_learning_offering(value)
    except (DjangoValidationError, TypeError, KeyError, ValueError) as error:
        raise PracticalRuleError("L'offre académique est invalide.", field="curriculum") from error
    return {
        "code": value["code"], "label": value["label"], "version": value["version"],
        "mode_evaluation": value["assessment"]["mode"], "sha256": canonical_hash(value),
    }


def curriculum_identity(source, tenant, *, active=True):
    ids = []
    identity = {"id": source.pk}
    if secondary():
        ids = [source.etablissement_id, source.niveau.etablissement_id, source.annee_scolaire.etablissement_id]
        identity.update(niveau=source.niveau_id, annee=source.annee_scolaire_id)
        if source.annee_scolaire.date_fin < source.annee_scolaire.date_debut:
            raise PracticalRuleError("Année scolaire incohérente.", field="curriculum")
    else:
        if active and not source.actif:
            raise PracticalRuleError("La formation est inactive.", field="curriculum")
        if source.departement_id:
            ids.append(source.departement.faculte.universite_id)
            identity.update(departement=source.departement_id, faculte=source.departement.faculte_id)
        if source.ecole_doctorale_id:
            ids.append(source.ecole_doctorale.universite_id)
            identity["ecole_doctorale"] = source.ecole_doctorale_id
        if source.responsable_id and not local_user(source.responsable, tenant, active=False):
            raise PracticalRuleError("Responsable hors établissement.", field="curriculum")
    try:
        organization = unit_path(tenant, source.organisation_unit)
    except ValidationError as error:
        raise PracticalRuleError("Organisation hors établissement.", field="curriculum") from error
    if organization:
        ids.append(tenant.pk)
    identity["organisation"] = [unit.pk for unit in organization]
    if not ids or any(identifier != tenant.pk for identifier in ids):
        raise PracticalRuleError("Curriculum hors établissement.", field="curriculum")
    return identity


def curriculum_dto(source, tenant, *, active=True, validate_offering=True):
    curriculum_identity(source, tenant, active=active)
    return {
        "id": source.pk, "type": "classe" if secondary() else "formation",
        "libelle": source.nom, "code": None if secondary() else source.code,
        "annee": period(source.annee_scolaire) if secondary() else None,
        "offre": offering(source) if validate_offering else None,
    }


def convention_binding(convention, programme, tenant, *, active=True, inscription_id=None, validate_offering=True):
    source = programme.curriculum
    ancestry = curriculum_identity(source, tenant, active=active)
    learner = convention.eleve if secondary() else convention.etudiant
    learner_tenant = learner.etablissement_id if secondary() else learner.universite_id
    tutor = convention.maitre_stage_etablissement if secondary() else convention.tuteur_pedagogique.user
    if (
        learner_tenant != tenant.pk
        or not local_user(learner.user, tenant, active=active)
        or not local_user(tutor, tenant, active=active)
        or tutor.pk == learner.user_id
    ):
        raise PracticalRuleError("Acteurs inactifs ou hors établissement.", field="convention")
    if active and learner.statut not in ("inscrit", "redoublant"):
        raise PracticalRuleError("L'apprenant n'est pas inscrit.", field="convention")
    if (
        convention.statut != "complete" or not convention.date_signature_complete
        or convention.date_fin < convention.date_debut or not convention.missions.strip()
    ):
        raise PracticalRuleError("Une convention complète et cohérente est requise.", field="convention")
    if secondary():
        registrations = learner.inscriptions.filter(classe_id=source.pk, annee_scolaire_id=source.annee_scolaire_id)
        if active:
            registrations = registrations.filter(statut__in=["en_cours", "validee"])
        year_field = "annee_scolaire"
    else:
        if convention.offre.formation_id != source.pk or convention.offre.entreprise_id != convention.entreprise_id:
            raise PracticalRuleError("Offre et convention incohérentes.", field="convention")
        registrations = learner.inscriptions_admin.filter(formation_id=source.pk)
        if active:
            registrations = registrations.filter(statut="validee")
        year_field = "annee_universitaire"
    registrations = registrations.filter(**{
        f"{year_field}__date_debut__lte": convention.date_debut,
        f"{year_field}__date_fin__gte": convention.date_fin,
    })
    if inscription_id is not None:
        registrations = registrations.filter(pk=inscription_id)
    candidates = list(registrations.select_related(year_field)[:2])
    if len(candidates) != 1:
        raise PracticalRuleError("Une inscription locale couvrant la convention est requise.", field="convention")
    registration = candidates[0]
    year = getattr(registration, year_field)
    year_tenant = year.etablissement_id if secondary() else year.universite_id
    if year_tenant != tenant.pk or year.date_fin < year.date_debut:
        raise PracticalRuleError("Année hors établissement.", field="convention")
    if not secondary() and registration.parcours_id and registration.parcours.formation_id != source.pk:
        raise PracticalRuleError("Parcours incohérent.", field="convention")
    contact, partner = None, None
    if not secondary():
        contact = convention.maitre_stage
        partner = contact.user
        if contact.entreprise_id != convention.entreprise_id or (
            active and (not contact.actif or not convention.entreprise.actif)
        ):
            raise PracticalRuleError("Entreprise ou contact incohérent/inactif.", field="convention")
        if partner and (
            not local_user(partner, tenant, active=active) or partner.pk in (learner.user_id, tutor.pk)
        ):
            raise PracticalRuleError("Compte de contact incompatible.", field="convention")
    identity = {
        "convention": convention.pk, "apprenant": learner.pk, "apprenant_user": learner.user_id,
        "tuteur_user": tutor.pk, "tuteur": None if secondary() else convention.tuteur_pedagogique_id,
        "contact": contact.pk if contact else None, "contact_user": partner.pk if partner else None,
        "entreprise": convention.entreprise_id, "offre": None if secondary() else convention.offre_id,
        "date_debut": convention.date_debut.isoformat(), "date_fin": convention.date_fin.isoformat(),
        "signature": stamp(convention.date_signature_complete), "missions": convention.missions,
        "statut": convention.statut, "curriculum": ancestry, "inscription": registration.pk,
        "annee": {"id": year.pk, "debut": year.date_debut.isoformat(), "fin": year.date_fin.isoformat()},
    }
    dto = {
        "id": convention.pk, "empreinte": canonical_hash(identity),
        "libelle": f"{actor(learner.user)['nom']} — {convention.entreprise.raison_sociale}",
        "statut": "complete",
        "apprenant": {"id": learner.pk, "utilisateur": actor(learner.user), "matricule": learner.matricule},
        "curriculum": curriculum_dto(source, tenant, active=active, validate_offering=active and validate_offering),
        "inscription": {"id": registration.pk, "type": "inscription" if secondary() else "inscription_administrative",
                        "annee": period(year)},
        "entreprise": {"id": convention.entreprise_id, "nom": convention.entreprise.raison_sociale},
        "tuteur_interne": actor(tutor), "habilitations_tuteur": {"can_validate": False, "can_evaluate": False},
        "partenaire_lie": actor(partner), "mode_partenaire": "affectation_explicite" if secondary() else "contact_entreprise",
        "contact_entreprise_id": contact.pk if contact else None,
        "date_debut": identity["date_debut"], "date_fin": identity["date_fin"],
        "date_signature_complete": identity["signature"], "missions": convention.missions,
        "duree_planifiee_minutes": convention.duree_heures * 60 if secondary() else None,
    }
    return {"identity": identity, "dto": dto, "learner": learner, "tutor": tutor,
            "partner": partner, "contact": contact, "registration": registration}


def binding_status(dossier, tenant, *, active=True):
    try:
        binding = convention_binding(
            dossier.convention, dossier.programme_revision.programme, tenant,
            active=active, inscription_id=dossier.inscription_id, validate_offering=False,
        )
        return binding["identity"] == dossier.identite
    except (PracticalRuleError, ObjectDoesNotExist, ValueError, TypeError):
        return False
