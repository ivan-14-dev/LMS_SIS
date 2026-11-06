"""Serializers for conseil de classe (SIS Secondaire)."""

from rest_framework import serializers

from sis_common.serializers import TenantBoundSerializerMixin

from .models import AppreciationConseil, ConseilClasse, DecisionConseil


class ConseilClasseListSerializer(serializers.ModelSerializer):
    """Serializer léger pour les listes de conseils."""

    classe_nom = serializers.CharField(source="classe.nom", read_only=True)
    periode_nom = serializers.CharField(source="periode", read_only=True)
    president_nom = serializers.CharField(source="president.get_full_name", read_only=True)
    statut_display = serializers.CharField(source="get_statut_display", read_only=True)
    nb_decisions = serializers.SerializerMethodField()

    class Meta:
        model = ConseilClasse
        fields = [
            "id",
            "classe",
            "classe_nom",
            "periode",
            "periode_nom",
            "date",
            "president_nom",
            "statut",
            "statut_display",
            "nb_decisions",
        ]

    def get_nb_decisions(self, obj):
        return obj.decisions.count()


class ConseilClasseDetailSerializer(TenantBoundSerializerMixin, serializers.ModelSerializer):
    """Serializer complet pour un conseil de classe."""

    classe_nom = serializers.CharField(source="classe.nom", read_only=True)
    periode_nom = serializers.CharField(source="periode", read_only=True)
    president_nom = serializers.CharField(source="president.get_full_name", read_only=True)
    secretaire_nom = serializers.CharField(source="secretaire.get_full_name", read_only=True)
    statut_display = serializers.CharField(source="get_statut_display", read_only=True)
    participants_list = serializers.SerializerMethodField()

    class Meta:
        model = ConseilClasse
        fields = [
            "id",
            "classe",
            "classe_nom",
            "periode",
            "periode_nom",
            "date",
            "president",
            "president_nom",
            "secretaire",
            "secretaire_nom",
            "participants",
            "participants_list",
            "ordre_jour",
            "pv",
            "statut",
            "statut_display",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def get_participants_list(self, obj):
        return [{"id": p.id, "nom": p.get_full_name()} for p in obj.participants.all()]

    def validate(self, attrs):
        attrs = super().validate(attrs)
        classe = attrs.get("classe", getattr(self.instance, "classe", None))
        periode = attrs.get("periode", getattr(self.instance, "periode", None))
        if classe and periode and classe.annee_scolaire_id != periode.annee_scolaire_id:
            raise serializers.ValidationError({"periode": "La période doit appartenir à l'année de la classe."})
        return attrs

    def validate_statut(self, statut):
        if self.instance is None:
            if statut != "planifie":
                raise serializers.ValidationError("Un nouveau conseil doit être planifié.")
        elif statut != self.instance.statut and not (
            statut == "annule" and self.instance.statut in ("planifie", "tenu")
        ):
            raise serializers.ValidationError(
                "La tenue et la validation doivent passer par leurs actions dédiées."
            )
        return statut


class DecisionConseilSerializer(serializers.ModelSerializer):
    """Serializer pour les décisions."""

    eleve_matricule = serializers.CharField(source="eleve.matricule", read_only=True)
    eleve_nom = serializers.CharField(source="eleve.user.get_full_name", read_only=True)
    decision_display = serializers.CharField(source="get_decision_display", read_only=True)

    class Meta:
        model = DecisionConseil
        fields = [
            "id",
            "conseil",
            "eleve",
            "eleve_matricule",
            "eleve_nom",
            "decision",
            "decision_display",
            "moyenne_generale",
            "rang",
            "motif",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class AppreciationConseilSerializer(serializers.ModelSerializer):
    """Serializer pour les appréciations."""

    eleve_matricule = serializers.CharField(source="eleve.matricule", read_only=True)
    eleve_nom = serializers.CharField(source="eleve.user.get_full_name", read_only=True)

    class Meta:
        model = AppreciationConseil
        fields = [
            "id",
            "conseil",
            "eleve",
            "eleve_matricule",
            "eleve_nom",
            "appreciation",
            "projet_orientation",
        ]
        read_only_fields = ["id"]
