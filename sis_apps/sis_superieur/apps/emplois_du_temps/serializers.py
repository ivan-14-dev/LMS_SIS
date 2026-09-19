"""Serializers for emplois du temps (SIS Supérieur)."""

from rest_framework import serializers

from .models import Batiment, ConflitHoraire, CreneauCours, CreneauHoraire, Reservation, Salle


# === Batiment Serializers ===
class BatimentListSerializer(serializers.ModelSerializer):
    """Liste des bâtiments."""

    nb_salles = serializers.IntegerField(read_only=True)

    class Meta:
        model = Batiment
        fields = ["id", "code", "nom", "nb_etages", "accessibilite_pmr", "nb_salles"]


class BatimentDetailSerializer(serializers.ModelSerializer):
    """Détail d'un bâtiment."""

    class Meta:
        model = Batiment
        fields = "__all__"


# === Salle Serializers ===
class SalleListSerializer(serializers.ModelSerializer):
    """Liste légère des salles."""

    batiment_code = serializers.CharField(source="batiment.code", read_only=True)
    type_display = serializers.CharField(source="get_type_display", read_only=True)

    class Meta:
        model = Salle
        fields = [
            "id",
            "code",
            "nom",
            "batiment_code",
            "type",
            "type_display",
            "capacite",
            "disponible",
        ]


class SalleDetailSerializer(serializers.ModelSerializer):
    """Détail complet d'une salle."""

    batiment = BatimentListSerializer(read_only=True)
    type_display = serializers.CharField(source="get_type_display", read_only=True)
    departement_nom = serializers.CharField(
        source="departement_gestionnaire.nom", read_only=True
    )

    class Meta:
        model = Salle
        fields = "__all__"


class SalleCreateUpdateSerializer(serializers.ModelSerializer):
    """Création/modification d'une salle."""

    class Meta:
        model = Salle
        fields = [
            "batiment",
            "nom",
            "code",
            "type",
            "capacite",
            "etage",
            "equipements",
            "accessibilite_pmr",
            "disponible",
            "departement_gestionnaire",
        ]


# === CreneauHoraire Serializers ===
class CreneauHoraireSerializer(serializers.ModelSerializer):
    """Créneau horaire type."""

    display = serializers.CharField(source="__str__", read_only=True)

    class Meta:
        model = CreneauHoraire
        fields = "__all__"


# === CreneauCours Serializers ===
class CreneauCoursListSerializer(serializers.ModelSerializer):
    """Liste légère des créneaux de cours."""

    jour_display = serializers.CharField(source="get_jour_display", read_only=True)
    ecue_code = serializers.CharField(source="ecue.code", read_only=True)
    ecue_nom = serializers.CharField(source="ecue.nom", read_only=True)
    enseignant_nom = serializers.CharField(source="enseignant.__str__", read_only=True)
    salle_code = serializers.CharField(source="salle.code", read_only=True)
    horaire = serializers.CharField(source="creneau_horaire.__str__", read_only=True)
    type_display = serializers.CharField(
        source="get_type_cours_display", read_only=True
    )

    class Meta:
        model = CreneauCours
        fields = [
            "id",
            "jour",
            "jour_display",
            "horaire",
            "ecue_code",
            "ecue_nom",
            "enseignant_nom",
            "salle_code",
            "type_cours",
            "type_display",
            "groupe",
        ]


class CreneauCoursDetailSerializer(serializers.ModelSerializer):
    """Détail complet d'un créneau."""

    jour_display = serializers.CharField(source="get_jour_display", read_only=True)
    type_display = serializers.CharField(
        source="get_type_cours_display", read_only=True
    )
    ecue = serializers.SerializerMethodField()
    enseignant = serializers.SerializerMethodField()
    salle = SalleListSerializer(read_only=True)
    creneau_horaire = CreneauHoraireSerializer(read_only=True)
    formation_nom = serializers.CharField(source="formation.nom", read_only=True)
    semestre_str = serializers.CharField(source="semestre.__str__", read_only=True)

    class Meta:
        model = CreneauCours
        fields = "__all__"

    def get_ecue(self, obj):
        return {
            "id": obj.ecue.id,
            "code": obj.ecue.code,
            "nom": obj.ecue.nom,
            "ue": str(obj.ecue.ue) if obj.ecue.ue else None,
        }

    def get_enseignant(self, obj):
        if not obj.enseignant:
            return None
        return {
            "id": obj.enseignant.id,
            "nom_complet": str(obj.enseignant),
            "grade": obj.enseignant.grade,
        }


