"""API views for portail doyen (SIS Supérieur) - Agrégation."""

from apps.enseignants.models import AffectationEnseignement, EnseignantChercheur
from apps.etudiants.models import InscriptionAdministrative
from apps.formations.models import Formation
from apps.recherche.models import Laboratoire, These
from apps.structure.models import Departement, Faculte
from django.db.models import Count, Q
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from sis_common.authorization import filter_queryset_by_scopes, request_has_business_access


class IsDoyen(IsAuthenticated):
    """Permission: uniquement pour les doyens/direction."""

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        return request_has_business_access(
            request,
            "formations.view_formation",
            ("doyen", "vice_doyen", "president", "vice_president"),
            tenant_group_codes=("academic_admin_superieur", "student_manager_superieur", "research_manager_superieur"),
        )


class PortailDoyenViewSet(viewsets.ViewSet):
    """ViewSet d'agrégation pour le portail doyen."""

    permission_classes = [IsDoyen]
    UNPAID_STATUSES = ("emise", "partielle", "en_retard")

    def _parse_faculte_id(self):
        value = self.request.query_params.get("faculte_id")
        if value in (None, ""):
            return None, None
        try:
            return int(value), None
        except (TypeError, ValueError):
            return None, Response({"error": "faculte_id invalide."}, status=400)

    def _formations_queryset(self):
        return filter_queryset_by_scopes(
            Formation.objects.all(),
            self.request.user,
            "formations.view_formation",
            {
                "facultes": "departement__faculte_id",
                "departements": "departement_id",
                "formations": "id",
            },
        )

    def _departements_queryset(self):
        return filter_queryset_by_scopes(
            Departement.objects.all(),
            self.request.user,
            "formations.view_formation",
            {
                "facultes": "faculte_id",
                "departements": "id",
            },
        )

    def _inscriptions_queryset(self):
        return filter_queryset_by_scopes(
            InscriptionAdministrative.objects.all(),
            self.request.user,
            "etudiants.view_etudiant",
            {
                "facultes": "formation__departement__faculte_id",
                "departements": "formation__departement_id",
                "formations": "formation_id",
                "annees": "annee_universitaire_id",
            },
        )

    def _enseignants_queryset(self):
        return filter_queryset_by_scopes(
            EnseignantChercheur.objects.all(),
            self.request.user,
            "utilisateurs.view_utilisateur",
            {
                "facultes": "affectations__ecue__ue__formation__departement__faculte_id",
                "departements": "affectations__ecue__ue__formation__departement_id",
            },
        )

    def _laboratoires_queryset(self):
        return filter_queryset_by_scopes(
            Laboratoire.objects.all(),
            self.request.user,
            "recherche.view_laboratoire",
            {
                "facultes": "faculte_id",
            },
        )

    def _theses_queryset(self):
        return filter_queryset_by_scopes(
            These.objects.all(),
            self.request.user,
            "recherche.view_these",
            {
                "facultes": "laboratoire__faculte_id",
            },
        )

    @action(detail=False, methods=["get"])
    def tableau_bord(self, request):
        """Tableau de bord du doyen."""
        faculte_id, error = self._parse_faculte_id()
        if error:
            return error

        formations = self._formations_queryset()
        departements = self._departements_queryset()
        inscriptions = self._inscriptions_queryset()
        enseignants = self._enseignants_queryset()
        laboratoires = self._laboratoires_queryset()
        theses = self._theses_queryset()
        if faculte_id:
            try:
                faculte = Faculte.objects.get(id=faculte_id)
            except Faculte.DoesNotExist:
                return Response({"error": "Faculté non trouvée."}, status=404)
            formations = formations.filter(departement__faculte=faculte)
            departements = departements.filter(faculte=faculte)
            inscriptions = inscriptions.filter(formation__departement__faculte=faculte)
            enseignants = enseignants.filter(
                Q(affectations__ecue__ue__formation__departement__faculte=faculte)
                | Q(affectations__ue__formation__departement__faculte=faculte)
                | Q(laboratoire__faculte=faculte)
            ).distinct()
            laboratoires = laboratoires.filter(faculte=faculte)
        elif not formations.exists() and not departements.exists():
            faculte = None
        else:
            faculte = None

        stats = {
            "nb_formations": formations.count(),
            "nb_departements": departements.count(),
            "nb_etudiants": inscriptions.filter(
                formation__in=formations, statut="validee"
            ).values("etudiant_id").distinct().count(),
            "nb_enseignants": enseignants.distinct().count(),
            "nb_laboratoires": laboratoires.count(),
            "nb_theses_en_cours": theses.filter(statut="en_cours").count(),
        }

        # Départements
        deps = [
            {
                "id": d.id,
                "nom": d.nom,
                "directeur": d.directeur.get_full_name() if d.directeur else None,
                "nb_formations": d.formations.count(),
                "nb_enseignants": AffectationEnseignement.objects.filter(
                    Q(ecue__ue__formation__departement=d) | Q(ue__formation__departement=d)
                )
                .values("enseignant_id")
                .distinct()
                .count(),
            }
            for d in departements[:10]
        ]

        return Response(
            {
                "faculte": (
                    {"id": faculte.id, "nom": faculte.nom} if faculte_id else None
                ),
                "statistiques": stats,
                "departements": deps,
            }
        )

    @action(detail=False, methods=["get"])
    def statistiques_formations(self, request):
        """Statistiques détaillées par formation."""
        faculte_id, error = self._parse_faculte_id()
        if error:
            return error

        formations = self._formations_queryset().annotate(
            nb_inscrits=Count(
                "inscriptions_admin",
                filter=Q(inscriptions_admin__statut="validee"),
                distinct=True,
            ),
        )
        if faculte_id:
            formations = formations.filter(departement__faculte_id=faculte_id)

        return Response(
            [
                {
                    "id": f.id,
                    "nom": f.nom,
                    "departement": f.departement.nom if f.departement else None,
                    "nb_inscrits": f.nb_inscrits,
                    "niveau": f.niveau,
                }
                for f in formations
            ]
        )

    @action(detail=False, methods=["get"])
    def recherche(self, request):
        """Statistiques recherche."""
        faculte_id, error = self._parse_faculte_id()
        if error:
            return error

        labos = self._laboratoires_queryset()
        theses = self._theses_queryset()
        if faculte_id:
            labos = labos.filter(faculte_id=faculte_id)
            theses = theses.filter(laboratoire__faculte_id=faculte_id)

        return Response(
            {
                "nb_laboratoires": labos.count(),
                "nb_theses_en_cours": theses.filter(statut="en_cours").count(),
                "nb_theses_soutenues": theses.filter(statut="soutenue").count(),
                "laboratoires": [
                    {
                        "id": labo.id,
                        "nom": labo.nom,
                        "acronyme": labo.acronyme,
                        "directeur": (
                            labo.directeur.user.get_full_name() if labo.directeur else None
                        ),
                    }
                    for labo in labos[:10]
                ],
            }
        )

    @action(detail=False, methods=["get"])
    def budget(self, request):
        """Informations budgétaires."""
        from apps.paiements.models import FactureFrais as Facture
        from django.db.models import Sum

        factures = filter_queryset_by_scopes(
            Facture.objects.filter(type_frais__annee_universitaire__en_cours=True),
            request.user,
            "paiements.view_facturefrais",
            {
                "facultes": "etudiant__inscriptions_admin__formation__departement__faculte_id",
                "departements": "etudiant__inscriptions_admin__formation__departement_id",
                "formations": "etudiant__inscriptions_admin__formation_id",
                "annees": "type_frais__annee_universitaire_id",
            },
        )

        return Response(
            {
                "total_facture": float(
                    factures.aggregate(t=Sum("montant"))["t"] or 0
                ),
                "total_paye": float(
                    factures.filter(statut="payee").aggregate(t=Sum("montant"))[
                        "t"
                    ]
                    or 0
                ),
                "total_impaye": float(
                    factures.filter(statut__in=self.UNPAID_STATUSES).aggregate(t=Sum("montant"))[
                        "t"
                    ]
                    or 0
                ),
            }
        )
