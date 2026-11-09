"""Versioned contracts for modules shipped and reviewed with the SIS release."""

from dataclasses import asdict, dataclass

from django.apps import apps
from django.conf import settings
from rest_framework.exceptions import PermissionDenied, ValidationError


@dataclass(frozen=True)
class ModuleManifest:
    identifier: str
    label: str
    description: str
    required: bool
    dependencies: tuple[str, ...] = ()
    permissions: tuple[str, ...] = ()
    api: tuple[str, ...] = ()
    ui: tuple[str, ...] = ()
    events: tuple[str, ...] = ()
    version: str = "1.0.0"
    publisher: str = "LMS_SIS"
    contract_version: int = 1
    variants: tuple[str, ...] = ("secondaire", "superieur")
    execution: str = "builtin"
    default_enabled: bool = True
    data_retention: str = "preserve"


MODULES = {
    item.identifier: item
    for item in (
        ModuleManifest(
            "core.identity",
            "Identité et autorisations",
            "Comptes, authentification et contrôle des accès ; noyau obligatoire.",
            True,
        ),
        ModuleManifest(
            "core.notifications",
            "Historique et notifications",
            "Traçabilité et notifications persistantes, y compris les livraisons déjà engagées.",
            True,
            dependencies=("core.identity",),
        ),
        ModuleManifest(
            "sis.complaints",
            "Réclamations privées",
            "Dépôt, affectation, échanges et recours des apprenants.",
            False,
            dependencies=("core.identity", "core.notifications"),
            permissions=("core.affecter_reclamation", "core.traiter_reclamation"),
            api=("core/reclamations/",),
            ui=("reclamations",),
            events=("core.reclamation",),
        ),
        ModuleManifest(
            "sis.projects",
            "Projets pédagogiques",
            "Équipes, jalons, livrables privés et évaluations humaines distinctes des notes officielles.",
            False,
            dependencies=("core.identity", "core.notifications"),
            permissions=("core.gerer_projet_pedagogique", "core.evaluer_projet_pedagogique"),
            api=("core/projets/",),
            ui=("projets",),
            events=("core.pedagogicalproject",),
            default_enabled=False,
        ),
        ModuleManifest(
            "sis.events",
            "Agenda institutionnel",
            "Conférences, examens, réunions, cérémonies et activités privées sur invitation.",
            False,
            dependencies=("core.identity", "core.notifications"),
            permissions=("core.gerer_evenement_institutionnel", "core.consulter_evenement_institutionnel"),
            api=("core/evenements/",),
            ui=("evenements",),
            events=("core.institutionalevent",),
            default_enabled=False,
        ),
        ModuleManifest(
            "sis.practical_training",
            "Suivi pratique",
            "Heures réelles et compétences professionnelles sur convention complète et programme publié.",
            False,
            dependencies=("core.identity", "core.notifications"),
            permissions=(
                "stages.gerer_suivi_pratique",
                "stages.consulter_suivi_pratique",
                "stages.saisir_heures_pratiques",
                "stages.valider_heures_pratiques",
                "stages.evaluer_competences_pratiques",
            ),
            api=("stages/pratique/",),
            ui=("stages-pratiques",),
            events=("stages.programmepratique", "stages.dossierpratique"),
            default_enabled=False,
        ),
        ModuleManifest(
            "sis.research",
            "Recherche universitaire",
            "Laboratoires, projets, encadrements, publications privées et journal financier de recherche.",
            False,
            dependencies=("core.identity", "core.notifications"),
            permissions=(
                "recherche.gerer_recherche",
                "recherche.consulter_recherche",
                "recherche.contribuer_recherche",
                "recherche.comptabiliser_recherche",
            ),
            api=("recherche/",),
            ui=("recherche",),
            variants=("superieur",),
            default_enabled=False,
        ),
        ModuleManifest(
            "sis.surveys",
            "Enquêtes institutionnelles nominatives",
            "Destinataires authentifiés explicitement sélectionnés, réponse unique et résultats privés.",
            False,
            dependencies=("core.identity", "core.notifications"),
            permissions=("core.gerer_enquete_institutionnelle",),
            api=("core/enquetes/", "portail/enquetes/"),
            ui=("portail-enquetes",),
            events=("core.institutionalsurvey",),
            default_enabled=False,
        ),
        ModuleManifest(
            "sis.delegations",
            "Missions et accès délégués",
            "Consultation de dossiers par mission explicite, datée et révocable, sans changement de rôle.",
            False,
            dependencies=("core.identity", "core.notifications"),
            permissions=("core.manage_accessdelegation",),
            api=("core/delegations/",),
            ui=("missions",),
            events=("delegation_accordee", "delegation_revoquee"),
        ),
    )
}


def available_modules():
    return {
        identifier: item for identifier, item in MODULES.items() if settings.SIS_VARIANT in item.variants
    }


def effective_modules(overrides):
    """Only explicit JSON true enables a configured module, including dependencies."""
    modules = available_modules()
    configured = {
        identifier: overrides.get(identifier, item.default_enabled) is True for identifier, item in modules.items()
    }

    def active(identifier):
        return configured[identifier] and all(active(dependency) for dependency in modules[identifier].dependencies)

    return {identifier: active(identifier) for identifier in modules}


def validate_module_changes(current, changes):
    modules = available_modules()
    if not isinstance(changes, dict) or not changes:
        raise ValidationError({"enabled": "Indiquez les modules à modifier."})
    for identifier, enabled in changes.items():
        if identifier not in modules:
            raise ValidationError({"enabled": f"Module non installé : {identifier}."})
        if type(enabled) is not bool:
            raise ValidationError({"enabled": "L'activation d'un module doit être un booléen."})
    proposed = {**current, **changes}
    configured = {
        identifier: proposed.get(identifier, item.default_enabled) is True for identifier, item in modules.items()
    }
    for identifier, item in modules.items():
        if item.required and not configured[identifier]:
            raise ValidationError({"enabled": f"Le module {item.label} est obligatoire."})
        if configured[identifier] and any(not configured[dependency] for dependency in item.dependencies):
            raise ValidationError({"enabled": f"Les dépendances de {item.label} doivent être actives."})
    return proposed


def module_configuration(tenant):
    return apps.get_model("core.ModuleConfiguration").objects.filter(etablissement_id=tenant.pk).first()


def module_snapshot(tenant):
    configuration = module_configuration(tenant)
    overrides = configuration.enabled if configuration else {}
    enabled = effective_modules(overrides)
    return {
        "contract_version": 1,
        "revision": configuration.revision if configuration else 0,
        "enabled": enabled,
        "modules": [
            {
                **asdict(item),
                "enabled": enabled[identifier],
                "origin": "tenant" if identifier in overrides else "default",
            }
            for identifier, item in available_modules().items()
        ],
    }


def require_module(tenant, identifier):
    if identifier not in MODULES:
        raise ValueError(f"Unknown installed module: {identifier}")
    if identifier not in available_modules():
        raise PermissionDenied("Ce module n'est pas disponible pour ce SIS.", code="module_unavailable")
    configuration = module_configuration(tenant)
    if not effective_modules(configuration.enabled if configuration else {})[identifier]:
        raise PermissionDenied("Ce module est désactivé pour votre établissement.", code="module_disabled")
