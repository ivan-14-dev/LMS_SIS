"""Serializers for examens (SIS Secondaire)."""

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
    """Serializer pour les sessions d'examen."""

    type_display = serializers.CharField(source="get_type_display", read_only=True)
    annee_libelle = serializers.CharField(
        source="annee_scolaire.libelle", read_only=True
    )
    nb_epreuves = serializers.SerializerMethodField()

    class Meta:
        model = SessionExamen
        fields = [
            "id",
            "annee_scolaire",
            "annee_libelle",
            "type",
            "type_display",
            "nom",
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
    """Serializer léger pour les épreuves."""

    session_nom = serializers.CharField(source="session.nom", read_only=True)
    matiere_nom = serializers.CharField(source="matiere.nom", read_only=True)
    salle_nom = serializers.CharField(source="salle_principale.nom", read_only=True)
    soumission_statut = serializers.SerializerMethodField()
    soumission_alerte = serializers.SerializerMethodField()

    class Meta:
        model = EpreuveExamen
        fields = [
            "id",
            "session",
            "session_nom",
            "matiere",
            "matiere_nom",
            "date",
            "heure_debut",
            "duree_minutes",
            "debut_soumission",
            "fin_soumission",
            "salle_principale",
            "salle_nom",
            "bareme",
            "coefficient",
            "anonymat",
            "nombre_corrections",
            "soumission_statut",
            "soumission_alerte",
        ]

    def get_soumission_statut(self, obj):
        return get_submission_window_status(obj)

    def get_soumission_alerte(self, obj):
        request = self.context.get("request")
        configuration = getattr(getattr(request, "tenant", None), "configuration_academique", {})
        return get_submission_window_alert(obj, configuration, "exam")


class EpreuveExamenDetailSerializer(serializers.ModelSerializer):
    """Serializer complet pour une épreuve."""

    session_nom = serializers.CharField(source="session.nom", read_only=True)
    matiere_nom = serializers.CharField(source="matiere.nom", read_only=True)
    classes_list = serializers.SerializerMethodField()
    surveillants_list = serializers.SerializerMethodField()
    soumission_statut = serializers.SerializerMethodField()
    soumission_alerte = serializers.SerializerMethodField()

    class Meta:
        model = EpreuveExamen
        fields = [
            "id",
            "session",
            "session_nom",
            "matiere",
            "matiere_nom",
            "classes",
            "classes_list",
            "date",
            "heure_debut",
            "duree_minutes",
            "debut_soumission",
            "fin_soumission",
            "salle_principale",
            "bareme",
            "coefficient",
            "surveillants",
            "surveillants_list",
            "anonymat",
            "nombre_corrections",
            "soumission_statut",
            "soumission_alerte",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def get_classes_list(self, obj):
        return [{"id": c.id, "nom": c.nom} for c in obj.classes.all()]

    def get_surveillants_list(self, obj):
        return [{"id": s.id, "nom": s.get_full_name()} for s in obj.surveillants.all()]

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

    epreuve_info = serializers.SerializerMethodField()
    eleve_matricule = serializers.CharField(source="eleve.matricule", read_only=True)
    eleve_nom = serializers.CharField(source="eleve.user.get_full_name", read_only=True)
    statut_display = serializers.CharField(source="get_statut_display", read_only=True)

    class Meta:
        model = ConvocationExamen
        fields = [
            "id",
            "epreuve",
            "epreuve_info",
            "eleve",
            "eleve_matricule",
            "eleve_nom",
            "numero_place",
            "salle",
            "statut",
            "statut_display",
            "notifie_parents",
            "date_notification",
        ]
        read_only_fields = ["id"]

    def get_epreuve_info(self, obj):
        return {
            "matiere": obj.epreuve.matiere.nom,
            "date": obj.epreuve.date,
            "heure": str(obj.epreuve.heure_debut),
        }


class ResultatExamenSerializer(serializers.ModelSerializer):
    """Serializer pour les résultats."""

    epreuve_matiere = serializers.CharField(
        source="epreuve.matiere.nom", read_only=True
    )
    eleve_matricule = serializers.CharField(source="eleve.matricule", read_only=True)
    eleve_nom = serializers.CharField(source="eleve.user.get_full_name", read_only=True)
    statut_display = serializers.CharField(source="get_statut_display", read_only=True)
    type_resultat_display = serializers.CharField(
        source="get_type_resultat_display", read_only=True
    )

    class Meta:
        model = ResultatExamen
        fields = [
            "id",
            "epreuve",
            "epreuve_matiere",
            "eleve",
            "eleve_matricule",
            "eleve_nom",
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
            correcteur.role != "enseignant" and not correcteur.is_staff
        ) or not correcteur.is_active:
            raise serializers.ValidationError(
                {"correcteur": "Le correcteur doit être un enseignant actif."}
            )
        if correcteur.pk == copie.convocation.eleve.user_id:
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
        if attrs["note"] > affectation.copie.epreuve.bareme or attrs["note"] < 0:
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
