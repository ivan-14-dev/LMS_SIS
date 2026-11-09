"""Fresh named permissions and independent administrative/actor access paths."""

from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist
from django.db import connection
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied

from sis_common.module_registry import require_module
from sis_common.practical_bindings import binding_status, curriculum_identity, local_user, secondary
from sis_common.practical_rules import PERMISSIONS, PracticalRuleError, constraints


def refresh_context(request):
    user, tenant = getattr(request, "user", None), getattr(request, "tenant", None)
    if (
        not user or not user.is_authenticated or not tenant
        or tenant.schema_name == "public" or getattr(connection, "schema_name", None) != tenant.schema_name
        or user.etablissement_id != tenant.pk
    ):
        raise PermissionDenied("Contexte pratique inaccessible.", code="contexte_inactif")
    fresh_tenant = type(tenant).objects.filter(pk=tenant.pk, actif=True).first()
    fresh_user = get_user_model().objects.filter(pk=user.pk, etablissement_id=tenant.pk, is_active=True).first()
    if fresh_tenant is None or fresh_user is None:
        raise PermissionDenied("Contexte pratique inactif.", code="contexte_inactif")
    request.user, request.tenant = fresh_user, fresh_tenant
    require_module(fresh_tenant, "sis.practical_training")
    return fresh_user


def permission(user, name, tenant, programme=None, dossier=None):
    name = PERMISSIONS.get(name, name)
    if not local_user(user, tenant) or not user.has_perm(name):
        return False
    limits = {} if user.is_superuser else constraints(user.attributs_acces, name)
    if limits is None:
        return False
    context = {"etablissement_id": tenant.pk}
    if programme is not None:
        context["programme_id"] = programme.pk
    if dossier is not None:
        context["dossier_id"] = dossier.pk
        context["programme_id"] = dossier.programme_revision.programme_id
    return all(context.get(key) in values for key, values in limits.items())


def scoped(queryset, user, name, tenant, *, dossier=False):
    name = PERMISSIONS.get(name, name)
    if not local_user(user, tenant) or not user.has_perm(name):
        return queryset.none()
    limits = {} if user.is_superuser else constraints(user.attributs_acces, name)
    if limits is None:
        return queryset.none()
    paths = {"programme_id": "programme_revision__programme_id" if dossier else "pk"}
    if dossier:
        paths["dossier_id"] = "pk"
    for key, values in limits.items():
        if key == "etablissement_id":
            if tenant.pk not in values:
                return queryset.none()
        elif key not in paths:
            return queryset.none()
        else:
            queryset = queryset.filter(**{f"{paths[key]}__in": values})
    return queryset.filter(etablissement_id=tenant.pk)


def locally_bound(dossier, tenant):
    if dossier.etablissement_id != tenant.pk:
        return False
    try:
        curriculum_identity(dossier.programme_revision.programme.curriculum, tenant, active=False)
        learner = dossier.apprenant
        if (learner.etablissement_id if secondary() else learner.universite_id) != tenant.pk:
            return False
        users = [learner.user, dossier.apprenant_user, dossier.tuteur_interne_user]
        if dossier.partenaire_user_id:
            users.append(dossier.partenaire_user)
        if any(not local_user(user, tenant, active=False) for user in users):
            return False
        convention = dossier.convention
        tutor = convention.maitre_stage_etablissement if secondary() else convention.tuteur_pedagogique.user
        if not local_user(tutor, tenant, active=False):
            return False
        if not secondary() and convention.maitre_stage.user_id:
            if not local_user(convention.maitre_stage.user, tenant, active=False):
                return False
        return True
    except (ObjectDoesNotExist, PracticalRuleError):
        return False


def actor_kind(user, dossier, tenant):
    if not local_user(user, tenant) or not locally_bound(dossier, tenant):
        return None
    convention = dossier.convention
    if dossier.apprenant_user_id == user.pk and dossier.apprenant.user_id == user.pk:
        return "learner"
    tutor_id = (
        convention.maitre_stage_etablissement_id if secondary()
        else convention.tuteur_pedagogique.user_id
    )
    if dossier.tuteur_interne_user_id == user.pk == tutor_id:
        return "tutor"
    if dossier.partenaire_user_id != user.pk or dossier.partenaire_revoque_le:
        return None
    today = timezone.now().astimezone(ZoneInfo(tenant.fuseau_horaire)).date()
    if not dossier.date_debut <= today <= dossier.date_fin:
        return None
    if convention.entreprise_id != dossier.identite["entreprise"]:
        return None
    if not secondary():
        contact = convention.maitre_stage
        if (
            not contact.actif or not convention.entreprise.actif
            or contact.pk != dossier.contact_entreprise_id
            or contact.user_id != user.pk or contact.entreprise_id != convention.entreprise_id
        ):
            return None
    return "partner"


def manages(request, dossier=None, programme=None):
    return permission(request.user, "manage", request.tenant, programme, dossier)


def readable(request, dossier):
    if not locally_bound(dossier, request.tenant):
        return False
    if manages(request, dossier):
        return True
    kind = actor_kind(request.user, dossier, request.tenant)
    if not kind:
        return False
    names = ["consult", "enter"] + (["validate", "evaluate"] if kind != "learner" else [])
    return any(permission(request.user, name, request.tenant, dossier=dossier) for name in names)


def usable(request, dossier):
    return (
        dossier.statut == "ouvert" and dossier.fuseau_horaire == request.tenant.fuseau_horaire
        and binding_status(dossier, request.tenant)
    )


def can_record(request, dossier):
    return bool(
        actor_kind(request.user, dossier, request.tenant)
        and permission(request.user, "enter", request.tenant, dossier=dossier)
    )


def can_decide(request, dossier, kind, hour=None):
    return bool(
        actor_kind(request.user, dossier, request.tenant) in ("tutor", "partner")
        and request.user.pk != dossier.apprenant_user_id
        and (hour is None or request.user.pk != hour.saisi_par_id)
        and permission(request.user, kind, request.tenant, dossier=dossier)
    )


def effective_permissions(request, *, programme=None, dossier=None):
    return [
        name for name in PERMISSIONS.values()
        if permission(request.user, name, request.tenant, programme, dossier)
    ]
