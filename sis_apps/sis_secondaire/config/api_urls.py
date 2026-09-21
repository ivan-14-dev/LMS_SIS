"""API URLs pour SIS Secondaire."""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

router = DefaultRouter()

urlpatterns = [
    path("etablissement/", include("apps.etablissement.urls_api")),
    path("utilisateurs/", include("apps.utilisateurs.urls_api")),
    path("classes/", include("apps.classes.urls_api")),
    path("enseignants/", include("apps.enseignants.urls_api")),
    path("eleves/", include("apps.eleves.urls_api")),
    path("salles/", include("apps.salles.urls_api")),
    path("edt/", include("apps.emplois_du_temps.urls_api")),
    path("presences/", include("apps.presences.urls_api")),
    path("evaluations/", include("apps.evaluations.urls_api")),
    path("notes/", include("apps.notes.urls_api")),
    path("bulletins/", include("apps.bulletins.urls_api")),
    path("examens/", include("apps.examens.urls_api")),
    path("conseils/", include("apps.conseil_classe.urls_api")),
    path("discipline/", include("apps.discipline.urls_api")),
    path("paiements/", include("apps.paiements.urls_api")),
    path("cantine/", include("apps.cantine.urls_api")),
    path("transport/", include("apps.transport.urls_api")),
    path("internat/", include("apps.internat.urls_api")),
    path("bibliotheque/", include("apps.bibliotheque.urls_api")),
    path("infirmerie/", include("apps.infirmerie.urls_api")),
    path("clubs/", include("apps.clubs.urls_api")),
    path("stages/", include("apps.stages.urls_api")),
    path("portail/eleve/", include("apps.portail_eleve.urls_api")),
    path("portail/parent/", include("apps.portail_parent.urls_api")),
    path("portail/enseignant/", include("apps.portail_enseignant.urls_api")),
    path("integration/", include("apps.integration.urls_api")),
    path("", include(router.urls)),
]
