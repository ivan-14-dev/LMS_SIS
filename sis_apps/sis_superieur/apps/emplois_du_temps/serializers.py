"""Serializers for emplois du temps (SIS Supérieur)."""

from django.db import connection
from django.db.models import Q
from rest_framework import serializers

from sis_common.academic_lifecycle import ensure_academic_open

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
    departement_nom = serializers.CharField(source="departement_gestionnaire.nom", read_only=True)

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

    def validate(self, attrs):
        start = attrs.get("heure_debut", getattr(self.instance, "heure_debut", None))
        end = attrs.get("heure_fin", getattr(self.instance, "heure_fin", None))
        if start and end and start >= end:
            raise serializers.ValidationError({"heure_fin": "La fin doit suivre le début."})
        return attrs


# === CreneauCours Serializers ===
class CreneauCoursListSerializer(serializers.ModelSerializer):
    """Liste légère des créneaux de cours."""

    jour_display = serializers.CharField(source="get_jour_display", read_only=True)
    ecue_code = serializers.CharField(source="ecue.code", read_only=True)
    ecue_nom = serializers.CharField(source="ecue.nom", read_only=True)
    enseignant_nom = serializers.SerializerMethodField()
    salle_code = serializers.CharField(source="salle.code", read_only=True)
    horaire = serializers.CharField(source="creneau_horaire.__str__", read_only=True)
    type_display = serializers.CharField(source="get_type_cours_display", read_only=True)

    def get_enseignant_nom(self, obj):
        return str(obj.enseignant) if obj.enseignant_id else ""

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
    type_display = serializers.CharField(source="get_type_cours_display", read_only=True)
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
        instance = self.instance

        def value(field):
            return attrs.get(field, getattr(instance, field, None))

        salle, jour, creneau, semestre = (value(field) for field in ("salle", "jour", "creneau_horaire", "semestre"))
        ensure_academic_open(instance, attrs, ("semestre.annee_universitaire", "semestre"))
        ecue, formation = value("ecue"), value("formation")
        if ecue and (ecue.ue.maquette.formation_id != formation.pk or ecue.ue.semestre_id != semestre.pk):
            raise serializers.ValidationError({"ecue": "L'ECUE doit appartenir à cette formation et à ce semestre."})
        semaine_debut = attrs.get("semaine_debut", getattr(instance, "semaine_debut", 1))
        semaine_fin = attrs.get("semaine_fin", getattr(instance, "semaine_fin", 52))
        if semaine_debut > semaine_fin:
            raise serializers.ValidationError({"semaine_fin": "La dernière semaine doit suivre la première."})

        if salle and creneau:
            conflits = CreneauCours.objects.filter(
                salle=salle,
                jour=jour,
                semestre=semestre,
                creneau_horaire__heure_debut__lt=creneau.heure_fin,
                creneau_horaire__heure_fin__gt=creneau.heure_debut,
            )
            if instance:
                conflits = conflits.exclude(pk=instance.pk)
            if conflits.exists():
                raise serializers.ValidationError({"salle": "Cette salle est déjà occupée sur ce créneau."})

        # Vérification des conflits d'enseignant
        enseignant = value("enseignant")
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
                raise serializers.ValidationError({"enseignant": "Cet enseignant a déjà un cours sur ce créneau."})

        if formation and creneau:
            groupe = value("groupe")
            conflits = CreneauCours.objects.filter(
                formation=formation,
                semestre=semestre,
                jour=jour,
                creneau_horaire__heure_debut__lt=creneau.heure_fin,
                creneau_horaire__heure_fin__gt=creneau.heure_debut,
                semaine_debut__lte=semaine_fin,
                semaine_fin__gte=semaine_debut,
            )
            # Un cours sans groupe concerne toute la formation.
            if groupe:
                conflits = conflits.filter(Q(groupe=groupe) | Q(groupe=""))
            semaines_paires = value("semaines_paires")
            if semaines_paires is not None:
                conflits = conflits.filter(Q(semaines_paires=semaines_paires) | Q(semaines_paires__isnull=True))
            if instance:
                conflits = conflits.exclude(pk=instance.pk)
            if conflits.exists():
                raise serializers.ValidationError({"groupe": "Ce groupe a déjà un cours sur ce créneau."})

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
        salle = attrs.get("salle", getattr(self.instance, "salle", None))
        date = attrs.get("date", getattr(self.instance, "date", None))
        heure_debut = attrs.get("heure_debut", getattr(self.instance, "heure_debut", None))
        heure_fin = attrs.get("heure_fin", getattr(self.instance, "heure_fin", None))
        if connection.in_atomic_block:
            salle = Salle.objects.select_for_update().get(pk=salle.pk)
        if not salle.disponible:
            raise serializers.ValidationError({"salle": "Cette salle n'est pas disponible."})

        if heure_debut >= heure_fin:
            raise serializers.ValidationError({"heure_fin": "L'heure de fin doit être après l'heure de début."})

        # Vérifier si la salle n'est pas déjà réservée
        conflits = Reservation.objects.filter(salle=salle, date=date, statut="confirmee").filter(
            heure_debut__lt=heure_fin, heure_fin__gt=heure_debut
        )
        if self.instance:
            conflits = conflits.exclude(pk=self.instance.pk)
        if conflits.exists():
            raise serializers.ValidationError({"salle": "Cette salle est déjà réservée sur ce créneau."})

        return attrs


class ValidationReservationSerializer(serializers.Serializer):
    """Validation/refus d'une réservation."""

    action = serializers.ChoiceField(choices=["confirmer", "refuser"])
    motif_refus = serializers.CharField(required=False, allow_blank=True)


# === ConflitHoraire Serializers ===
class ConflitHoraireSerializer(serializers.ModelSerializer):
    """Conflit horaire."""

    type_display = serializers.CharField(source="get_type_conflit_display", read_only=True)
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
