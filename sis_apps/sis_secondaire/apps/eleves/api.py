"""API views for eleves (ViewSets DRF) - SIS Secondaire."""

from apps.classes.models import Classe
from django.db import transaction
from django.db.models import Q
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from sis_common.academic_lifecycle import AcademicLifecycleMixin, ensure_academic_open
from sis_common.admissions import (
    AdmissionTenantAccess,
    ReenrollmentMixin,
    activate_school_enrollment,
    scoped_admissions,
)
from sis_common.authorization import is_current_tenant_user, request_has_business_access
from sis_common.learner_import import LearnerImportMixin
from sis_common.workflow_tracking import record_workflow_event

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


def _ensure_class_capacity(classe, eleve):
    occupants = (
        Eleve.objects.filter(
            Q(classe_actuelle=classe) | Q(inscriptions__classe=classe, inscriptions__statut="validee")
        )
        .exclude(pk=eleve.pk)
        .distinct()
        .count()
    )
    if occupants >= classe.effectif_max:
        raise serializers.ValidationError({"classe": "La classe a atteint sa capacité."})


class IsVieScolariteOrReadOnly(IsAuthenticated):
    """Permission: vie scolaire/direction pour écriture, authentifié pour lecture."""

    def has_permission(self, request, view):
        if not super().has_permission(request, view) or not is_current_tenant_user(request):
            return False
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return True
        permission = getattr(view, "required_change_permission", "eleves.change_eleve")
        if hasattr(view, "required_change_permission") and request.user.has_perm(permission):
            return True
        return request_has_business_access(
            request,
            permission,
            ("vie_scolaire", "directeur", "proviseur", "principal", "cpe"),
            tenant_group_codes=("student_manager_secondary",),
        )


