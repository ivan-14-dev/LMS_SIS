"""Read-only timetables scoped to the current learner's schooling."""

from django.apps import apps
from django.db.models import F, Q
from rest_framework.exceptions import PermissionDenied

from .lms_access_sync import REVOKED_LEARNER_STATUSES


def school_timetable(request):
    from apps.emplois_du_temps.models import Creneau

    learner = request.user.eleve_profile
    classe = learner.classe_actuelle
    if learner.statut in REVOKED_LEARNER_STATUSES or classe is None:
        return []
    tenant_id = request.tenant.pk
    if (
        classe.etablissement_id not in (None, tenant_id)
        or classe.annee_scolaire.etablissement_id != tenant_id
        or classe.niveau.etablissement_id != tenant_id
    ):
        raise PermissionDenied("La classe ne relève pas de cet établissement.")
    if (
        learner.inscriptions.filter(annee_scolaire_id=classe.annee_scolaire_id)
        .exclude(statut="validee", classe_id=classe.pk)
        .exists()
    ):
        return []
    slots = (
        Creneau.objects.filter(
            Q(matiere__etablissement_id=tenant_id) | Q(matiere__etablissement__isnull=True),
            classe=classe,
            actif=True,
        )
        .select_related("matiere", "salle")
        .order_by("jour", "heure_debut", "pk")
    )
    return [
        {
            "id": slot.pk,
            "jour": slot.get_jour_display(),
            "debut": str(slot.heure_debut),
            "fin": str(slot.heure_fin),
            "cours": slot.matiere.nom,
            "salle": slot.salle.nom if slot.salle else "",
            "groupe": classe.nom,
            "periode": (
                str(slot.date_specifique)
                if slot.date_specifique
                else (f"Semaine {slot.semaine}" if slot.semaine else "Toutes les semaines")
            ),
        }
        for slot in slots
    ]


def _group_scope(td, tp):
    scope = Q(groupe="")
    if td:
        scope |= Q(type_cours="TD", groupe=td)
    if tp:
        scope |= Q(type_cours="TP", groupe=tp)
    return scope


def university_timetable(request):
    from apps.emplois_du_temps.models import CreneauCours
    from apps.etudiants.models import AffectationECUEIndividuelle, InscriptionPedagogique

    learner = request.user.etudiant_profile
    if learner.statut in REVOKED_LEARNER_STATUSES:
        return []
    registrations = learner.inscriptions_admin.filter(
        statut="validee", annee_universitaire__universite_id=request.tenant.pk
    )
    if learner.annee_universitaire_actuelle_id:
        registrations = registrations.filter(annee_universitaire_id=learner.annee_universitaire_actuelle_id)
    else:
        registrations = registrations.filter(annee_universitaire__en_cours=True)
    allowed = Q(pk__in=[])
    choices = (
        InscriptionPedagogique.objects.filter(
            inscription_admin__in=registrations,
            statut__in=("validee", "modifiee"),
            semestre__annee_universitaire_id=F("inscription_admin__annee_universitaire_id"),
        )
        .prefetch_related("ues", "ecues")
        .select_related("inscription_admin")
    )
    for choice in choices:
        ecues = [ecue.pk for ecue in choice.ecues.all()]
        subjects = Q(ecue_id__in=ecues) if ecues else Q(ecue__ue_id__in=[ue.pk for ue in choice.ues.all()])
        allowed |= (
            Q(semestre_id=choice.semestre_id, formation_id=choice.inscription_admin.formation_id)
            & subjects
            & _group_scope(choice.groupe_td, choice.groupe_tp)
        )
    individual = AffectationECUEIndividuelle.objects.filter(
        inscription_admin__in=registrations,
        semestre_cible__annee_universitaire_id=F("inscription_admin__annee_universitaire_id"),
    ).select_related("inscription_admin")
    for assignment in individual:
        allowed |= Q(
            semestre_id=assignment.semestre_cible_id,
            formation_id=assignment.inscription_admin.formation_id,
            ecue_id=assignment.ecue_id,
        ) & _group_scope(assignment.groupe_td, assignment.groupe_tp)
    slots = (
        CreneauCours.objects.filter(allowed)
        .filter(
            Q(formation__departement__isnull=True)
            | Q(formation__departement__faculte__universite_id=request.tenant.pk),
            semestre__annee_universitaire__universite_id=request.tenant.pk,
            ecue__ue__maquette__annee_universitaire__universite_id=request.tenant.pk,
            ecue__ue__maquette__formation_id=F("formation_id"),
        )
        .select_related("ecue", "salle", "creneau_horaire", "semestre")
        .order_by("jour", "creneau_horaire__heure_debut", "pk")
    )
    return [
        {
            "id": slot.pk,
            "jour": slot.get_jour_display(),
            "debut": str(slot.creneau_horaire.heure_debut),
            "fin": str(slot.creneau_horaire.heure_fin),
            "cours": slot.ecue.nom,
            "salle": slot.salle.nom if slot.salle else "",
            "groupe": slot.groupe,
            "periode": (
                f"{slot.semestre} · semaines {slot.semaine_debut}–{slot.semaine_fin}"
                f" · {slot.get_frequence_display()}"
                + (" · semaines paires" if slot.semaines_paires is True else "")
                + (" · semaines impaires" if slot.semaines_paires is False else "")
            ),
        }
        for slot in slots
    ]


def personal_timetable(request):
    return school_timetable(request) if apps.is_installed("apps.classes") else university_timetable(request)
