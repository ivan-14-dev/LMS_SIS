"""Closed, tenant-scoped bridges to existing records. No permission or LMS side effects."""

from copy import copy
from dataclasses import dataclass
from importlib import import_module

from django.apps import apps
from django.conf import settings
from django.core.exceptions import ValidationError as ModelValidationError
from django.db import connection, transaction
from django.db.models import Q
from django.db.models.deletion import ProtectedError
from rest_framework.exceptions import PermissionDenied, ValidationError

from sis_common.authorization import has_business_permission_or_role
from sis_common.pagination import SISPagination


@dataclass(frozen=True)
class Target:
    label: str
    category: str
    model: str
    view: str
    owners: tuple = ()
    required_owners: tuple = ()
    search: tuple = ("nom",)
    details: tuple = ("nom", "code")
    relations: tuple = ()
    direct: bool = False


class PreserveOrganizationAttachmentsMixin:
    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError as error:
            attachment = apps.get_model("core.OrganizationAttachment")
            if not any(isinstance(item, attachment) for item in error.protected_objects):
                raise
            raise ValidationError({
                "detail": "Cet objet est rattaché à l’organisation ; sa suppression est refusée pour conserver l’historique.",
            }) from error


def target_registry():
    """Only reviewed models, fields and native read contracts may be used here."""
    targets = {
        "user": Target(
            "Utilisateurs", "users", "utilisateurs.Utilisateur", "utilisateurs.UtilisateursViewSet",
            required_owners=("etablissement",), search=("username", "first_name", "last_name"),
            details=("username", "first_name", "last_name", "is_active"),
        ),
        "book": Target(
            "Ressources — livres et documents", "resources", "bibliotheque.Livre", "bibliotheque.LivresViewSet",
            search=("titre", "auteurs", "isbn"), details=("titre", "auteurs", "isbn", "resume"),
        ),
    }
    if settings.SIS_VARIANT == "secondaire":
        class_owners = ("etablissement", "niveau__etablissement")
        class_required = ("annee_scolaire__etablissement",)
        targets.update({
            "course": Target(
                "Formations — classes", "courses", "classes.Classe", "classes.ClassesViewSet",
                owners=class_owners, required_owners=class_required, details=("nom", "offre_code"),
                relations=(("level", "niveau"),), direct=True,
            ),
            "level": Target(
                "Niveaux scolaires", "academic", "etablissement.Niveau", "etablissement.NiveauxViewSet",
                required_owners=("etablissement",), search=("libelle", "code"), details=("libelle", "code"),
            ),
            "group": Target(
                "Groupes d’élèves (TD, TP, options)", "academic", "classes.Groupe", "classes.GroupesViewSet",
                owners=("etablissement", "classes__etablissement", "classes__annee_scolaire__etablissement",
                        "classes__niveau__etablissement"),
                required_owners=("annee_scolaire__etablissement",), details=("nom", "type", "capacite"),
                relations=(("course", "classes"),),
            ),
            "subject": Target(
                "Matières", "academic", "classes.Matiere", "classes.MatieresViewSet",
                required_owners=("etablissement",), details=("nom", "code", "description"),
            ),
            "activity": Target(
                "Activités — créneaux de cours", "activities", "emplois_du_temps.Creneau",
                "emplois_du_temps.CreneauxViewSet",
                owners=("classe__etablissement", "classe__niveau__etablissement", "salle__etablissement"),
                required_owners=("classe__annee_scolaire__etablissement", "matiere__etablissement",
                                 "enseignant__user__etablissement"),
                search=("classe__nom", "matiere__nom"),
                details=("jour", "heure_debut", "heure_fin", "type", "date_specifique"),
                relations=(("course", "classe"), ("subject", "matiere")),
            ),
        })
    else:
        formation_owners = ("departement__faculte__universite", "ecole_doctorale__universite",
                            "responsable__etablissement", "maquettes__annee_universitaire__universite")
        targets.update({
            "course": Target(
                "Formations", "courses", "formations.Formation", "formations.FormationsViewSet",
                owners=formation_owners, details=("nom", "code", "niveau", "type", "offre_code"),
                relations=(("department", "departement"), ("school", "ecole_doctorale")), direct=True,
            ),
            "faculty": Target(
                "Facultés", "academic", "structure.Faculte", "structure.FacultesViewSet",
                required_owners=("universite",), details=("nom", "code", "description"),
            ),
            "department": Target(
                "Départements", "academic", "structure.Departement", "structure.DepartementsViewSet",
                required_owners=("faculte__universite",), relations=(("faculty", "faculte"),),
            ),
            "school": Target(
                "Écoles doctorales", "academic", "structure.EcoleDoctorale", "structure.EcolesDoctoralesViewSet",
                required_owners=("universite",),
            ),
            "track": Target(
                "Filières / parcours", "academic", "formations.Parcours", "formations.ParcoursViewSet",
                owners=tuple(f"formation__{field}" for field in formation_owners),
                relations=(("course", "formation"),), details=("nom", "code", "specialisation"),
            ),
            "teaching_unit": Target(
                "Unités d’enseignement", "academic", "ue_ecue.UE", "ue_ecue.UEViewSet",
                owners=tuple(f"maquette__formation__{field}" for field in formation_owners),
                required_owners=("maquette__annee_universitaire__universite",
                                 "semestre__annee_universitaire__universite"),
                details=("nom", "code", "credits_ects", "description"),
                relations=(("course", "maquette.formation"),),
            ),
            "subject": Target(
                "Éléments d’UE", "academic", "ue_ecue.ECUE", "ue_ecue.ECUEViewSet",
                owners=tuple(f"ue__maquette__formation__{field}" for field in formation_owners),
                required_owners=("ue__maquette__annee_universitaire__universite",
                                 "ue__semestre__annee_universitaire__universite"),
                details=("nom", "code", "credits_ects", "description"), relations=(("teaching_unit", "ue"),),
            ),
            "activity": Target(
                "Activités — créneaux de cours", "activities", "emplois_du_temps.CreneauCours",
                "emplois_du_temps.CreneauCoursViewSet",
                owners=tuple(f"formation__{field}" for field in formation_owners)
                + tuple(f"ecue__ue__maquette__formation__{field}" for field in formation_owners) + (
                    "enseignant__user__etablissement", "salle__departement_gestionnaire__faculte__universite",
                ),
                required_owners=("semestre__annee_universitaire__universite",
                                 "ecue__ue__maquette__annee_universitaire__universite"),
                search=("formation__nom", "ecue__nom"),
                details=("jour", "type_cours", "groupe", "semaine_debut", "semaine_fin",
                         "creneau_horaire.heure_debut", "creneau_horaire.heure_fin"),
                relations=(("course", "formation"), ("subject", "ecue")),
            ),
        })
    return targets


