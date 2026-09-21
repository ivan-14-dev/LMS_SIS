"""API views for eleves (ViewSets DRF) - SIS Secondaire."""

from django.db.models import Q
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from sis_common.authorization import request_has_business_access

from .models import Eleve, EleveTuteur, Inscription, Tuteur
from .serializers import (
    AffectationMatiereIndividuelleSerializer,
    EleveCreateSerializer,
    EleveDetailSerializer,
    EleveListSerializer,
    EleveTuteurSerializer,
    InscriptionSerializer,
    TuteurSerializer,
)


class IsVieScolariteOrReadOnly(IsAuthenticated):
    """Permission: vie scolaire/direction pour écriture, authentifié pour lecture."""

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return True
        return request_has_business_access(
            request,
            "eleves.change_eleve",
            ("vie_scolaire", "directeur", "proviseur", "principal", "cpe"),
            tenant_group_codes=("student_manager_secondary",),
        )


class ElevesViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour élèves."""

    permission_classes = [IsVieScolariteOrReadOnly]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = [
        "statut",
        "sexe",
        "classe_actuelle",
        "bourse",
        "transport",
        "cantine",
        "interne",
    ]
    search_fields = [
        "matricule",
        "ine",
        "user__first_name",
        "user__last_name",
        "user__email",
    ]
    ordering_fields = ["matricule", "user__last_name", "date_naissance", "created_at"]
    ordering = ["user__last_name", "user__first_name"]

    def get_queryset(self):
        """Retourne les élèves de l'établissement courant."""
        qs = Eleve.objects.select_related(
            "user", "etablissement", "classe_actuelle__niveau"
        )

        # Filtrer par établissement du tenant
        request = self.request
        if hasattr(request, "tenant"):
            qs = qs.filter(etablissement=request.tenant)

        # Un élève ne voit que son propre profil
        user = request.user
        if hasattr(user, "eleve_profile"):
            if not user.is_staff and getattr(user, "role", "") == "eleve":
                qs = qs.filter(user=user)

        # Un tuteur ne voit que ses enfants
        if hasattr(user, "tuteur_profile"):
            tuteur = user.tuteur_profile
            eleves_ids = EleveTuteur.objects.filter(
                tuteur=tuteur, autorise_acces_portail=True
            ).values_list("eleve_id", flat=True)
            qs = qs.filter(id__in=eleves_ids)

        return qs

    def get_serializer_class(self):
        if self.action == "list":
            return EleveListSerializer
        elif self.action == "create":
            return EleveCreateSerializer
        return EleveDetailSerializer

    @action(detail=False, methods=["get"])
    def search(self, request):
        """Recherche avancée d'élèves."""
        q = request.query_params.get("q", "")
        qs = self.get_queryset()

        if q:
            qs = qs.filter(
                Q(matricule__icontains=q)
                | Q(ine__icontains=q)
                | Q(user__first_name__icontains=q)
                | Q(user__last_name__icontains=q)
            )

        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = EleveListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = EleveListSerializer(qs[:50], many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def inscriptions(self, request, pk=None):
        """Liste les inscriptions d'un élève."""
        eleve = self.get_object()
        inscriptions = eleve.inscriptions.select_related(
            "classe", "annee_scolaire"
        ).order_by("-annee_scolaire__date_debut")
        serializer = InscriptionSerializer(inscriptions, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def tuteurs(self, request, pk=None):
        """Liste les tuteurs d'un élève."""
        eleve = self.get_object()
        liens = eleve.tuteurs_lies.select_related("tuteur")
        serializer = EleveTuteurSerializer(liens, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def changer_classe(self, request, pk=None):
        """Change la classe d'un élève."""
        from apps.classes.models import Classe

        eleve = self.get_object()
        nouvelle_classe_id = request.data.get("classe_id")

        try:
            nouvelle_classe = Classe.objects.get(pk=nouvelle_classe_id)
        except Classe.DoesNotExist:
            return Response(
                {"error": "Classe non trouvée."}, status=status.HTTP_404_NOT_FOUND
            )

        ancienne_classe = eleve.classe_actuelle
        eleve.classe_actuelle = nouvelle_classe
        eleve.save(update_fields=["classe_actuelle", "updated_at"])

        return Response(
            {
                "id": eleve.id,
                "ancienne_classe": str(ancienne_classe) if ancienne_classe else None,
                "nouvelle_classe": str(nouvelle_classe),
                "detail": f"Élève transféré vers {nouvelle_classe.nom}.",
            }
        )

    @action(detail=True, methods=["get", "post"])
    def matieres_individuelles(self, request, pk=None):
        """Liste ou crée des matières individualisées pour un élève."""
        eleve = self.get_object()
        if request.method == "GET":
            affectations = eleve.affectations_matiere_individuelles.select_related(
                "annee_scolaire",
                "matiere",
                "programme_source__classe",
                "enseignant_principal",
            ).prefetch_related("enseignants")
            serializer = AffectationMatiereIndividuelleSerializer(affectations, many=True)
            return Response(serializer.data)

        serializer = AffectationMatiereIndividuelleSerializer(
            data=request.data,
            context={"request": request, "eleve": eleve},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save(eleve=eleve)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def retirer_matiere_individuelle(self, request, pk=None):
        """Retire une matière individualisée d'un élève."""
        eleve = self.get_object()
        affectation_id = request.data.get("affectation_id")
        affectation = eleve.affectations_matiere_individuelles.filter(id=affectation_id).first()
        if affectation is None:
            return Response(
                {"error": "Affectation individuelle introuvable."},
                status=status.HTTP_404_NOT_FOUND,
            )
        affectation.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class InscriptionsViewSet(viewsets.ModelViewSet):
    """ViewSet pour les inscriptions."""

    permission_classes = [IsVieScolariteOrReadOnly]
    serializer_class = InscriptionSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["statut", "annee_scolaire", "classe"]
    ordering = ["-annee_scolaire__date_debut", "-date_inscription"]

    def get_queryset(self):
        return Inscription.objects.select_related(
            "eleve__user", "classe", "annee_scolaire"
        )

    @action(detail=True, methods=["post"])
    def valider(self, request, pk=None):
        """Valide une inscription."""
        inscription = self.get_object()
        if inscription.statut != "en_cours":
            return Response(
                {"error": "Seules les inscriptions en cours peuvent être validées."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        inscription.statut = "validee"
        inscription.save(update_fields=["statut"])

        # Mettre à jour la classe actuelle de l'élève
        eleve = inscription.eleve
        eleve.classe_actuelle = inscription.classe
        eleve.save(update_fields=["classe_actuelle", "updated_at"])

        return Response({"detail": "Inscription validée.", "id": inscription.id})


class TuteursViewSet(viewsets.ModelViewSet):
    """ViewSet pour les tuteurs."""

    permission_classes = [IsVieScolariteOrReadOnly]
    serializer_class = TuteurSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ["lien_parente"]
    search_fields = ["nom", "prenom", "email", "telephone"]

    def get_queryset(self):
        qs = Tuteur.objects.all()
        # Filtrer par établissement du tenant
        if hasattr(self.request, "tenant"):
            qs = qs.filter(etablissement=self.request.tenant)
        return qs