class ElevesViewSet(LearnerImportMixin, AcademicLifecycleMixin, viewsets.ModelViewSet):
    """ViewSet CRUD pour élèves."""

    permission_classes = [IsVieScolariteOrReadOnly]
    learner_model = Eleve
    learner_create_serializer = EleveCreateSerializer
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
        qs = Eleve.objects.select_related("user", "etablissement", "classe_actuelle__niveau")

        # Filtrer par établissement du tenant
        request = self.request
        if hasattr(request, "tenant"):
            qs = qs.filter(etablissement=request.tenant)

        # Un élève ne voit que son propre profil
        user = request.user
        if not user.is_staff and not getattr(user, "is_superuser", False) and getattr(user, "role", "") == "eleve":
            qs = qs.filter(user=user)

        # Un tuteur ne voit que ses enfants
        if getattr(user, "role", "") == "parent" and not hasattr(user, "tuteur_profile"):
            return qs.none()
        if hasattr(user, "tuteur_profile"):
            tuteur = user.tuteur_profile
            eleves_ids = EleveTuteur.objects.filter(tuteur=tuteur, autorise_acces_portail=True).values_list(
                "eleve_id", flat=True
            )
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
        inscriptions = eleve.inscriptions.select_related("classe", "annee_scolaire").order_by(
            "-annee_scolaire__date_debut"
        )
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
    @transaction.atomic
    def changer_classe(self, request, pk=None):
        """Transfert sans conversion implicite des règles ou des résultats."""
        from apps.examens.models import ResultatExamen
        from apps.notes.models import Note

        eleve = self.get_object()
        nouvelle_classe_id = serializers.IntegerField(min_value=1).run_validation(request.data.get("classe_id"))
        motif = serializers.CharField(allow_blank=False, max_length=2000).run_validation(request.data.get("motif"))

        try:
            nouvelle_classe = Classe.objects.select_for_update().get(
                pk=nouvelle_classe_id, etablissement=request.tenant
            )
        except Classe.DoesNotExist:
            return Response({"error": "Classe non trouvée."}, status=status.HTTP_404_NOT_FOUND)

        ancienne_classe = eleve.classe_actuelle
        if ancienne_classe is None or ancienne_classe.annee_scolaire_id != nouvelle_classe.annee_scolaire_id:
            raise serializers.ValidationError({"classe_id": "Pour une nouvelle année, créez une inscription."})
        if ancienne_classe.pk == nouvelle_classe.pk:
            raise serializers.ValidationError({"classe_id": "Sélectionnez une autre classe."})
        ensure_academic_open(ancienne_classe, {"annee_scolaire": nouvelle_classe.annee_scolaire}, ("annee_scolaire",))
        inscription = (
            eleve.inscriptions.select_for_update()
            .filter(annee_scolaire=nouvelle_classe.annee_scolaire, classe=ancienne_classe, statut="validee")
            .first()
        )
        if inscription is None:
            raise serializers.ValidationError(
                {"detail": "Une inscription validée dans la classe actuelle est requise."}
            )
        if (
            inscription.offre_configuration
            or nouvelle_classe.offre_configuration
            or Note.objects.filter(eleve=eleve, evaluation__periode__annee_scolaire=inscription.annee_scolaire).exists()
            or ResultatExamen.objects.filter(
                eleve=eleve, epreuve__session__annee_scolaire=inscription.annee_scolaire
            ).exists()
        ):
            raise serializers.ValidationError(
                {
                    "detail": (
                        "Ce dossier possède des règles historisées ou des résultats. "
                        "Un traitement des équivalences est requis."
                    )
                }
            )
        _ensure_class_capacity(nouvelle_classe, eleve)
        inscription.classe = nouvelle_classe
        inscription.save(update_fields=["classe"])
        eleve.classe_actuelle = nouvelle_classe
        eleve.save(update_fields=["classe_actuelle", "updated_at"])
        record_workflow_event(
            request,
            inscription,
            "transfert",
            "Changement de classe",
            message=motif,
            recipients=[eleve.user],
            metadata={"ancienne_classe_id": ancienne_classe.pk, "nouvelle_classe_id": nouvelle_classe.pk},
        )

        return Response(
            {
                "id": eleve.id,
                "ancienne_classe": str(ancienne_classe) if ancienne_classe else None,
                "nouvelle_classe": str(nouvelle_classe),
                "detail": f"Élève transféré vers {nouvelle_classe.nom}.",
            }
        )

    @action(detail=True, methods=["get", "post"])
    @transaction.atomic
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
        ensure_academic_open(data=serializer.validated_data, paths=("annee_scolaire",))
        serializer.save(eleve=eleve)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    @transaction.atomic
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
        ensure_academic_open(affectation, paths=("annee_scolaire",))
        affectation.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class InscriptionsViewSet(ReenrollmentMixin, AcademicLifecycleMixin, viewsets.ModelViewSet):
    """ViewSet pour les inscriptions."""

    permission_classes = [AdmissionTenantAccess, IsVieScolariteOrReadOnly]
    required_change_permission = "eleves.change_inscription"
    serializer_class = InscriptionSerializer
    academic_period_paths = ("annee_scolaire", "classe.annee_scolaire")
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["statut", "annee_scolaire", "classe"]
    ordering = ["-annee_scolaire__date_debut", "-date_inscription"]

    def get_queryset(self):
        qs = Inscription.objects.select_related("eleve__user", "classe", "annee_scolaire")
        qs = qs.filter(eleve__etablissement=self.request.tenant)
        user = self.request.user
        if user.role in ("eleve", "parent") and not user.is_superuser:
            return qs.filter(
                Q(eleve__user=user)
                | Q(eleve__tuteurs_lies__tuteur__user=user, eleve__tuteurs_lies__autorise_acces_portail=True)
            ).distinct()
        if (
            user.has_perm("eleves.view_inscription")
            or (
                self.request.method not in ("GET", "HEAD", "OPTIONS") and user.has_perm(self.required_change_permission)
            )
            or request_has_business_access(
                self.request,
                "eleves.view_inscription",
                ("vie_scolaire", "directeur", "proviseur", "principal", "cpe"),
                tenant_group_codes=("student_manager_secondary",),
            )
        ):
            return scoped_admissions(qs, self.request)
        return qs.filter(
            Q(eleve__user=self.request.user)
            | Q(eleve__tuteurs_lies__tuteur__user=self.request.user, eleve__tuteurs_lies__autorise_acces_portail=True)
        ).distinct()

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def valider(self, request, pk=None):
        """Valide une inscription."""
        inscription = self.get_object()
        ensure_academic_open(inscription, paths=self.academic_period_paths)
        if inscription.statut != "en_cours":
            return Response(
                {"error": "Seules les inscriptions en cours peuvent être validées."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        classe = Classe.objects.select_for_update().get(pk=inscription.classe_id)
        _ensure_class_capacity(classe, inscription.eleve)
        inscription.statut = "validee"
        inscription.save(update_fields=["statut"])

        eleve = inscription.eleve
        activate_school_enrollment(inscription)
        record_workflow_event(
            request,
            inscription,
            "validation",
            "Inscription validée",
            recipients=[eleve.user],
            metadata={"classe_id": inscription.classe_id},
        )

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
