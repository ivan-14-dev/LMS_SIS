"""API views for notes (ViewSets DRF) - SIS Secondaire."""

from django.db.models import Avg, Count
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Bulletin, Evaluation, Note
from .serializers import (
    BulletinDetailSerializer,
    BulletinListSerializer,
    EvaluationDetailSerializer,
    EvaluationListSerializer,
    NoteSaisieSerializer,
    NoteSerializer,
)


class IsEnseignantOrVieScolarite(IsAuthenticated):
    """Permission: enseignant ou vie scolaire."""

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return True
        user = request.user
        return user.is_staff or getattr(user, "role", "") in (
            "enseignant",
            "vie_scolaire",
            "directeur",
            "proviseur",
            "principal",
        )


class EvaluationsViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour évaluations."""

    permission_classes = [IsEnseignantOrVieScolarite]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["matiere", "classe", "periode", "type", "enseignant"]
    search_fields = ["titre", "description"]
    ordering_fields = ["date", "titre", "created_at"]
    ordering = ["-date"]

    def get_queryset(self):
        qs = Evaluation.objects.select_related(
            "matiere", "classe", "periode", "enseignant__user"
        )
        # Un enseignant ne voit que ses évaluations
        user = self.request.user
        if not user.is_staff and getattr(user, "role", "") == "enseignant":
            if hasattr(user, "personnel_profile"):
                qs = qs.filter(enseignant=user.personnel_profile)
        return qs

    def get_serializer_class(self):
        if self.action == "list":
            return EvaluationListSerializer
        return EvaluationDetailSerializer

    @action(detail=True, methods=["get"])
    def notes(self, request, pk=None):
        """Liste les notes d'une évaluation."""
        evaluation = self.get_object()
        notes = evaluation.notes.select_related("eleve__user").order_by(
            "eleve__user__last_name"
        )
        serializer = NoteSerializer(notes, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def saisir_notes(self, request, pk=None):
        """Saisie en masse des notes."""
        evaluation = self.get_object()
        serializer = NoteSaisieSerializer(data=request.data, many=True)
        serializer.is_valid(raise_exception=True)

        created = 0
        updated = 0
        saisi_par = None
        if hasattr(request.user, "personnel_profile"):
            saisi_par = request.user.personnel_profile

        for item in serializer.validated_data:
            note, was_created = Note.objects.update_or_create(
                evaluation=evaluation,
                eleve_id=item["eleve_id"],
                defaults={
                    "valeur": item["valeur"],
                    "statut": item.get("statut", "presente"),
                    "appreciation": item.get("appreciation", ""),
                    "saisi_par": saisi_par,
                },
            )
            if was_created:
                created += 1
            else:
                updated += 1
                note.modifie_le = timezone.now()
                note.modifie_par = saisi_par
                note.save(update_fields=["modifie_le", "modifie_par"])

        return Response(
            {
                "evaluation_id": evaluation.id,
                "notes_creees": created,
                "notes_modifiees": updated,
            }
        )

    @action(detail=True, methods=["get"])
    def statistiques(self, request, pk=None):
        """Statistiques de l'évaluation."""
        evaluation = self.get_object()
        notes = evaluation.notes.filter(valeur__isnull=False)
        stats = notes.aggregate(
            moyenne=Avg("valeur"),
            nb_notes=Count("id"),
        )
        absents = evaluation.notes.filter(statut="absente").count()
        return Response(
            {
                "evaluation_id": evaluation.id,
                "moyenne": float(stats["moyenne"]) if stats["moyenne"] else None,
                "nb_notes": stats["nb_notes"],
                "nb_absents": absents,
                "bareme": float(evaluation.bareme),
            }
        )


class NotesViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour notes."""

    permission_classes = [IsEnseignantOrVieScolarite]
    serializer_class = NoteSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["evaluation", "eleve", "statut"]
    ordering = ["eleve__user__last_name"]

    def get_queryset(self):
        qs = Note.objects.select_related("evaluation", "eleve__user")
        user = self.request.user
        # Un élève ne voit que ses propres notes
        if hasattr(user, "eleve_profile"):
            if not user.is_staff and getattr(user, "role", "") == "eleve":
                qs = qs.filter(eleve__user=user)
        # Un parent ne voit que les notes de ses enfants
        if hasattr(user, "tuteur_profile"):
            from apps.eleves.models import EleveTuteur

            eleves_ids = EleveTuteur.objects.filter(
                tuteur=user.tuteur_profile, autorise_acces_portail=True
            ).values_list("eleve_id", flat=True)
            qs = qs.filter(eleve_id__in=eleves_ids)
        return qs


class BulletinsViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour bulletins."""

    permission_classes = [IsEnseignantOrVieScolarite]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["eleve", "classe", "periode", "publie"]
    ordering = ["-periode__date_fin"]

    def get_queryset(self):
        qs = Bulletin.objects.select_related("eleve__user", "classe", "periode")
        user = self.request.user
        # Un élève ne voit que ses propres bulletins publiés
        if hasattr(user, "eleve_profile"):
            if not user.is_staff and getattr(user, "role", "") == "eleve":
                qs = qs.filter(eleve__user=user, publie=True)
        # Un parent ne voit que les bulletins publiés de ses enfants
        if hasattr(user, "tuteur_profile"):
            from apps.eleves.models import EleveTuteur

            eleves_ids = EleveTuteur.objects.filter(
                tuteur=user.tuteur_profile, autorise_acces_portail=True
            ).values_list("eleve_id", flat=True)
            qs = qs.filter(eleve_id__in=eleves_ids, publie=True)
        return qs

    def get_serializer_class(self):
        if self.action == "list":
            return BulletinListSerializer
        return BulletinDetailSerializer

    @action(detail=True, methods=["post"])
    def publier(self, request, pk=None):
        """Publie un bulletin."""
        bulletin = self.get_object()
        if bulletin.publie:
            return Response({"error": "Ce bulletin est déjà publié."}, status=400)
        bulletin.publie = True
        bulletin.date_publication = timezone.now()
        bulletin.save(update_fields=["publie", "date_publication", "updated_at"])
        return Response({"detail": "Bulletin publié.", "id": bulletin.id})

    @action(detail=True, methods=["post"])
    def signer(self, request, pk=None):
        """Signe un bulletin (par le chef d'établissement)."""
        bulletin = self.get_object()
        if bulletin.signe:
            return Response({"error": "Ce bulletin est déjà signé."}, status=400)
        bulletin.signe = True
        bulletin.date_signature = timezone.now()
        bulletin.save(update_fields=["signe", "date_signature", "updated_at"])
        return Response({"detail": "Bulletin signé.", "id": bulletin.id})
