"""API views for bourses (SIS Supérieur)."""

from django.db.models import Sum
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import AttributionBourse, DemandeBourse, TypeBourse, VersementBourse
from .serializers import (
    AttributionBourseCreateSerializer,
    AttributionBourseDetailSerializer,
    AttributionBourseListSerializer,
    DecisionBourseSerializer,
    DemandeBourseCreateSerializer,
    DemandeBourseDetailSerializer,
    DemandeBourseListSerializer,
    DemandeBourseUpdateSerializer,
    TypeBourseDetailSerializer,
    TypeBourseListSerializer,
    VersementBourseCreateSerializer,
    VersementBourseSerializer,
)


class TypeBourseViewSet(viewsets.ModelViewSet):
    """ViewSet pour les types de bourses."""

    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["categorie", "actif"]
    search_fields = ["nom", "description"]

    def get_queryset(self):
        return TypeBourse.objects.all()

    def get_serializer_class(self):
        if self.action == "list":
            return TypeBourseListSerializer
        return TypeBourseDetailSerializer

    @action(detail=False, methods=["get"])
    def actifs(self, request):
        """Liste des types de bourses actifs."""
        types = self.get_queryset().filter(actif=True)
        serializer = TypeBourseListSerializer(types, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def statistiques(self, request, pk=None):
        """Statistiques d'un type de bourse."""
        type_bourse = self.get_object()
        demandes = type_bourse.demandes.all()
        return Response(
            {
                "type_bourse": type_bourse.nom,
                "total_demandes": demandes.count(),
                "demandes_acceptees": demandes.filter(statut="acceptee").count(),
                "demandes_refusees": demandes.filter(statut="refusee").count(),
                "demandes_en_attente": demandes.filter(
                    statut__in=["soumise", "en_instruction"]
                ).count(),
            }
        )


class DemandeBourseViewSet(viewsets.ModelViewSet):
    """ViewSet pour les demandes de bourse."""

    permission_classes = [IsAuthenticated]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["statut", "type_bourse", "annee_universitaire"]
    search_fields = ["etudiant__nom", "etudiant__prenom", "etudiant__matricule"]
    ordering_fields = ["created_at", "date_soumission"]
    ordering = ["-created_at"]

    def get_queryset(self):
        return DemandeBourse.objects.select_related(
            "etudiant", "type_bourse", "annee_universitaire", "decision_par"
        ).prefetch_related("attribution")

    def get_serializer_class(self):
        if self.action == "list":
            return DemandeBourseListSerializer
        if self.action == "create":
            return DemandeBourseCreateSerializer
        if self.action in ["update", "partial_update"]:
            return DemandeBourseUpdateSerializer
        return DemandeBourseDetailSerializer

    @action(detail=True, methods=["post"])
    def soumettre(self, request, pk=None):
        """Soumettre une demande de bourse."""
        demande = self.get_object()
        if demande.statut != "brouillon":
            return Response(
                {"error": "Seules les demandes en brouillon peuvent être soumises."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        demande.statut = "soumise"
        demande.date_soumission = timezone.now()
        demande.save()
        return Response({"status": "Demande soumise avec succès."})

    @action(detail=True, methods=["post"])
    def decision(self, request, pk=None):
        """Prendre une décision sur une demande."""
        demande = self.get_object()
        serializer = DecisionBourseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        demande.statut = data["decision"]
        demande.date_decision = timezone.now()
        demande.decision_par = request.user.utilisateur
        demande.motif_refus = data.get("motif", "")
        demande.commentaires_instruction = data.get("commentaires", "")
        demande.save()

        return Response(
            {
                "status": f"Demande {data['decision']}.",
                "demande": DemandeBourseDetailSerializer(demande).data,
            }
        )

    @action(detail=True, methods=["post"])
    def creer_attribution(self, request, pk=None):
        """Créer l'attribution pour une demande acceptée."""
        demande = self.get_object()
        if demande.statut != "acceptee":
            return Response(
                {"error": "La demande doit être acceptée pour créer une attribution."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if hasattr(demande, "attribution"):
            return Response(
                {"error": "Une attribution existe déjà pour cette demande."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = AttributionBourseCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Générer numéro d'attribution
        annee = demande.annee_universitaire.annee_debut
        count = (
            AttributionBourse.objects.filter(
                numero_attribution__startswith=f"ATT-{annee}"
            ).count()
            + 1
        )
        numero = f"ATT-{annee}-{count:05d}"

        data = serializer.validated_data
        montant_total = data["montant_mensuel"] * demande.type_bourse.duree_mois

        attribution = AttributionBourse.objects.create(
            demande=demande,
            numero_attribution=numero,
            montant_total=montant_total,
            **data,
        )

        return Response(
            AttributionBourseDetailSerializer(attribution).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=["get"])
    def mes_demandes(self, request):
        """Demandes de l'étudiant connecté."""
        etudiant = getattr(request.user, "etudiant", None)
        if not etudiant:
            return Response({"error": "Utilisateur non étudiant."}, status=400)

        demandes = self.get_queryset().filter(etudiant=etudiant)
        serializer = DemandeBourseListSerializer(demandes, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def statistiques(self, request):
        """Statistiques globales des bourses."""
        annee_id = request.query_params.get("annee")
        qs = DemandeBourse.objects.all()
        if annee_id:
            qs = qs.filter(annee_universitaire_id=annee_id)

        stats = {
            "total_demandes": qs.count(),
            "demandes_en_attente": qs.filter(
                statut__in=["soumise", "en_instruction"]
            ).count(),
            "demandes_acceptees": qs.filter(statut="acceptee").count(),
            "demandes_refusees": qs.filter(statut="refusee").count(),
            "attributions_actives": AttributionBourse.objects.filter(
                statut="active"
            ).count(),
            "montant_total_attribue": AttributionBourse.objects.filter(
                statut="active"
            ).aggregate(total=Sum("montant_total"))["total"]
            or 0,
            "montant_total_verse": VersementBourse.objects.filter(
                statut="effectue"
            ).aggregate(total=Sum("montant"))["total"]
            or 0,
        }
        return Response(stats)


class AttributionBourseViewSet(viewsets.ModelViewSet):
    """ViewSet pour les attributions de bourses."""

    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["statut"]
    search_fields = ["numero_attribution", "demande__etudiant__nom"]

    def get_queryset(self):
        return AttributionBourse.objects.select_related(
            "demande__etudiant", "demande__type_bourse"
        ).prefetch_related("versements")

    def get_serializer_class(self):
        if self.action == "list":
            return AttributionBourseListSerializer
        return AttributionBourseDetailSerializer

    @action(detail=True, methods=["post"])
    def suspendre(self, request, pk=None):
        """Suspendre une attribution."""
        attribution = self.get_object()
        motif = request.data.get("motif", "")
        if not motif:
            return Response({"error": "Le motif est requis."}, status=400)

        attribution.statut = "suspendue"
        attribution.motif_suspension = motif
        attribution.save()
        return Response({"status": "Attribution suspendue."})

    @action(detail=True, methods=["post"])
    def reactiver(self, request, pk=None):
        """Réactiver une attribution suspendue."""
        attribution = self.get_object()
        if attribution.statut != "suspendue":
            return Response(
                {
                    "error": "Seules les attributions suspendues peuvent être réactivées."
                },
                status=400,
            )

        attribution.statut = "active"
        attribution.motif_suspension = ""
        attribution.save()
        return Response({"status": "Attribution réactivée."})

    @action(detail=True, methods=["get", "post"])
    def versements(self, request, pk=None):
        """Lister ou créer des versements."""
        attribution = self.get_object()

        if request.method == "GET":
            serializer = VersementBourseSerializer(
                attribution.versements.all(), many=True
            )
            return Response(serializer.data)

        serializer = VersementBourseCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        versement = serializer.save(attribution=attribution)
        return Response(
            VersementBourseSerializer(versement).data, status=status.HTTP_201_CREATED
        )

    @action(detail=True, methods=["post"])
    def generer_versements(self, request, pk=None):
        """Générer automatiquement les versements planifiés."""
        attribution = self.get_object()
        from dateutil.relativedelta import relativedelta

        versements_crees = []
        current_date = attribution.date_debut.replace(day=1)
        end_date = attribution.date_fin

        while current_date <= end_date:
            versement, created = VersementBourse.objects.get_or_create(
                attribution=attribution,
                mois=current_date,
                defaults={"montant": attribution.montant_mensuel},
            )
            if created:
                versements_crees.append(versement)
            current_date = current_date + relativedelta(months=1)

        return Response(
            {
                "status": f"{len(versements_crees)} versements créés.",
                "versements": VersementBourseSerializer(
                    versements_crees, many=True
                ).data,
            }
        )


class VersementBourseViewSet(viewsets.ModelViewSet):
    """ViewSet pour les versements de bourses."""

    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["statut", "attribution"]
    serializer_class = VersementBourseSerializer

    def get_queryset(self):
        return VersementBourse.objects.select_related("attribution__demande__etudiant")

    @action(detail=True, methods=["post"])
    def effectuer(self, request, pk=None):
        """Marquer un versement comme effectué."""
        versement = self.get_object()
        versement.statut = "effectue"
        versement.date_virement = timezone.now().date()
        versement.reference_virement = request.data.get("reference", "")
        versement.save()
        return Response(VersementBourseSerializer(versement).data)

    @action(detail=False, methods=["post"])
    def effectuer_batch(self, request):
        """Effectuer plusieurs versements en lot."""
        ids = request.data.get("versement_ids", [])
        reference = request.data.get("reference", "")

        versements = VersementBourse.objects.filter(id__in=ids, statut="planifie")
        count = versements.update(
            statut="effectue",
            date_virement=timezone.now().date(),
            reference_virement=reference,
        )
        return Response({"status": f"{count} versements effectués."})
