"""API views for portail scolarité (SIS Supérieur) - Agrégation."""

from apps.etudiants.models import Etudiant, InscriptionAdministrative
from apps.formations.models import Formation
from apps.paiements.models import FactureFrais as Facture
from django.db.models import Count, Q, Sum
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from sis_common.authorization import filter_queryset_by_scopes, request_has_business_access


class IsScolarite(IsAuthenticated):
    """Permission: personnel scolarité."""

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        return request_has_business_access(
            request,
            "etudiants.view_etudiant",
            ("scolarite", "directeur_etudes", "chef_departement", "doyen"),
            tenant_group_codes=(
                "academic_admin_superieur",
                "student_manager_superieur",
                "registration_manager_superieur",
                "finance_manager_superieur",
            ),
        )


class PortailScolariteViewSet(viewsets.ViewSet):
    """ViewSet d'agrégation pour la scolarité."""

    permission_classes = [IsScolarite]

    UNPAID_STATUSES = ("emise", "partielle", "en_retard")
    ACTIVE_STUDENT_STATUSES = ("pre_inscrit", "inscrit", "redoublant")

    def _etudiants_queryset(self):
        return filter_queryset_by_scopes(
            Etudiant.objects.all(),
            self.request.user,
            "etudiants.view_etudiant",
            {
                "formations": "inscriptions_admin__formation_id",
                "facultes": "inscriptions_admin__formation__departement__faculte_id",
                "departements": "inscriptions_admin__formation__departement_id",
                "annees": "annee_universitaire_actuelle_id",
            },
        )

    def _inscriptions_queryset(self):
        return filter_queryset_by_scopes(
            InscriptionAdministrative.objects.all(),
            self.request.user,
            "etudiants.view_etudiant",
            {
                "formations": "formation_id",
                "facultes": "formation__departement__faculte_id",
                "departements": "formation__departement_id",
                "annees": "annee_universitaire_id",
            },
        )

    def _formations_queryset(self):
        return filter_queryset_by_scopes(
            Formation.objects.all(),
            self.request.user,
            "formations.view_formation",
            {
                "formations": "id",
                "facultes": "departement__faculte_id",
                "departements": "departement_id",
            },
        )

    def _factures_queryset(self):
        return filter_queryset_by_scopes(
            Facture.objects.all(),
            self.request.user,
            "paiements.view_facturefrais",
            {
                "formations": "etudiant__inscriptions_admin__formation_id",
                "facultes": "etudiant__inscriptions_admin__formation__departement__faculte_id",
                "departements": "etudiant__inscriptions_admin__formation__departement_id",
                "annees": "type_frais__annee_universitaire_id",
            },
        )

    @action(detail=False, methods=["get"])
    def tableau_bord(self, request):
        """Tableau de bord de la scolarité."""
        timezone.now().date()

        etudiants = self._etudiants_queryset()
        inscriptions = self._inscriptions_queryset()
        factures = self._factures_queryset()
        stats = {
            "total_etudiants": etudiants.filter(
                statut__in=self.ACTIVE_STUDENT_STATUSES
            )
            .values("id")
            .distinct()
            .count(),
            "inscriptions_annee": inscriptions.filter(annee_universitaire__en_cours=True).count(),
            "factures_impayees": factures.filter(statut__in=self.UNPAID_STATUSES).count(),
            "montant_impaye": float(
                factures.filter(statut__in=self.UNPAID_STATUSES).aggregate(total=Sum("montant"))["total"]
                or 0
            ),
        }

        inscriptions = self._inscriptions_queryset().select_related(
            "etudiant__user", "formation"
        ).order_by("-created_at")[:10]

        inscriptions_recentes = [
            {
                "id": i.id,
                "etudiant": i.etudiant.user.get_full_name(),
                "matricule": i.etudiant.matricule,
                "formation": i.formation.nom,
                "date": i.created_at.isoformat(),
                "statut": i.statut,
            }
            for i in inscriptions
        ]

        return Response(
            {
                "statistiques": stats,
                "inscriptions_recentes": inscriptions_recentes,
            }
        )

    @action(detail=False, methods=["get"])
    def statistiques_formations(self, request):
        """Statistiques par formation."""
        formations = self._formations_queryset().annotate(
            nb_inscrits=Count(
                "inscriptions_admin",
                filter=Q(inscriptions_admin__statut="validee"),
                distinct=True,
            ),
        ).values("id", "nom", "nb_inscrits")

        return Response(list(formations))

    @action(detail=False, methods=["get"])
    def etudiants_recherche(self, request):
        """Recherche d'étudiants."""
        q = request.query_params.get("q", "")
        if len(q) < 2:
            return Response(
                {"error": "Recherche trop courte (min 2 caractères)."}, status=400
            )

        etudiants = self._etudiants_queryset().filter(
            Q(matricule__icontains=q)
            | Q(user__first_name__icontains=q)
            | Q(user__last_name__icontains=q)
            | Q(user__email__icontains=q)
        ).select_related("user")[:20]

        return Response(
            [
                {
                    "id": e.id,
                    "matricule": e.matricule,
                    "nom": e.user.get_full_name(),
                    "email": e.user.email,
                    "statut": e.statut,
                }
                for e in etudiants
            ]
        )

    @action(detail=False, methods=["get"])
    def dossier_etudiant(self, request):
        """Dossier complet d'un étudiant."""
        etudiant_id = request.query_params.get("etudiant_id")
        if not etudiant_id:
            return Response({"error": "etudiant_id requis."}, status=400)

        try:
            etudiant = self._etudiants_queryset().select_related("user").get(id=etudiant_id)
        except Etudiant.DoesNotExist:
            return Response({"error": "Étudiant non trouvé."}, status=404)

        # Inscriptions
        inscriptions = [
            {
                "id": i.id,
                "formation": i.formation.nom,
                "annee": str(i.annee_universitaire),
                "statut": i.statut,
                "annee_en_cours": i.annee_universitaire.en_cours,
            }
            for i in etudiant.inscriptions_admin.select_related(
                "formation", "annee_universitaire"
            )
        ]

        # Factures
        factures = [
            {
                "id": f.id,
                "numero": f.numero,
                "montant": float(f.montant),
                "statut": f.statut,
            }
            for f in self._factures_queryset().filter(etudiant=etudiant)[:10]
        ]

        return Response(
            {
                "etudiant": {
                    "id": etudiant.id,
                    "matricule": etudiant.matricule,
                    "nom": etudiant.user.get_full_name(),
                    "email": etudiant.user.email,
                    "statut": etudiant.statut,
                },
                "inscriptions": inscriptions,
                "factures": factures,
            }
        )

    @action(detail=False, methods=["get"])
    def alertes(self, request):
        """Alertes et notifications."""
        alertes = []

        # Factures en retard
        factures_retard = self._factures_queryset().filter(
            statut__in=self.UNPAID_STATUSES, date_echeance__lt=timezone.now().date()
        ).count()
        if factures_retard > 0:
            alertes.append(
                {
                    "type": "factures_retard",
                    "message": f"{factures_retard} facture(s) en retard de paiement",
                    "niveau": "warning",
                }
            )

        return Response(alertes)
