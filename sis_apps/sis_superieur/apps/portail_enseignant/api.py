"""API views for portail enseignant (SIS Supérieur) - Agrégation."""

from apps.emplois_du_temps.models import CreneauCours
from apps.enseignants.models import AffectationEnseignement
from apps.etudiants.models import InscriptionPedagogique
from apps.notes.models import Evaluation
from django.db.models import Count, Q
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response


def _decimal_to_float(value):
    return float(value) if value is not None else None


def _parse_positive_int(value, field_name, *, minimum=1):
    if value in (None, ""):
        return None, None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None, Response({"error": f"{field_name} invalide."}, status=400)
    if parsed < minimum:
        return None, Response({"error": f"{field_name} invalide."}, status=400)
    return parsed, None


class IsEnseignant(IsAuthenticated):
    """Permission: uniquement pour les enseignants."""

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        return hasattr(request.user, "enseignant_profile")


class PortailEnseignantViewSet(viewsets.ViewSet):
    """ViewSet d'agrégation pour le portail enseignant."""

    permission_classes = [IsEnseignant]

    def _get_enseignant(self, request):
        return request.user.enseignant_profile

    def _affectations_queryset(self, enseignant):
        return AffectationEnseignement.objects.filter(enseignant=enseignant).select_related(
            "ecue__ue__formation__departement",
            "ue__formation__departement",
            "annee_universitaire",
        )

    def _accessible_ecue_ids(self, request):
        ecue_ids = set()
        for affectation in self._affectations_queryset(self._get_enseignant(request)):
            if affectation.ecue_id:
                ecue_ids.add(affectation.ecue_id)
            elif affectation.ue_id:
                ecue_ids.update(affectation.ue.ecues.values_list("id", flat=True))
        return ecue_ids

    @action(detail=False, methods=["get"])
    def tableau_bord(self, request):
        """Tableau de bord de l'enseignant."""
        enseignant = self._get_enseignant(request)
        affectations = self._affectations_queryset(enseignant).filter(
            annee_universitaire__en_cours=True
        )
        cours = []
        departements = set()
        for affectation in affectations:
            ecue = affectation.ecue
            ue = affectation.ue or (ecue.ue if ecue else None)
            formation = ue.formation if ue and ue.formation else None
            departement = formation.departement if formation else None
            if departement:
                departements.add(departement.nom)
            cours.append(
                {
                    "affectation_id": affectation.id,
                    "ecue_id": ecue.id if ecue else None,
                    "ecue_nom": ecue.nom if ecue else None,
                    "ue": ue.nom if ue else None,
                    "formation": formation.nom if formation else None,
                    "type": affectation.type_enseignement,
                    "heures": _decimal_to_float(affectation.heures),
                }
            )

        return Response(
            {
                "enseignant": {
                    "nom": enseignant.user.get_full_name(),
                    "corps": enseignant.corps,
                    "laboratoire": (
                        enseignant.laboratoire.nom if enseignant.laboratoire else None
                    ),
                    "departements": sorted(departements),
                },
                "cours_semestre": cours,
                "statistiques": {
                    "nb_cours": len(cours),
                    "heures_total": sum(item["heures"] or 0 for item in cours),
                },
            }
        )

    @action(detail=False, methods=["get"])
    def mes_cours(self, request):
        """Liste des cours de l'enseignant."""
        semestre_id, error = _parse_positive_int(
            request.query_params.get("semestre"),
            "semestre",
        )
        if error:
            return error
        affectations = self._affectations_queryset(self._get_enseignant(request))
        if semestre_id:
            affectations = affectations.filter(
                Q(ecue__creneaux__semestre_id=semestre_id)
                | Q(ue__ecues__creneaux__semestre_id=semestre_id)
            ).distinct()

        return Response(
            [
                {
                    "id": affectation.id,
                    "ecue": (
                        {
                            "id": affectation.ecue.id,
                            "nom": affectation.ecue.nom,
                            "code": affectation.ecue.code,
                        }
                        if affectation.ecue
                        else None
                    ),
                    "ue": (
                        (affectation.ue or affectation.ecue.ue).nom
                        if affectation.ue or affectation.ecue
                        else None
                    ),
                    "annee_universitaire": affectation.annee_universitaire.libelle,
                    "type": affectation.type_enseignement,
                    "heures": _decimal_to_float(affectation.heures),
                }
                for affectation in affectations
            ]
        )

    @action(detail=False, methods=["get"])
    def etudiants_cours(self, request):
        """Liste des étudiants pour un cours."""
        ecue_id, error = _parse_positive_int(
            request.query_params.get("ecue_id"),
            "ecue_id",
        )
        if error:
            return error
        if not ecue_id:
            return Response({"error": "ecue_id requis."}, status=400)
        semestre_id, error = _parse_positive_int(
            request.query_params.get("semestre_id"),
            "semestre_id",
        )
        if error:
            return error
        if ecue_id not in self._accessible_ecue_ids(request):
            return Response({"error": "ECUE non trouvé ou non autorisé."}, status=404)

        inscriptions = InscriptionPedagogique.objects.filter(statut="validee").select_related(
            "inscription_admin__etudiant__user",
            "inscription_admin__formation",
        )
        if semestre_id:
            inscriptions = inscriptions.filter(semestre_id=semestre_id)
        else:
            inscriptions = inscriptions.filter(semestre__annee_universitaire__en_cours=True)
        inscriptions = inscriptions.filter(Q(ecues__id=ecue_id) | Q(ues__ecues__id=ecue_id)).distinct()

        return Response(
            [
                {
                    "id": inscription.inscription_admin.etudiant.id,
                    "matricule": inscription.inscription_admin.etudiant.matricule,
                    "nom": inscription.inscription_admin.etudiant.user.get_full_name(),
                    "formation": inscription.inscription_admin.formation.nom,
                    "groupe_td": inscription.groupe_td,
                    "groupe_tp": inscription.groupe_tp,
                }
                for inscription in inscriptions
            ]
        )

    @action(detail=False, methods=["get"])
    def notes_a_saisir(self, request):
        """Notes en attente de saisie."""
        evaluations = (
            Evaluation.objects.filter(enseignant=request.user)
            .select_related("ecue__ue", "semestre")
            .annotate(notes_saisies=Count("notes"))
            .order_by("-date")[:25]
        )

        return Response(
            [
                {
                    "evaluation_id": evaluation.id,
                    "ecue_id": evaluation.ecue.id,
                    "ecue_nom": evaluation.ecue.nom,
                    "semestre": str(evaluation.semestre),
                    "titre": evaluation.titre,
                    "modalite": evaluation.modalite,
                    "date": evaluation.date.isoformat(),
                    "notes_saisies": evaluation.notes_saisies,
                }
                for evaluation in evaluations
            ]
        )

    @action(detail=False, methods=["get"])
    def emploi_du_temps(self, request):
        """Emploi du temps de l'enseignant."""
        enseignant = self._get_enseignant(request)
        semaine, error = _parse_positive_int(
            request.query_params.get("semaine"),
            "semaine",
        )
        if error:
            return error
        semestre_id, error = _parse_positive_int(
            request.query_params.get("semestre_id"),
            "semestre_id",
        )
        if error:
            return error
        creneaux = CreneauCours.objects.filter(enseignant=enseignant).select_related(
            "semestre",
            "formation",
            "ecue",
            "salle",
            "creneau_horaire",
        )
        if semestre_id:
            creneaux = creneaux.filter(semestre_id=semestre_id)
        else:
            creneaux = creneaux.filter(semestre__annee_universitaire__en_cours=True)
        if semaine:
            creneaux = creneaux.filter(semaine_debut__lte=semaine, semaine_fin__gte=semaine)
        emploi = {i: [] for i in range(7)}
        for creneau in creneaux.order_by("jour", "creneau_horaire__ordre"):
            emploi[creneau.jour].append(
                {
                    "id": creneau.id,
                    "formation": creneau.formation.nom,
                    "ecue": creneau.ecue.nom,
                    "salle": creneau.salle.nom if creneau.salle else None,
                    "groupe": creneau.groupe,
                    "type": creneau.type_cours,
                    "heure_debut": str(creneau.creneau_horaire.heure_debut),
                    "heure_fin": str(creneau.creneau_horaire.heure_fin),
                }
            )

        return Response(
            {
                "semaine": semaine,
                "emploi_du_temps": emploi,
            }
        )
