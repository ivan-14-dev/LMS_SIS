"""Serializers for memoires (SIS Supérieur)."""

from rest_framework import serializers

from .models import JuryMemoire, Memoire, SujetMemoire


class SujetMemoireListSerializer(serializers.ModelSerializer):
    """Serializer léger pour les listes de sujets."""

    formation_nom = serializers.CharField(source="formation.nom", read_only=True)
    encadreur_nom = serializers.CharField(
        source="encadreur.user.get_full_name", read_only=True
    )
    statut_display = serializers.CharField(source="get_statut_display", read_only=True)
    nb_candidats = serializers.SerializerMethodField()

    class Meta:
        model = SujetMemoire
        fields = [
            "id",
            "formation",
            "formation_nom",
            "titre",
            "encadreur_nom",
            "statut",
            "statut_display",
            "nb_etudiants_max",
            "nb_candidats",
            "date_limite_candidature",
        ]

    def get_nb_candidats(self, obj):
        return obj.memoires.count()


class SujetMemoireDetailSerializer(serializers.ModelSerializer):
    """Serializer complet pour un sujet de mémoire."""

    formation_nom = serializers.CharField(source="formation.nom", read_only=True)
    encadreur_nom = serializers.CharField(
        source="encadreur.user.get_full_name", read_only=True
    )
    co_encadreur_nom = serializers.CharField(
        source="co_encadreur.user.get_full_name", read_only=True
    )
    laboratoire_nom = serializers.CharField(source="laboratoire.nom", read_only=True)
    statut_display = serializers.CharField(source="get_statut_display", read_only=True)

    class Meta:
        model = SujetMemoire
        fields = [
            "id",
            "formation",
            "formation_nom",
            "annee_universitaire",
            "titre",
            "description",
            "mots_cles",
            "encadreur",
            "encadreur_nom",
            "co_encadreur",
            "co_encadreur_nom",
            "laboratoire",
            "laboratoire_nom",
            "nb_etudiants_max",
            "prerequis",
            "statut",
            "statut_display",
            "date_publication",
            "date_limite_candidature",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class MemoireListSerializer(serializers.ModelSerializer):
    """Serializer léger pour les listes de mémoires."""

    etudiant_matricule = serializers.CharField(
        source="etudiant.matricule", read_only=True
    )
    etudiant_nom = serializers.CharField(
        source="etudiant.user.get_full_name", read_only=True
    )
    sujet_titre = serializers.CharField(source="sujet.titre", read_only=True)
    encadreur_nom = serializers.CharField(
        source="sujet.encadreur.user.get_full_name", read_only=True
    )
    statut_display = serializers.CharField(source="get_statut_display", read_only=True)

    class Meta:
        model = Memoire
        fields = [
            "id",
            "etudiant",
            "etudiant_matricule",
            "etudiant_nom",
            "sujet",
            "sujet_titre",
            "encadreur_nom",
            "statut",
            "statut_display",
            "date_depot",
        ]


class MemoireDetailSerializer(serializers.ModelSerializer):
    """Serializer complet pour un mémoire."""

    etudiant_matricule = serializers.CharField(
        source="etudiant.matricule", read_only=True
    )
    etudiant_nom = serializers.CharField(
        source="etudiant.user.get_full_name", read_only=True
    )
    sujet_titre = serializers.CharField(source="sujet.titre", read_only=True)
    statut_display = serializers.CharField(source="get_statut_display", read_only=True)

    class Meta:
        model = Memoire
        fields = [
            "id",
            "sujet",
            "sujet_titre",
            "etudiant",
            "etudiant_matricule",
            "etudiant_nom",
            "fichier",
            "resume",
            "abstract",
            "date_depot",
            "rapport_similarite",
            "statut",
            "statut_display",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class JuryMemoireSerializer(serializers.ModelSerializer):
    """Serializer pour les jurys de mémoire."""

    memoire_titre = serializers.CharField(source="memoire.sujet.titre", read_only=True)
    etudiant_nom = serializers.CharField(
        source="memoire.etudiant.user.get_full_name", read_only=True
    )
    president_nom = serializers.CharField(
        source="president.get_full_name", read_only=True
    )
    rapporteurs_list = serializers.SerializerMethodField()

    class Meta:
        model = JuryMemoire
        fields = [
            "id",
            "memoire",
            "memoire_titre",
            "etudiant_nom",
            "president",
            "president_nom",
            "rapporteurs",
            "rapporteurs_list",
            "autres_membres",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def get_rapporteurs_list(self, obj):
        return [{"id": r.id, "nom": r.get_full_name()} for r in obj.rapporteurs.all()]
