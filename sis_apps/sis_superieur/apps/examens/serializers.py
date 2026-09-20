"""Serializers for examens (SIS Supérieur)."""

from rest_framework import serializers

from .models import ConvocationExamen, EpreuveExamen, SessionExamen


class SessionExamenSerializer(serializers.ModelSerializer):
    """Serializer pour les sessions d'examens."""

    numero_display = serializers.CharField(source="get_numero_display", read_only=True)
    type_display = serializers.CharField(source="get_type_display", read_only=True)
    semestre_libelle = serializers.CharField(source="semestre.libelle", read_only=True)
    nb_epreuves = serializers.SerializerMethodField()

    class Meta:
        model = SessionExamen
        fields = [
            "id",
            "semestre",
            "semestre_libelle",
            "numero",
            "numero_display",
            "type",
            "type_display",
            "date_debut",
            "date_fin",
            "cloturee",
            "nb_epreuves",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def get_nb_epreuves(self, obj):
        if hasattr(obj, "nb_epreuves_count"):
            return obj.nb_epreuves_count
        return obj.epreuves.count()


class EpreuveExamenListSerializer(serializers.ModelSerializer):
    """Serializer léger pour les listes d'épreuves."""

    ecue_code = serializers.CharField(source="ecue.code", read_only=True)
    ecue_nom = serializers.CharField(source="ecue.nom", read_only=True)
    session_numero = serializers.IntegerField(source="session.numero", read_only=True)
    nb_convoques = serializers.SerializerMethodField()

    class Meta:
        model = EpreuveExamen
        fields = [
            "id",
            "session",
            "session_numero",
            "ecue",
            "ecue_code",
            "ecue_nom",
            "date",
            "heure_debut",
            "duree_minutes",
            "lieu",
            "places_totales",
            "nb_convoques",
        ]

    def get_nb_convoques(self, obj):
        if hasattr(obj, "nb_convoques_count"):
            return obj.nb_convoques_count
        return obj.convocations.count()


class EpreuveExamenDetailSerializer(serializers.ModelSerializer):
    """Serializer complet pour une épreuve."""

    ecue_code = serializers.CharField(source="ecue.code", read_only=True)
    ecue_nom = serializers.CharField(source="ecue.nom", read_only=True)
    session_numero = serializers.IntegerField(source="session.numero", read_only=True)
    surveillants_noms = serializers.SerializerMethodField()
    nb_convoques = serializers.SerializerMethodField()
    nb_presents = serializers.SerializerMethodField()

    class Meta:
        model = EpreuveExamen
        fields = [
            "id",
            "session",
            "session_numero",
            "ecue",
            "ecue_code",
            "ecue_nom",
            "date",
            "heure_debut",
            "duree_minutes",
            "lieu",
            "places_totales",
            "anonymat",
            "surveillants",
            "surveillants_noms",
            "nb_convoques",
            "nb_presents",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def get_surveillants_noms(self, obj):
        return [s.get_full_name() for s in obj.surveillants.all()]

    def get_nb_convoques(self, obj):
        if hasattr(obj, "nb_convoques_count"):
            return obj.nb_convoques_count
        return obj.convocations.count()

    def get_nb_presents(self, obj):
        if hasattr(obj, "nb_presents_count"):
            return obj.nb_presents_count
        return obj.convocations.filter(statut="present").count()


class ConvocationExamenSerializer(serializers.ModelSerializer):
    """Serializer pour les convocations."""

    etudiant_matricule = serializers.CharField(
        source="etudiant.matricule", read_only=True
    )
    etudiant_nom = serializers.CharField(
        source="etudiant.user.get_full_name", read_only=True
    )
    epreuve_ecue = serializers.CharField(source="epreuve.ecue.nom", read_only=True)
    epreuve_date = serializers.DateField(source="epreuve.date", read_only=True)
    statut_display = serializers.CharField(source="get_statut_display", read_only=True)

    class Meta:
        model = ConvocationExamen
        fields = [
            "id",
            "epreuve",
            "epreuve_ecue",
            "epreuve_date",
            "etudiant",
            "etudiant_matricule",
            "etudiant_nom",
            "numero_place",
            "salle",
            "statut",
            "statut_display",
            "notifie",
            "date_notification",
        ]
        read_only_fields = ["id"]
