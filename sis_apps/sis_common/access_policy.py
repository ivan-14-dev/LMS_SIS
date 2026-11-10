"""Individual exceptions and explicit, request-local role contexts."""

from django.db.models import Q
from django.utils.functional import SimpleLazyObject
from rest_framework.exceptions import PermissionDenied

FEATURES = {
    "learner_portal": {
        "label": "Dossier et résultats apprenant / famille",
        "api": ("portail/apprenant/", "portail-eleve/", "portail-etudiant/", "portail-parent/"),
        "ui": ("portail-apprenant",),
    },
    "staff_portal": {
        "label": "Portail pédagogique du personnel",
        "api": ("portail/staff/", "portail-enseignant/", "portail-doyen/", "portail-scolarite/"),
        "ui": ("portail-staff",),
    },
    "timetable": {
        "label": "Emplois du temps",
        "api": ("edt/", "portail/apprenant/emploi_du_temps/"),
        "ui": ("emploi-du-temps", "mon-emploi-du-temps"),
    },
    "lms": {
        "label": "Cours LMS associés par le SIS",
        "api": ("integration/my-learning/",),
        "ui": ("cours-lms",),
    },
    "studio": {
        "label": "Droits Studio attribués par le SIS",
        "api": (),
        "ui": (),
    },
    "library": {
        "label": "Bibliothèque",
        "api": ("bibliotheque/",),
        "ui": ("bibliotheque",),
    },
    "payments": {
        "label": "Finances et paiements",
        "api": ("paiements/",),
        "ui": ("paiements",),
    },
}


def policy_for(user):
    attributes = getattr(user, "attributs_acces", None)
    if attributes is None:
        return {}
    if not isinstance(attributes, dict):
        raise PermissionDenied("La configuration des accès du compte est invalide.")
    policy = attributes.get("access_policy", {})
    if not isinstance(policy, dict) or any(
        not isinstance(policy.get(key, []), list) or any(not isinstance(item, str) for item in policy[key])
        for key in ("additional_roles", "denied_permissions", "disabled_features")
        if key in policy
    ):
        raise PermissionDenied("La configuration des accès individuels est invalide.")
    return policy


def assigned_roles(user):
    primary = getattr(user, "primary_role", getattr(user, "role", ""))
    additional = policy_for(user).get("additional_roles", [])
    return list(dict.fromkeys([primary, *additional]))


def assigned_role_filter(*roles, prefix=""):
    condition = Q(**{f"{prefix}role__in": roles})
    for role in roles:
        condition |= Q(**{f"{prefix}attributs_acces__access_policy__additional_roles__contains": [role]})
    return condition


def permission_is_denied(user, permission):
    if user.is_superuser:
        return False
    namespace = permission.split(".", 1)[0]
    feature = {"bibliotheque": "library", "paiements": "payments", "emplois_du_temps": "timetable"}.get(namespace)
    return permission in policy_for(user).get("denied_permissions", []) or bool(
        feature and feature_is_denied(user, feature)
    )


def feature_is_denied(user, feature):
    if user.is_superuser:
        return False
    policy = policy_for(user)
    if feature in policy.get("disabled_features", []):
        return True
    aggregate_permissions = {
        "learner_portal": {
            "notes.view_note",
            "notes.view_bulletin",
            "releves.view_relevenotes",
            "eleves.view_eleve",
            "etudiants.view_etudiant",
        },
        "timetable": {"emplois_du_temps.view_creneau", "emplois_du_temps.view_creneaucours"},
    }
    return bool(aggregate_permissions.get(feature, set()) & set(policy.get("denied_permissions", [])))


def public_policy(user):
    roles = dict(getattr(user, "ROLE_CHOICES", ()))
    return {
        "primary_role": getattr(user, "primary_role", user.role),
        "roles": [{"code": role, "label": roles.get(role, role)} for role in assigned_roles(user)],
        "disabled_features": [feature for feature in FEATURES if feature_is_denied(user, feature)],
        "denied_permissions": [] if user.is_superuser else policy_for(user).get("denied_permissions", []),
        "disabled_paths": [
            path for code, feature in FEATURES.items() if feature_is_denied(user, code) for path in feature["ui"]
        ],
    }


class RoleContextUser(SimpleLazyObject):
    """Keep ORM identity and writes on the real user; never persist the active role."""

    def __init__(self, user, role):
        super().__init__(lambda: user)
        self._setup()
        self.__dict__["_selected_role"] = role

    @property
    def primary_role(self):
        return self._wrapped.role

    @property
    def role(self):
        return self.__dict__["_selected_role"]

    def get_role_display(self):
        return dict(self.ROLE_CHOICES).get(self.role, self.role)

    @property
    def is_eleve(self):
        return self.role == "eleve"

    @property
    def is_etudiant(self):
        return self.role in ("etudiant", "doctorant")

    @property
    def is_parent(self):
        return self.role == "parent"

    @property
    def is_enseignant(self):
        return self.role in ("enseignant", "chercheur")

    @property
    def is_admin(self):
        return self.role in ("president", "vice_president", "doyen", "directeur_dept", "scolarite")


def contextual_user(user, request):
    if request.path.startswith("/api/v1/auth/"):
        return user
    selected = request.headers.get("X-SIS-Role")
    if selected:
        if selected not in assigned_roles(user):
            raise PermissionDenied("Ce rôle ne vous est pas attribué. Revenez au rôle principal.")
        if selected != user.role:
            user = RoleContextUser(user, selected)
    if policy_for(user):
        enforce_request_policy(user, request)
    return user


def enforce_request_policy(user, request):
    if user.is_superuser:
        return
    path = request.path.removeprefix("/api/v1/")
    for code, feature in FEATURES.items():
        if feature_is_denied(user, code) and any(path.startswith(prefix) for prefix in feature["api"]):
            raise PermissionDenied(f"Accès retiré pour ce compte : {feature['label']}.")

    denied = policy_for(user).get("denied_permissions", [])
    if not denied or path.startswith(("auth/", "utilisateurs/comptes/me/", "utilisateurs/comptes/capabilities/")):
        return
    view = request.parser_context.get("view")
    if view is None:
        return
    if path.startswith("utilisateurs/comptes/") and getattr(view, "action", None) in (
        "update_profile",
        "change_password",
        "revoke_sessions",
        "sessions",
        "revoke_session",
        "mfa_enroll",
        "mfa_activate",
        "mfa_disable",
        "workspace_link",
    ):
        return
    model = getattr(getattr(view, "queryset", None), "model", None)
    serializer = getattr(view, "serializer_class", None)
    if model is None and serializer is None and hasattr(view, "get_serializer_class"):
        from rest_framework.generics import GenericAPIView

        if type(view).get_serializer_class is not GenericAPIView.get_serializer_class:
            request.user = user
            serializer = view.get_serializer_class()
    if model is None and serializer is not None:
        model = getattr(getattr(serializer, "Meta", None), "model", None)
    if model is not None:
        operation = {"GET": "view", "HEAD": "view", "OPTIONS": "view", "DELETE": "delete"}.get(request.method, "change")
        if request.method == "POST" and getattr(view, "action", None) == "create":
            operation = "add"
        permission = f"{model._meta.app_label}.{operation}_{model._meta.model_name}"
        if permission_is_denied(user, permission):
            raise PermissionDenied("Cette permission a été retirée individuellement pour votre compte.")