def configuration_admin(user):
    secondary = settings.SIS_VARIANT == "secondaire"
    return user.is_active and has_business_permission_or_role(
        user,
        "etablissement.change_etablissement" if secondary else "etablissement.change_universite",
        ("direction", "responsable_pedagogique") if secondary else (
            "president", "vice_president", "doyen", "directeur_etudes", "scolarite",
        ),
    )


def scoped_targets(target, tenant):
    # Models without an owner FK (notably the library catalogue) are isolated by schema.
    if connection.schema_name != tenant.schema_name or tenant.schema_name == "public":
        raise PermissionDenied("Un schéma d’établissement actif est requis.")
    queryset = apps.get_model(target.model).objects.all()
    for field in target.required_owners:
        queryset = queryset.filter(**{field: tenant.pk})
    for field in target.owners:
        queryset = queryset.exclude(Q(**{f"{field}__isnull": False}) & ~Q(**{field: tenant.pk}))
    return queryset.distinct()


def readable_targets(kind, request):
    target = target_registry().get(kind)
    if target is None:
        raise ValidationError({"kind": "Type de rattachement non autorisé."})
    module, name = target.view.split(".")
    native = getattr(import_module(f"apps.{module}.api"), name)()
    native.request = copy(request)
    native.request.method = "GET"
    native.action = "list"
    native.kwargs = {}
    native.format_kwarg = None
    native.check_permissions(native.request)
    queryset = scoped_targets(target, request.tenant).filter(pk__in=native.get_queryset().values("pk"))
    return target, queryset, native


def target_unit(kind, item):
    if kind == "course":
        return item.organisation_unit_id
    return apps.get_model("core.OrganizationAttachment").objects.filter(
        **{f"{kind}_id": item.pk}
    ).values_list("unit_id", flat=True).first()


def target_summary(kind, target, item):
    details = {}
    for field in target.details:
        value = item
        for segment in field.split("."):
            value = getattr(value, segment)
        details[field] = value
    return {
        "id": item.pk, "kind": kind, "category": target.category, "label": str(item),
        "unit": target_unit(kind, item),
        "details": details,
    }


def target_detail(kind, target, item, request):
    result = target_summary(kind, target, item)
    result["relations"] = []
    result["relation_pages"] = []
    for related_kind, path in target.relations:
        related = item
        for segment in path.split("."):
            related = getattr(related, segment, None)
            if related is None:
                break
        if related is None:
            continue
        ids = related.values_list("pk", flat=True) if hasattr(related, "all") else [related.pk]
        related_target, visible, _native = readable_targets(related_kind, request)
        paginator = SISPagination()
        page = paginator.paginate_queryset(visible.filter(pk__in=ids).order_by("pk"), request)
        result["relations"].extend(
            target_summary(related_kind, related_target, value)
            for value in page
        )
        result["relation_pages"].append({
            "kind": related_kind, "count": paginator.page.paginator.count,
            "next": paginator.get_next_link(), "previous": paginator.get_previous_link(),
        })
    return result


def validate_attachment_model(item):
    targets = target_registry()
    selected = [kind for kind, target in targets.items() if not target.direct and getattr(item, f"{kind}_id")]
    if len(selected) != 1:
        raise ModelValidationError("Un rattachement doit désigner exactement un objet existant.")
    tenant = item.unit.etablissement
    if item.created_by.etablissement_id != tenant.pk or not configuration_admin(item.created_by):
        raise ModelValidationError("L’auteur doit être un administrateur actif de cet établissement.")
    kind = selected[0]
    if not scoped_targets(targets[kind], tenant).filter(pk=getattr(item, f"{kind}_id")).exists():
        raise ModelValidationError("Cet objet n’appartient pas à cet établissement.")
    if item.pk:
        previous = type(item).objects.get(pk=item.pk)
        if previous.unit_id != item.unit_id or previous.created_by_id != item.created_by_id or any(
            getattr(previous, f"{key}_id") != getattr(item, f"{key}_id")
            for key, target in targets.items() if not target.direct
        ):
            raise ModelValidationError("Un rattachement existant est figé pour conserver l’historique.")
