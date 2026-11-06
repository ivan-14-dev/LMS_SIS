"""API views for presences (ViewSets DRF) - SIS Secondaire."""

from django.db import transaction
from django.db.models import Count
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.filters import OrderingFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from sis_common.authorization import is_current_tenant_user, request_has_business_access, user_has_any_role

from .models import Appel, Justificatif, Presence
from .serializers import (
    AppelDetailSerializer,
    AppelListSerializer,
    JustificatifSerializer,
    PresenceSaisieSerializer,
    PresenceSerializer,
    validate_attendance,
)


class IsEnseignantOrVieScolarite(IsAuthenticated):
    """Permission: enseignant ou vie scolaire."""

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return True
        if getattr(view, "action", None) == "valider":
            return request_has_business_access(
                request,
                "presences.change_appel",
                ("vie_scolaire", "cpe", "directeur", "proviseur", "principal"),
                tenant_group_codes=("attendance_manager_secondary",),
            )
        return request_has_business_access(
            request,
            "presences.change_appel",
            (
                "enseignant",
                "vie_scolaire",
                "cpe",
                "directeur",
                "proviseur",
                "principal",
            ),
            tenant_group_codes=("attendance_manager_secondary",),
        )


class AppelsViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour appels."""

    permission_classes = [IsEnseignantOrVieScolarite]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["creneau", "date", "enseignant", "statut"]
    ordering_fields = ["date", "creneau__heure_debut"]
    ordering = ["-date", "-creneau__heure_debut"]

    def get_queryset(self):
        qs = Appel.objects.select_related("creneau", "enseignant__user")
        user = self.request.user
        if not user.is_staff and user_has_any_role(user, ("enseignant",)):
            if hasattr(user, "personnel_profile"):
                return qs.filter(enseignant=user.personnel_profile)
            return qs.none()
        if request_has_business_access(
            self.request,
            "presences.view_appel",
            ("vie_scolaire", "cpe", "directeur", "proviseur", "principal"),
            tenant_group_codes=("attendance_manager_secondary",),
        ):
            return qs
        return qs.none()

    def get_serializer_class(self):
        if self.action == "list":
            return AppelListSerializer
        return AppelDetailSerializer

    @transaction.atomic
    def perform_update(self, serializer):
        appel = Appel.objects.select_for_update().get(pk=serializer.instance.pk)
        validate_attendance(self.request, appel)
        serializer.save()

    @transaction.atomic
    def perform_destroy(self, instance):
        appel = Appel.objects.select_for_update().get(pk=instance.pk)
        validate_attendance(self.request, appel)
        instance.delete()

    @action(detail=True, methods=["get"])
    def presences(self, request, pk=None):
        """Liste les présences de l'appel."""
        appel = self.get_object()
        presences = appel.presences.select_related("eleve__user").order_by("eleve__user__last_name")
        serializer = PresenceSerializer(presences, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def saisir_presences(self, request, pk=None):
        """Saisie en masse des présences."""
        appel = self.get_object()
        appel = Appel.objects.select_for_update().get(pk=appel.pk)
        validate_attendance(request, appel)
        serializer = PresenceSaisieSerializer(data=request.data, many=True)
        serializer.is_valid(raise_exception=True)
        identifiers = [item["eleve_id"] for item in serializer.validated_data]
        if len(set(identifiers)) != len(identifiers):
            raise ValidationError({"eleve_id": "Un élève ne peut apparaître qu'une fois dans le lot."})
        from apps.eleves.models import Eleve

        valid_ids = set(
            Eleve.objects.filter(pk__in=identifiers, classe_actuelle_id=appel.creneau.classe_id).values_list(
                "pk", flat=True
            )
        )
        if valid_ids != set(identifiers):
            raise ValidationError({"eleve_id": "Tous les élèves doivent appartenir à la classe de l'appel."})

        created = 0
        updated = 0
        for item in serializer.validated_data:
            presence, was_created = Presence.objects.update_or_create(
                appel=appel,
                eleve_id=item["eleve_id"],
                defaults={
                    "statut": item["statut"],
                    "retard_minutes": item.get("retard_minutes"),
                    "commentaire": item.get("commentaire", ""),
                },
            )
            if was_created:
                created += 1
            else:
                updated += 1

        return Response(
            {
                "appel_id": appel.id,
                "presences_creees": created,
                "presences_modifiees": updated,
            }
        )

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def fermer(self, request, pk=None):
        """Ferme un appel."""
        appel = self.get_object()
        appel = Appel.objects.select_for_update().get(pk=appel.pk)
        if appel.statut != "ouvert":
            return Response({"error": "L'appel n'est pas ouvert."}, status=400)
        appel.statut = "ferme"
        appel.save(update_fields=["statut", "updated_at"])
        return Response({"detail": "Appel fermé.", "id": appel.id})

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def valider(self, request, pk=None):
        """Valide un appel (par CPE/direction)."""
        appel = self.get_object()
        appel = Appel.objects.select_for_update().get(pk=appel.pk)
        if appel.statut != "ferme":
            return Response({"error": "L'appel doit d'abord être fermé."}, status=400)
        appel.statut = "valide"
        appel.date_validation = timezone.now()
        appel.save(update_fields=["statut", "date_validation", "updated_at"])
        return Response({"detail": "Appel validé.", "id": appel.id})

    @action(detail=True, methods=["get"])
    def statistiques(self, request, pk=None):
        """Statistiques de l'appel."""
        appel = self.get_object()
        stats = appel.presences.values("statut").annotate(count=Count("id"))
        result = {s["statut"]: s["count"] for s in stats}
        return Response(
            {
                "appel_id": appel.id,
                "date": appel.date,
                "presents": result.get("present", 0),
                "absents": result.get("absent", 0),
                "absents_justifies": result.get("absent_justifie", 0),
                "retards": result.get("retard", 0),
                "dispenses": result.get("dispense", 0),
            }
        )


class PresencesViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour présences."""

    permission_classes = [IsEnseignantOrVieScolarite]
    serializer_class = PresenceSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["appel", "eleve", "statut"]
    ordering = ["eleve__user__last_name"]

    @transaction.atomic
    def perform_create(self, serializer):
        appel = Appel.objects.select_for_update().get(pk=serializer.validated_data["appel"].pk)
        validate_attendance(self.request, appel, serializer.validated_data["eleve"])
        serializer.save()

    @transaction.atomic
    def perform_update(self, serializer):
        appel = serializer.validated_data.get("appel", serializer.instance.appel)
        appel = Appel.objects.select_for_update().get(pk=appel.pk)
        validate_attendance(
            self.request,
            appel,
            serializer.validated_data.get("eleve", serializer.instance.eleve),
        )
        serializer.save()

    @transaction.atomic
    def perform_destroy(self, instance):
        appel = Appel.objects.select_for_update().get(pk=instance.appel_id)
        validate_attendance(self.request, appel, instance.eleve)
        instance.delete()

    def get_queryset(self):
        qs = Presence.objects.select_related("appel", "eleve__user")
        user = self.request.user
        if hasattr(user, "eleve_profile"):
            if not user.is_staff and user_has_any_role(user, ("eleve",)):
                return qs.filter(eleve__user=user)
        if hasattr(user, "tuteur_profile"):
            from apps.eleves.models import EleveTuteur

            eleves_ids = EleveTuteur.objects.filter(
                tuteur=user.tuteur_profile, autorise_acces_portail=True
            ).values_list("eleve_id", flat=True)
            return qs.filter(eleve_id__in=eleves_ids)
        if not user.is_staff and user_has_any_role(user, ("enseignant",)):
            if hasattr(user, "personnel_profile"):
                return qs.filter(appel__enseignant=user.personnel_profile)
            return qs.none()
        if request_has_business_access(
            self.request,
            "presences.view_presence",
            ("vie_scolaire", "cpe", "directeur", "proviseur", "principal"),
            tenant_group_codes=("attendance_manager_secondary",),
        ):
            return qs
        return qs.none()


class JustificatifsViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour justificatifs."""

    permission_classes = [IsEnseignantOrVieScolarite]
    serializer_class = JustificatifSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["statut"]
    ordering = ["-date_depot"]

    def get_queryset(self):
        qs = Justificatif.objects.select_related("presence__eleve__user", "presence__appel", "valide_par__user")
        user = self.request.user
        if hasattr(user, "eleve_profile") and not user.is_staff and user_has_any_role(user, ("eleve",)):
            return qs.filter(presence__eleve__user=user)
        if hasattr(user, "tuteur_profile"):
            from apps.eleves.models import EleveTuteur

            eleves_ids = EleveTuteur.objects.filter(
                tuteur=user.tuteur_profile, autorise_acces_portail=True
            ).values_list("eleve_id", flat=True)
            return qs.filter(presence__eleve_id__in=eleves_ids)
        if not user.is_staff and user_has_any_role(user, ("enseignant",)):
            if hasattr(user, "personnel_profile"):
                return qs.filter(presence__appel__enseignant=user.personnel_profile)
            return qs.none()
        if request_has_business_access(
            self.request,
            "presences.view_justificatif",
            ("vie_scolaire", "cpe", "directeur", "proviseur", "principal"),
            tenant_group_codes=("attendance_manager_secondary",),
        ):
            return qs
        return qs.none()

    @transaction.atomic
    def perform_update(self, serializer):
        justificatif = Justificatif.objects.select_for_update().get(pk=serializer.instance.pk)
        if justificatif.statut != "en_attente":
            raise ValidationError({"statut": "Une décision déjà prise ne peut être modifiée."})
        serializer.instance = justificatif
        serializer.save()

    @transaction.atomic
    def perform_destroy(self, instance):
        justificatif = Justificatif.objects.select_for_update().get(pk=instance.pk)
        if justificatif.statut != "en_attente":
            raise ValidationError({"statut": "Une décision déjà prise ne peut être supprimée."})
        justificatif.delete()

    def _pending_review(self, request):
        if not is_current_tenant_user(request):
            raise PermissionDenied()
        justificatif = self.get_object()
        justificatif = get_object_or_404(Justificatif.objects.select_for_update(), pk=justificatif.pk)
        if justificatif.statut != "en_attente":
            raise ValidationError({"statut": "Ce justificatif a déjà été traité."})
        return justificatif

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def accepter(self, request, pk=None):
        """Accepte un justificatif."""
        justificatif = self._pending_review(request)
        presence = Presence.objects.select_for_update().select_related(
            "eleve__user", "appel__creneau__classe__annee_scolaire", "appel__creneau__matiere",
            "appel__enseignant__user",
        ).get(pk=justificatif.presence_id)
        appel = presence.appel
        creneau = appel.creneau
        classe = creneau.classe
        eleve = presence.eleve
        tenant_id = request.tenant.pk
        if (
            presence.statut != "absent"
            or eleve.etablissement_id != tenant_id
            or eleve.user.etablissement_id != tenant_id
            or classe.etablissement_id != tenant_id
            or classe.annee_scolaire.etablissement_id != tenant_id
            or creneau.matiere.etablissement_id != tenant_id
            or appel.enseignant.user.etablissement_id != tenant_id
            or appel.enseignant_id != creneau.enseignant_id
            or not classe.annee_scolaire.date_debut <= appel.date <= classe.annee_scolaire.date_fin
            or creneau.jour != appel.date.isoweekday()
            or (creneau.date_specifique is not None and creneau.date_specifique != appel.date)
            or (
                eleve.classe_actuelle_id != classe.pk
                and not eleve.inscriptions.filter(
                    classe=classe,
                    annee_scolaire=classe.annee_scolaire,
                    date_inscription__lte=appel.date,
                    statut="validee",
                ).exists()
            )
        ):
            raise ValidationError({"presence": "Cette absence ne correspond pas à un cours de cet établissement."})

        valide_par = None
        if hasattr(request.user, "personnel_profile"):
            valide_par = request.user.personnel_profile

        justificatif.statut = "accepte"
        justificatif.valide_par = valide_par
        justificatif.date_validation = timezone.now()
        justificatif.commentaire_validation = request.data.get("commentaire", "")
        justificatif.save()

        presence.statut = "absent_justifie"
        presence.save(update_fields=["statut"])

        return Response({"detail": "Justificatif accepté.", "id": justificatif.id})

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def refuser(self, request, pk=None):
        """Refuse un justificatif."""
        justificatif = self._pending_review(request)

        valide_par = None
        if hasattr(request.user, "personnel_profile"):
            valide_par = request.user.personnel_profile

        justificatif.statut = "refuse"
        justificatif.valide_par = valide_par
        justificatif.date_validation = timezone.now()
        justificatif.commentaire_validation = request.data.get("commentaire", "")
        justificatif.save()

        return Response({"detail": "Justificatif refusé.", "id": justificatif.id})