class CreneauCoursCreateUpdateSerializer(serializers.ModelSerializer):
    """Création/modification d'un créneau de cours."""

    class Meta:
        model = CreneauCours
        fields = [
            "semestre",
            "formation",
            "ecue",
            "enseignant",
            "salle",
            "jour",
            "creneau_horaire",
            "type_cours",
            "groupe",
            "semaine_debut",
            "semaine_fin",
            "frequence",
            "semaines_paires",
            "commentaire",
        ]

    def validate(self, attrs):
        # Vérification des conflits de salle
        salle = attrs.get("salle")
        jour = attrs.get("jour")
        creneau = attrs.get("creneau_horaire")
        semestre = attrs.get("semestre")
        instance = self.instance

        if salle and creneau:
            conflits = CreneauCours.objects.filter(
                salle=salle, jour=jour, creneau_horaire=creneau, semestre=semestre
            )
            if instance:
                conflits = conflits.exclude(pk=instance.pk)
            if conflits.exists():
                raise serializers.ValidationError(
                    {"salle": "Cette salle est déjà occupée sur ce créneau."}
                )

        # Vérification des conflits d'enseignant
        enseignant = attrs.get("enseignant")
        if enseignant and creneau:
            conflits = CreneauCours.objects.filter(
                enseignant=enseignant,
                jour=jour,
                creneau_horaire=creneau,
                semestre=semestre,
            )
            if instance:
                conflits = conflits.exclude(pk=instance.pk)
            if conflits.exists():
                raise serializers.ValidationError(
                    {"enseignant": "Cet enseignant a déjà un cours sur ce créneau."}
                )

        return attrs


# === Reservation Serializers ===
class ReservationListSerializer(serializers.ModelSerializer):
    """Liste des réservations."""

    salle_code = serializers.CharField(source="salle.code", read_only=True)
    demandeur_nom = serializers.CharField(source="demandeur.__str__", read_only=True)
    statut_display = serializers.CharField(source="get_statut_display", read_only=True)
    motif_display = serializers.CharField(source="get_motif_display", read_only=True)

    class Meta:
        model = Reservation
        fields = [
            "id",
            "salle_code",
            "demandeur_nom",
            "date",
            "heure_debut",
            "heure_fin",
            "motif",
            "motif_display",
            "statut",
            "statut_display",
        ]


class ReservationDetailSerializer(serializers.ModelSerializer):
    """Détail d'une réservation."""

    salle = SalleDetailSerializer(read_only=True)
    demandeur_nom = serializers.CharField(source="demandeur.__str__", read_only=True)
    valide_par_nom = serializers.CharField(source="valide_par.__str__", read_only=True)
    statut_display = serializers.CharField(source="get_statut_display", read_only=True)
    motif_display = serializers.CharField(source="get_motif_display", read_only=True)

    class Meta:
        model = Reservation
        fields = "__all__"


class ReservationCreateSerializer(serializers.ModelSerializer):
    """Création d'une réservation."""

    class Meta:
        model = Reservation
        fields = [
            "salle",
            "date",
            "heure_debut",
            "heure_fin",
            "motif",
            "description",
            "nb_personnes",
        ]

    def validate(self, attrs):
        salle = attrs.get("salle")
        date = attrs.get("date")
        heure_debut = attrs.get("heure_debut")
        heure_fin = attrs.get("heure_fin")

        if heure_debut >= heure_fin:
            raise serializers.ValidationError(
                {"heure_fin": "L'heure de fin doit être après l'heure de début."}
            )

        # Vérifier si la salle n'est pas déjà réservée
        conflits = Reservation.objects.filter(
            salle=salle, date=date, statut="confirmee"
        ).filter(heure_debut__lt=heure_fin, heure_fin__gt=heure_debut)
        if conflits.exists():
            raise serializers.ValidationError(
                {"salle": "Cette salle est déjà réservée sur ce créneau."}
            )

        return attrs


class ValidationReservationSerializer(serializers.Serializer):
    """Validation/refus d'une réservation."""

    action = serializers.ChoiceField(choices=["confirmer", "refuser"])
    motif_refus = serializers.CharField(required=False, allow_blank=True)


# === ConflitHoraire Serializers ===
class ConflitHoraireSerializer(serializers.ModelSerializer):
    """Conflit horaire."""

    type_display = serializers.CharField(
        source="get_type_conflit_display", read_only=True
    )
    creneau_1_str = serializers.CharField(source="creneau_1.__str__", read_only=True)
    creneau_2_str = serializers.CharField(source="creneau_2.__str__", read_only=True)

    class Meta:
        model = ConflitHoraire
        fields = "__all__"


# === Emploi du temps ===
class EmploiDuTempsSerializer(serializers.Serializer):
    """Emploi du temps d'une formation/groupe."""

    formation_id = serializers.IntegerField()
    formation_nom = serializers.CharField()
    semestre = serializers.CharField()
    groupe = serializers.CharField(required=False)
    creneaux = serializers.ListField(child=serializers.DictField())


class DisponibiliteSalleSerializer(serializers.Serializer):
    """Disponibilité d'une salle sur une période."""

    salle = SalleListSerializer()
    date_debut = serializers.DateField()
    date_fin = serializers.DateField()
    creneaux_libres = serializers.ListField(child=serializers.DictField())
    creneaux_occupes = serializers.ListField(child=serializers.DictField())
