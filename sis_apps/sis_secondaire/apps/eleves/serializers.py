"""Serializers for eleves (SIS Secondaire)."""

from rest_framework import serializers

from .models import Eleve, EleveTuteur, Inscription, Tuteur


class EleveListSerializer(serializers.ModelSerializer):
    """Serializer léger pour les listes d'élèves."""

    full_name = serializers.CharField(source="user.get_full_name", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)
    classe_nom = serializers.CharField(source="classe_actuelle.nom", read_only=True)
    niveau_nom = serializers.CharField(
        source="classe_actuelle.niveau.nom", read_only=True
    )
    statut_display = serializers.CharField(source="get_statut_display", read_only=True)

    class Meta:
        model = Eleve
        fields = [
            "id",
            "matricule",
            "full_name",
            "email",
            "sexe",
            "classe_actuelle",
            "classe_nom",
            "niveau_nom",
            "statut",
            "statut_display",
            "bourse",
            "transport",
            "cantine",
        ]


class EleveDetailSerializer(serializers.ModelSerializer):
    """Serializer complet pour le détail d'un élève."""

    full_name = serializers.CharField(source="user.get_full_name", read_only=True)
    first_name = serializers.CharField(source="user.first_name", read_only=True)
    last_name = serializers.CharField(source="user.last_name", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)
    classe_nom = serializers.CharField(source="classe_actuelle.nom", read_only=True)
    statut_display = serializers.CharField(source="get_statut_display", read_only=True)
    sexe_display = serializers.CharField(source="get_sexe_display", read_only=True)

    class Meta:
        model = Eleve
        fields = [
            "id",
            "user",
            "etablissement",
            "matricule",
            "ine",
            "full_name",
            "first_name",
            "last_name",
            "email",
            "date_naissance",
            "lieu_naissance",
            "sexe",
            "sexe_display",
            "nationalite",
            "adresse",
            "code_postal",
            "ville",
            "classe_actuelle",
            "classe_nom",
            "statut",
            "statut_display",
            "date_inscription",
            "motif_sortie",
            "photo",
            "qr_code",
            "bourse",
            "transport",
            "cantine",
            "interne",
            "allergies",
            "contact_urgence_nom",
            "contact_urgence_tel",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "matricule", "qr_code", "created_at", "updated_at"]


class EleveCreateSerializer(serializers.ModelSerializer):
    """Serializer pour la création d'un élève."""

    # Données utilisateur imbriquées
    username = serializers.CharField(write_only=True)
    email = serializers.EmailField(write_only=True)
    first_name = serializers.CharField(write_only=True)
    last_name = serializers.CharField(write_only=True)
    password = serializers.CharField(write_only=True)

    class Meta:
        model = Eleve
        fields = [
            "username",
            "email",
            "first_name",
            "last_name",
            "password",
            "etablissement",
            "date_naissance",
            "lieu_naissance",
            "sexe",
            "nationalite",
            "adresse",
            "code_postal",
            "ville",
            "classe_actuelle",
            "bourse",
            "transport",
            "cantine",
            "interne",
        ]

    def create(self, validated_data):
        import uuid

        from apps.utilisateurs.models import Utilisateur
        from django.utils import timezone

        # Extraire les données utilisateur
        user_data = {
            "username": validated_data.pop("username"),
            "email": validated_data.pop("email"),
            "first_name": validated_data.pop("first_name"),
            "last_name": validated_data.pop("last_name"),
            "role": "eleve",
        }
        password = validated_data.pop("password")

        # Créer l'utilisateur
        user = Utilisateur(**user_data)
        user.set_password(password)
        user.save()

        # Générer un matricule unique
        matricule = f"EL{timezone.now().year}{uuid.uuid4().hex[:6].upper()}"

        # Créer l'élève
        eleve = Eleve.objects.create(
            user=user,
            matricule=matricule,
            date_inscription=timezone.now().date(),
            **validated_data,
        )
        return eleve


class InscriptionSerializer(serializers.ModelSerializer):
    """Serializer pour les inscriptions."""

    eleve_matricule = serializers.CharField(source="eleve.matricule", read_only=True)
    eleve_nom = serializers.CharField(source="eleve.user.get_full_name", read_only=True)
    classe_nom = serializers.CharField(source="classe.nom", read_only=True)
    annee_libelle = serializers.CharField(
        source="annee_scolaire.libelle", read_only=True
    )
    statut_display = serializers.CharField(source="get_statut_display", read_only=True)

    class Meta:
        model = Inscription
        fields = [
            "id",
            "eleve",
            "eleve_matricule",
            "eleve_nom",
            "classe",
            "classe_nom",
            "annee_scolaire",
            "annee_libelle",
            "date_inscription",
            "statut",
            "statut_display",
            "motif",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class TuteurSerializer(serializers.ModelSerializer):
    """Serializer pour les tuteurs."""

    lien_display = serializers.CharField(
        source="get_lien_parente_display", read_only=True
    )

    class Meta:
        model = Tuteur
        fields = [
            "id",
            "etablissement",
            "user",
            "nom",
            "prenom",
            "lien_parente",
            "lien_display",
            "telephone",
            "telephone_2",
            "email",
            "profession",
            "adresse",
            "autorise_sortie",
            "autorise_photos",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class EleveTuteurSerializer(serializers.ModelSerializer):
    """Serializer pour les liens élève-tuteur."""

    tuteur_nom = serializers.CharField(source="tuteur.__str__", read_only=True)
    eleve_nom = serializers.CharField(source="eleve.user.get_full_name", read_only=True)

    class Meta:
        model = EleveTuteur
        fields = [
            "id",
            "eleve",
            "eleve_nom",
            "tuteur",
            "tuteur_nom",
            "est_payeur",
            "est_contact_urgence",
            "autorise_acces_portail",
        ]
