"""Serializers for examens (SIS Supérieur)."""

from rest_framework import serializers
from sis_common.exam_files import hash_uploaded_file
from sis_common.submission_windows import get_submission_window_alert, get_submission_window_status

from .models import (
    AffectationCorrection,
    AuditCopieExamen,
    ConvocationExamen,
    CopieExamen,
    CorrectionCopie,
    EpreuveExamen,
    ResultatExamen,
    SessionExamen,
)


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
    soumission_statut = serializers.SerializerMethodField()
    soumission_alerte = serializers.SerializerMethodField()

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
            "debut_soumission",
            "fin_soumission",
            "lieu",
            "places_totales",
            "bareme",
            "nb_convoques",
            "nombre_corrections",
            "soumission_statut",
            "soumission_alerte",
        ]

    def get_nb_convoques(self, obj):
        if hasattr(obj, "nb_convoques_count"):
            return obj.nb_convoques_count
        return obj.convocations.count()

    def get_soumission_statut(self, obj):
        return get_submission_window_status(obj)

    def get_soumission_alerte(self, obj):
        request = self.context.get("request")
        configuration = getattr(getattr(request, "tenant", None), "configuration_academique", {})
        return get_submission_window_alert(obj, configuration, "exam")


class EpreuveExamenDetailSerializer(serializers.ModelSerializer):
    """Serializer complet pour une épreuve."""

    ecue_code = serializers.CharField(source="ecue.code", read_only=True)
    ecue_nom = serializers.CharField(source="ecue.nom", read_only=True)
    session_numero = serializers.IntegerField(source="session.numero", read_only=True)
    surveillants_noms = serializers.SerializerMethodField()
    nb_convoques = serializers.SerializerMethodField()
    nb_presents = serializers.SerializerMethodField()
    soumission_statut = serializers.SerializerMethodField()
    soumission_alerte = serializers.SerializerMethodField()

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
            "debut_soumission",
            "fin_soumission",
            "lieu",
            "places_totales",
            "bareme",
            "anonymat",
            "nombre_corrections",
            "surveillants",
            "surveillants_noms",
            "nb_convoques",
            "nb_presents",
            "soumission_statut",
            "soumission_alerte",
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

    def get_soumission_statut(self, obj):
        return get_submission_window_status(obj)

    def get_soumission_alerte(self, obj):
        request = self.context.get("request")
        configuration = getattr(getattr(request, "tenant", None), "configuration_academique", {})
        return get_submission_window_alert(obj, configuration, "exam")

    def validate(self, attrs):
        debut_soumission = attrs.get(
            "debut_soumission", getattr(self.instance, "debut_soumission", None)
        )
        fin_soumission = attrs.get("fin_soumission", getattr(self.instance, "fin_soumission", None))
        if debut_soumission and fin_soumission and fin_soumission < debut_soumission:
            raise serializers.ValidationError(
                {"fin_soumission": "La fin de soumission doit être postérieure au début."}
            )
        return attrs


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


class ResultatExamenSerializer(serializers.ModelSerializer):
    """Serializer pour les résultats d'examen."""

    session_numero = serializers.IntegerField(source="epreuve.session.numero", read_only=True)
    session_type = serializers.CharField(source="epreuve.session.get_type_display", read_only=True)
    ecue_code = serializers.CharField(source="epreuve.ecue.code", read_only=True)
    ecue_nom = serializers.CharField(source="epreuve.ecue.nom", read_only=True)
    etudiant_matricule = serializers.CharField(source="etudiant.matricule", read_only=True)
    etudiant_nom = serializers.CharField(source="etudiant.user.get_full_name", read_only=True)
    statut_display = serializers.CharField(source="get_statut_display", read_only=True)
    type_resultat_display = serializers.CharField(
        source="get_type_resultat_display", read_only=True
    )

    class Meta:
        model = ResultatExamen
        fields = [
            "id",
            "epreuve",
            "session_numero",
            "session_type",
            "ecue_code",
            "ecue_nom",
            "etudiant",
            "etudiant_matricule",
            "etudiant_nom",
            "note",
            "appreciation",
            "numero_anonyme",
            "statut",
            "statut_display",
            "type_resultat",
            "type_resultat_display",
            "admis",
            "mention",
            "saisi_par",
            "saisi_le",
            "verifie_par",
            "verifie_le",
            "valide_par",
            "valide_le",
            "publie_par",
            "publie_le",
            "reouvert_par",
            "reouvert_le",
            "cloture_par",
            "cloture_le",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
            "numero_anonyme",
            "admis",
            "mention",
            "saisi_par",
            "saisi_le",
            "verifie_par",
            "verifie_le",
            "valide_par",
            "valide_le",
            "publie_par",
            "publie_le",
            "reouvert_par",
            "reouvert_le",
            "cloture_par",
            "cloture_le",
        ]


