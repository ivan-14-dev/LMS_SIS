"""API views for portail parent (SIS Secondaire) - Agrégation."""

from apps.eleves.models import EleveTuteur
from apps.emplois_du_temps.models import Creneau
from apps.notes.api import visible_bulletins
from apps.notes.models import Note
from apps.paiements.api import visible_invoices
from apps.presences.models import Presence
from django.db.models import Q
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from sis_common.authorization import filter_queryset_by_scopes, is_current_tenant_user

UNPAID_STATUSES = ("emise", "partielle", "en_retard")


def _decimal_to_float(value):
    return float(value) if value is not None else None


class IsParent(IsAuthenticated):
    """Permission: uniquement pour les parents."""

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        return (
            request.user.role == "parent"
            and is_current_tenant_user(request)
            and hasattr(request.user, "tuteur_profile")
            and request.user.tuteur_profile.etablissement_id == request.tenant.pk
        )


class PortailParentViewSet(viewsets.ViewSet):
    """ViewSet d'agrégation pour le portail parent."""

    permission_classes = [IsParent]

    def _authorized_links(self, request):
        tenant_id = request.tenant.pk
        links = (
            EleveTuteur.objects.filter(
                tuteur_id=request.user.tuteur_profile.pk,
                tuteur__etablissement_id=tenant_id,
                autorise_acces_portail=True,
                eleve__etablissement_id=tenant_id,
                eleve__user__etablissement_id=tenant_id,
            )
            .filter(Q(eleve__classe_actuelle__isnull=True) | Q(eleve__classe_actuelle__etablissement_id=tenant_id))
            .select_related("eleve__user", "eleve__classe_actuelle__niveau")
        )
        return filter_queryset_by_scopes(
            links,
            request.user,
            "eleves.view_eleve",
            {"eleves": "eleve_id", "classes": "eleve__classe_actuelle_id"},
        )

    def _get_enfants(self, request):
        return [link.eleve for link in self._authorized_links(request)]

    def _presences(self, request, enfant):
        return filter_queryset_by_scopes(
            Presence.objects.filter(
                eleve=enfant,
                appel__creneau__classe__etablissement=request.tenant,
                appel__creneau__matiere__etablissement=request.tenant,
            ),
            request.user,
            "presences.view_presence",
            {
                "eleves": "eleve_id",
                "classes": "appel__creneau__classe_id",
                "matieres": "appel__creneau__matiere_id",
                "annees": "appel__creneau__classe__annee_scolaire_id",
            },
        )

    def _get_enfant(self, request):
        enfant_id = request.query_params.get("enfant_id")
        if not enfant_id:
            return None, Response({"error": "enfant_id requis."}, status=400)
        enfant_id = serializers.IntegerField(min_value=1).run_validation(enfant_id)
        link = self._authorized_links(request).filter(eleve_id=enfant_id).first()
        if not link:
            return None, Response({"error": "Élève non trouvé ou non autorisé."}, status=404)
        return link.eleve, None

    @action(detail=False, methods=["get"])
    def tableau_bord(self, request):
        """Tableau de bord du parent."""
        enfants = self._get_enfants(request)
        enfant_ids = [enfant.id for enfant in enfants]
        latest_bulletins = {}
        for bulletin in (
            visible_bulletins(request)
            .filter(eleve_id__in=enfant_ids)
            .select_related("periode")
            .order_by("eleve_id", "-periode__date_fin")
        ):
            latest_bulletins.setdefault(bulletin.eleve_id, bulletin)

        enfants_data = []
        for enfant in enfants:
            presences = self._presences(request, enfant)
            absences = presences.filter(statut__in=("absent", "absent_justifie")).count()
            retards = presences.filter(statut="retard").count()
            bulletin = latest_bulletins.get(enfant.id)
            enfants_data.append(
                {
                    "id": enfant.id,
                    "matricule": enfant.matricule,
                    "nom": enfant.user.get_full_name(),
                    "classe": enfant.classe_actuelle.nom if enfant.classe_actuelle else None,
                    "niveau": (
                        enfant.classe_actuelle.niveau.libelle
                        if enfant.classe_actuelle and enfant.classe_actuelle.niveau
                        else None
                    ),
                    "moyenne": _decimal_to_float(bulletin.moyenne_generale if bulletin else None),
                    "rang": bulletin.rang if bulletin else None,
                    "absences": absences,
                    "retards": retards,
                }
            )

        factures = (
            visible_invoices(request)
            .filter(eleve_id__in=enfant_ids, statut__in=UNPAID_STATUSES)
            .select_related("eleve__user")
            .order_by("date_echeance", "-date_emission")[:5]
        )

        return Response(
            {
                "enfants": enfants_data,
                "factures_impayees": [
                    {
                        "id": facture.id,
                        "numero": facture.numero,
                        "eleve": facture.eleve.user.get_full_name(),
                        "montant": _decimal_to_float(facture.montant),
                        "reste_a_payer": _decimal_to_float(facture.montant_restant),
                        "echeance": (facture.date_echeance.isoformat() if facture.date_echeance else None),
                        "statut": facture.statut,
                    }
                    for facture in factures
                ],
            },
            headers={"Cache-Control": "private, no-store"},
        )

    @action(detail=False, methods=["get"])
    def enfant_detail(self, request):
        """Détails d'un enfant."""
        enfant, error = self._get_enfant(request)
        if error:
            return error

        latest_bulletin = (
            visible_bulletins(request)
            .filter(eleve=enfant)
            .select_related("periode")
            .order_by("-periode__date_fin")
            .first()
        )
        return Response(
            {
                "id": enfant.id,
                "matricule": enfant.matricule,
                "nom": enfant.user.get_full_name(),
                "classe": enfant.classe_actuelle.nom if enfant.classe_actuelle else None,
                "niveau": (
                    enfant.classe_actuelle.niveau.libelle
                    if enfant.classe_actuelle and enfant.classe_actuelle.niveau
                    else None
                ),
                "statut": enfant.statut,
                "moyenne": _decimal_to_float(latest_bulletin.moyenne_generale if latest_bulletin else None),
                "rang": latest_bulletin.rang if latest_bulletin else None,
            }
        )

    @action(detail=False, methods=["get"])
    def notes_enfant(self, request):
        """Notes d'un enfant."""
        enfant, error = self._get_enfant(request)
        if error:
            return error

        notes = Note.objects.filter(
            eleve=enfant,
            evaluation__classe__etablissement=request.tenant,
            evaluation__matiere__etablissement=request.tenant,
            evaluation__periode__annee_scolaire__etablissement=request.tenant,
        ).select_related("evaluation__matiere", "evaluation__periode")
        notes = filter_queryset_by_scopes(
            notes,
            request.user,
            "notes.view_note",
            {
                "classes": "evaluation__classe_id",
                "matieres": "evaluation__matiere_id",
                "periodes": "evaluation__periode_id",
                "annees": "evaluation__classe__annee_scolaire_id",
            },
        )

        return Response(
            [
                {
                    "id": note.id,
                    "matiere": note.evaluation.matiere.nom,
                    "evaluation": note.evaluation.titre,
                    "note": _decimal_to_float(note.valeur),
                    "type": note.evaluation.type,
                    "statut": note.statut,
                    "date": note.evaluation.date.isoformat(),
                }
                for note in notes.order_by("-evaluation__date", "-date_saisie")[:50]
            ]
        )

    @action(detail=False, methods=["get"])
    def absences_enfant(self, request):
        """Absences d'un enfant."""
        enfant, error = self._get_enfant(request)
        if error:
            return error

        presences = (
            self._presences(request, enfant)
            .filter(statut__in=("absent", "absent_justifie", "retard"))
            .select_related("appel__creneau", "justificatif")
            .order_by("-appel__date", "-appel__creneau__heure_debut")[:30]
        )

        return Response(
            [
                {
                    "date": presence.appel.date.isoformat(),
                    "statut": presence.statut,
                    "retard_minutes": presence.retard_minutes,
                    "commentaire": presence.commentaire,
                    "justificatif": (
                        {
                            "statut": presence.justificatif.statut,
                            "motif": presence.justificatif.motif,
                        }
                        if hasattr(presence, "justificatif")
                        else None
                    ),
                }
                for presence in presences
            ]
        )

    @action(detail=False, methods=["get"])
    def emploi_du_temps_enfant(self, request):
        """Emploi du temps d'un enfant."""
        enfant, error = self._get_enfant(request)
        if error:
            return error
        if not enfant.classe_actuelle:
            return Response({"error": "Élève sans classe."}, status=400)

        creneaux = (
            Creneau.objects.filter(
                classe=enfant.classe_actuelle,
                actif=True,
                classe__etablissement=request.tenant,
                matiere__etablissement=request.tenant,
                enseignant__user__etablissement=request.tenant,
            )
            .select_related("matiere", "enseignant__user", "salle")
            .order_by("jour", "heure_debut")
        )
        creneaux = filter_queryset_by_scopes(
            creneaux,
            request.user,
            "emplois_du_temps.view_creneau",
            {
                "classes": "classe_id",
                "matieres": "matiere_id",
                "enseignants": "enseignant_id",
                "annees": "classe__annee_scolaire_id",
            },
        )

        return Response(
            [
                {
                    "id": creneau.id,
                    "jour": creneau.jour,
                    "heure_debut": str(creneau.heure_debut),
                    "heure_fin": str(creneau.heure_fin),
                    "matiere": creneau.matiere.nom,
                    "enseignant": creneau.enseignant.user.get_full_name(),
                    "salle": creneau.salle.nom if creneau.salle else None,
                    "type": creneau.type,
                }
                for creneau in creneaux
            ]
        )

    @action(detail=False, methods=["get"])
    def dossier_enfant(self, request):
        """Expose existing child reads and published documents without a directory grant."""
        enfant, error = self._get_enfant(request)
        if error:
            return error
        bulletins = visible_bulletins(request).filter(eleve=enfant).order_by("-periode__date_fin", "-pk")
        factures = visible_invoices(request).filter(eleve=enfant).order_by("-date_emission", "-pk")
        return Response(
            {
                "enfant": self.enfant_detail(request).data,
                "notes": self.notes_enfant(request).data,
                "absences": self.absences_enfant(request).data,
                "planning": self.emploi_du_temps_enfant(request).data if enfant.classe_actuelle_id else [],
                "bulletins": [
                    {
                        "id": bulletin.pk,
                        "periode": bulletin.periode.libelle,
                        "classe": bulletin.classe.nom,
                        "moyenne": _decimal_to_float(bulletin.moyenne_generale),
                        "rang": bulletin.rang,
                    }
                    for bulletin in bulletins
                ],
                "factures": [
                    {
                        "id": facture.pk,
                        "numero": facture.numero,
                        "statut": facture.statut,
                        "montant": str(facture.montant),
                        "montant_paye": str(facture.montant_paye),
                        "reste_a_payer": str(facture.montant_restant),
                        "paiements": [
                            {
                                "numero": paiement.numero,
                                "date": paiement.date_paiement.isoformat(),
                                "montant": str(paiement.montant),
                                "statut": paiement.statut,
                            }
                            for paiement in facture.paiements.all()
                        ],
                    }
                    for facture in factures
                ],
            },
            headers={"Cache-Control": "private, no-store"},
        )
