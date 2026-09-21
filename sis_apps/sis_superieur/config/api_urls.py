"""API URLs pour SIS Supérieur."""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

router = DefaultRouter()

urlpatterns = [
    path("etablissement/", include("apps.etablissement.urls_api")),
    path("utilisateurs/", include("apps.utilisateurs.urls_api")),
    path("structure/", include("apps.structure.urls_api")),
    path("formations/", include("apps.formations.urls_api")),
    path("maquettes/", include("apps.maquettes.urls_api")),
    path("ue-ecue/", include("apps.ue_ecue.urls_api")),
    path("etudiants/", include("apps.etudiants.urls_api")),
    path("inscriptions/", include("apps.inscriptions.urls_api")),
    path("ects/", include("apps.ects.urls_api")),
    path("mobilite/", include("apps.mobilite.urls_api")),
    path("edt/", include("apps.emplois_du_temps.urls_api")),
    path("notes/", include("apps.notes.urls_api")),
    path("examens/", include("apps.examens.urls_api")),
    path("rattrapages/", include("apps.rattrapages.urls_api")),
    path("jurys/", include("apps.jurys.urls_api")),
    path("releves/", include("apps.releves.urls_api")),
    path("diplomes/", include("apps.diplomes.urls_api")),
    path("memoires/", include("apps.memoires.urls_api")),
    path("stages/", include("apps.stages.urls_api")),
    path("bourses/", include("apps.bourses.urls_api")),
    path("paiements/", include("apps.paiements.urls_api")),
    path("recherche/", include("apps.recherche.urls_api")),
    path("bibliotheque/", include("apps.bibliotheque.urls_api")),
    path("entreprises/", include("apps.entreprises.urls_api")),
    path("enseignants/", include("apps.enseignants.urls_api")),
    path("portail/etudiant/", include("apps.portail_etudiant.urls_api")),
    path("portail/enseignant/", include("apps.portail_enseignant.urls_api")),
    path("portail/doyen/", include("apps.portail_doyen.urls_api")),
    path("portail/scolarite/", include("apps.portail_scolarite.urls_api")),
    path("integration/", include("apps.integration.urls_api")),
    path("", include(router.urls)),
]