class CopieExamenSerializer(serializers.ModelSerializer):
    epreuve = serializers.IntegerField(source="convocation.epreuve_id", read_only=True)
    convocation = serializers.PrimaryKeyRelatedField(
        queryset=ConvocationExamen.objects.all(), write_only=True
    )

    class Meta:
        model = CopieExamen
        fields = [
            "id",
            "convocation",
            "epreuve",
            "numero_anonyme",
            "fichier",
            "empreinte_sha256",
            "taille_octets",
            "statut",
            "note_finale",
            "deposee_le",
        ]
        read_only_fields = [
            "id",
            "numero_anonyme",
            "empreinte_sha256",
            "taille_octets",
            "statut",
            "note_finale",
            "deposee_le",
        ]
        extra_kwargs = {"fichier": {"write_only": True}}

    def validate_convocation(self, value):
        if not value.epreuve.anonymat:
            raise serializers.ValidationError(
                "L'anonymat doit être activé avant le dépôt des copies."
            )
        if value.statut != "present":
            raise serializers.ValidationError(
                "Une copie ne peut être déposée que pour un candidat présent."
            )
        if hasattr(value, "copie"):
            raise serializers.ValidationError(
                "Une copie existe déjà pour cette convocation."
            )
        return value

    def create(self, validated_data):
        uploaded_file = validated_data["fichier"]
        return CopieExamen.objects.create(
            **validated_data,
            empreinte_sha256=hash_uploaded_file(uploaded_file),
            taille_octets=uploaded_file.size,
            deposee_par=self.context["request"].user,
        )


class AffectationCorrectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = AffectationCorrection
        fields = [
            "id",
            "copie",
            "correcteur",
            "ordre",
            "statut",
            "affectee_le",
        ]
        read_only_fields = ["id", "statut", "affectee_le"]

    def validate(self, attrs):
        copie = attrs["copie"]
        correcteur = attrs["correcteur"]
        if (
            correcteur.role not in ("enseignant", "chercheur")
            and not correcteur.is_staff
        ) or not correcteur.is_active:
            raise serializers.ValidationError(
                {"correcteur": "Le correcteur doit être un enseignant actif."}
            )
        if correcteur.pk == copie.convocation.etudiant.user_id:
            raise serializers.ValidationError(
                {"correcteur": "Un candidat ne peut pas corriger sa propre copie."}
            )
        if copie.statut not in ("deposee", "affectee"):
            raise serializers.ValidationError(
                {"copie": "Cette copie n'accepte plus de nouvelles affectations."}
            )
        if not 1 <= attrs["ordre"] <= copie.epreuve.nombre_corrections:
            raise serializers.ValidationError(
                {"ordre": "Cette épreuve ne prévoit pas ce niveau de correction."}
            )
        if copie.affectations.count() >= copie.epreuve.nombre_corrections:
            raise serializers.ValidationError(
                {"copie": "Toutes les corrections prévues sont déjà affectées."}
            )
        return attrs

    def create(self, validated_data):
        return AffectationCorrection.objects.create(
            **validated_data, affectee_par=self.context["request"].user
        )


class CorrectionCopieSerializer(serializers.ModelSerializer):
    numero_anonyme = serializers.CharField(
        source="affectation.copie.numero_anonyme", read_only=True
    )

    class Meta:
        model = CorrectionCopie
        fields = [
            "id",
            "affectation",
            "numero_anonyme",
            "note",
            "appreciation",
            "soumise_le",
        ]
        read_only_fields = ["id", "numero_anonyme", "soumise_le"]

    def validate(self, attrs):
        affectation = attrs["affectation"]
        if affectation.correcteur != self.context["request"].user:
            raise serializers.ValidationError(
                {"affectation": "Cette copie ne vous est pas affectée."}
            )
        if affectation.statut != "assignee" or affectation.copie.statut not in (
            "affectee",
            "correction",
        ):
            raise serializers.ValidationError(
                {"affectation": "Cette affectation n'accepte plus de correction."}
            )
        bareme = getattr(affectation.copie.epreuve, "bareme", 20)
        if attrs["note"] > bareme or attrs["note"] < 0:
            raise serializers.ValidationError(
                {"note": "La note doit respecter le barème de l'épreuve."}
            )
        return attrs


class AuditCopieExamenSerializer(serializers.ModelSerializer):
    acteur = serializers.CharField(source="acteur.get_full_name", read_only=True)

    class Meta:
        model = AuditCopieExamen
        fields = ["id", "copie", "acteur", "action", "details", "cree_le"]
        read_only_fields = fields
