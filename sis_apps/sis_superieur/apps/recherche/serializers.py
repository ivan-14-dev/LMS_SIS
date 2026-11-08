"""Strict command inputs and permission-aware research representations."""

import re
from decimal import Decimal

from apps.enseignants.models import EnseignantChercheur
from apps.etudiants.models import Etudiant
from apps.structure.models import Faculte
from django.db.models import Q
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied

from sis_common.exam_files import validate_exam_copy

from . import access
from .models import (
    Laboratoire,
    ProductionScientifique,
    ProjetRecherche,
    ResearchDelivery,
    ResearchMilestone,
    These,
)


class PositiveInteger(serializers.IntegerField):
    def to_internal_value(self, data):
        if type(data) is not int and not (isinstance(data, str) and re.fullmatch(r"[1-9][0-9]*", data)):
            self.fail("invalid")
        if int(data) < 1:
            self.fail("invalid")
        return super().to_internal_value(data)


class StrictInput:
    def to_internal_value(self, data):
        if not hasattr(data, "keys"):
            raise serializers.ValidationError({"non_field_errors": "Un objet est requis."})
        unknown = set(data) - set(self.fields)
        readonly = {key for key in data if key in self.fields and self.fields[key].read_only}
        if unknown or readonly:
            raise serializers.ValidationError({
                key: "Champ inconnu ou en lecture seule. Utilisez la commande dédiée."
                for key in unknown | readonly
            })
        return super().to_internal_value(data)


class VersionCommand(StrictInput, serializers.Serializer):
    version = PositiveInteger()


class MilestoneCommand(VersionCommand):
    titre = serializers.CharField(max_length=300)
    description = serializers.CharField(allow_blank=True, required=False, default="")
    echeance = serializers.DateField()


class DeliveryCommand(VersionCommand):
    jalon = PositiveInteger()
    fichier = serializers.FileField(validators=[validate_exam_copy])
    commentaire = serializers.CharField(allow_blank=True, max_length=10000, required=False, default="")


class AcceptMilestoneCommand(VersionCommand):
    jalon = PositiveInteger()


class DefendCommand(VersionCommand):
    date_soutenance = serializers.DateField()


def local_teachers(request):
    return EnseignantChercheur.objects.filter(
        user__etablissement_id=request.tenant.pk, user__is_active=True,
    ).filter(Q(laboratoire__isnull=True) | Q(laboratoire__in=access.local_laboratories(request)))


def local_students(request):
    return Etudiant.objects.filter(
        universite_id=request.tenant.pk, user__etablissement_id=request.tenant.pk,
        user__is_active=True, statut__in=access.ACTIVE_STUDENTS,
    )


def local_faculties(request):
    return Faculte.objects.filter(
        Q(doyen__isnull=True) | Q(doyen__etablissement_id=request.tenant.pk),
        universite_id=request.tenant.pk,
    )


def selectable_related(request, kind):
    user = access.current_research_user(request)
    if kind == "enseignants":
        queryset = local_teachers(request)
    elif kind == "etudiants":
        queryset = local_students(request)
    else:
        queryset = local_faculties(request)
    if user is None or access.constraints_for(user, access.MANAGE) is None:
        return queryset.none()
    if access.allowed(request, access.MANAGE):
        return queryset
    labs = access.managed_laboratories(request)
    projects = access.scoped_projects(request, user, access.MANAGE)
    if kind == "enseignants":
        return queryset.filter(
            Q(laboratoire__in=labs) | Q(projets_responsable__in=projects) | Q(projets_membre__in=projects),
        ).distinct()
    if kind == "etudiants":
        return queryset.filter(Q(these__laboratoire__in=labs) | Q(these__projet__in=projects)).distinct()
    return queryset.filter(Q(laboratoires__in=labs) | Q(laboratoires__projets__in=projects)).distinct()


class ResearchMetadata(StrictInput, serializers.ModelSerializer):
    version = PositiveInteger(required=False)

    @property
    def request(self):
        return self.context.get("request")

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if self.instance is None:
            if "version" in attrs:
                raise serializers.ValidationError({"version": "La version initiale est attribuée par le serveur."})
        elif "version" not in attrs:
            raise serializers.ValidationError({"version": "Ce champ est obligatoire."})
        return attrs

    def related_fields(self, **querysets):
        for field, queryset in querysets.items():
            if field in self.fields:
                target = self.fields[field]
                if isinstance(target, serializers.ManyRelatedField):
                    target = target.child_relation
                target.queryset = queryset

    def create(self, validated_data):
        validated_data.pop("version", None)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        validated_data.pop("version", None)
        return super().update(instance, validated_data)


class LaboratoireDetailSerializer(ResearchMetadata):
    type_display = serializers.CharField(source="get_type_display", read_only=True)
    faculte_nom = serializers.CharField(source="faculte.nom", read_only=True)
    directeur_nom = serializers.CharField(source="directeur.user.get_full_name", read_only=True)
    nb_projets = serializers.SerializerMethodField()
    nb_theses = serializers.SerializerMethodField()
    can_manage = serializers.SerializerMethodField()
    can_archiver = serializers.SerializerMethodField()

    class Meta:
        model = Laboratoire
        fields = [
            "id", "nom", "acronyme", "type", "type_display", "faculte", "faculte_nom", "directeur",
            "directeur_nom", "tutelle", "axes_recherche", "numero_rnsr", "created_at", "version", "archive",
            "nb_projets", "nb_theses", "can_manage", "can_archiver",
        ]
        read_only_fields = ["id", "created_at", "archive"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.request:
            self.related_fields(
                faculte=selectable_related(self.request, "facultes"),
                directeur=selectable_related(self.request, "enseignants"),
            )

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if not access.allowed(self.request, access.MANAGE, laboratoire=self.instance):
            raise PermissionDenied("Gestion de ce laboratoire non autorisée.")
        for field in ("tutelle", "axes_recherche"):
            if field in attrs and (
                not isinstance(attrs[field], list) or any(not isinstance(value, str) for value in attrs[field])
            ):
                raise serializers.ValidationError({field: "Une liste de textes est requise."})
        return attrs

    def get_nb_projets(self, obj):
        return access.visible_projects(self.request).filter(laboratoire=obj).count()

    def get_nb_theses(self, obj):
        return access.visible_theses(self.request).filter(laboratoire=obj).count()

    def get_can_manage(self, obj):
        return not obj.archive and access.allowed(self.request, access.MANAGE, laboratoire=obj)

    def get_can_archiver(self, obj):
        return self.get_can_manage(obj) and not obj.projets.filter(archive=False).exists()

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if not access.allowed(self.request, access.MANAGE, laboratoire=instance):
            # Reading a scoped child never grants the laboratory's other private metadata.
            keep = {"id", "nom", "acronyme", "version", "archive", "can_manage", "can_archiver", "nb_projets", "nb_theses"}
            data = {key: value for key, value in data.items() if key in keep}
        return data


class LaboratoireListSerializer(LaboratoireDetailSerializer):
    pass


class ResearchDeliverySerializer(serializers.ModelSerializer):
    url_telechargement = serializers.SerializerMethodField()

    class Meta:
        model = ResearchDelivery
        fields = ["id", "revision", "nom", "taille", "sha256", "commentaire", "created_at", "url_telechargement"]

    def get_url_telechargement(self, obj):
        return f"/api/v1/recherche/projets-recherche/{obj.jalon.projet_id}/livrables/{obj.pk}/fichier/"


class ResearchMilestoneSerializer(serializers.ModelSerializer):
    livrables = ResearchDeliverySerializer(many=True, read_only=True)

    class Meta:
        model = ResearchMilestone
        fields = ["id", "titre", "description", "echeance", "statut", "livrables"]


class ProjetRechercheDetailSerializer(ResearchMetadata):
    laboratoire_nom = serializers.CharField(source="laboratoire.acronyme", read_only=True)
    responsable_nom = serializers.CharField(source="responsable.user.get_full_name", read_only=True)
    statut_display = serializers.CharField(source="get_statut_display", read_only=True)
    membres_list = serializers.SerializerMethodField()
    can_manage = serializers.SerializerMethodField()
    can_read_academic = serializers.SerializerMethodField()
    can_contribute = serializers.SerializerMethodField()
    can_finance = serializers.SerializerMethodField()
    jalons = ResearchMilestoneSerializer(many=True, read_only=True)
    productions = serializers.SerializerMethodField()
    theses = serializers.SerializerMethodField()

    class Meta:
        model = ProjetRecherche
        fields = [
            "id", "titre", "acronyme", "description", "laboratoire", "laboratoire_nom", "responsable",
            "responsable_nom", "membres", "membres_list", "financeur", "reference", "budget",
            "date_debut", "date_fin", "statut", "statut_display", "created_at", "version", "archive",
            "can_manage", "can_read_academic", "can_contribute", "can_finance", "jalons", "productions", "theses",
        ]
        read_only_fields = ["id", "created_at", "statut", "archive"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.request:
            self.related_fields(
                laboratoire=access.local_laboratories(self.request),
                responsable=selectable_related(self.request, "enseignants"),
                membres=selectable_related(self.request, "enseignants"),
            )

    def validate(self, attrs):
        attrs = super().validate(attrs)
        lab = attrs.get("laboratoire", getattr(self.instance, "laboratoire", None))
        if lab is None or lab.archive:
            raise serializers.ValidationError({"laboratoire": "Un laboratoire actif est requis."})
        if self.instance is None:
            permitted = access.allowed(self.request, access.MANAGE, laboratoire=lab)
        else:
            permitted = access.allowed(self.request, access.MANAGE, projet=self.instance)
            if lab.pk != self.instance.laboratoire_id:
                raise serializers.ValidationError({"laboratoire": "Le rattachement d'un projet est immuable."})
        if not permitted:
            raise PermissionDenied("Gestion de ce projet non autorisée.")
        start = attrs.get("date_debut", getattr(self.instance, "date_debut", None))
        end = attrs.get("date_fin", getattr(self.instance, "date_fin", None))
        if start and end and end < start:
            raise serializers.ValidationError({"date_fin": "La fin doit suivre le début."})
        if attrs.get("budget", Decimal("0")) < 0:
            raise serializers.ValidationError({"budget": "Le budget ne peut pas être négatif."})
        if self.instance:
            if "date_debut" in attrs and self.instance.operations_financieres.filter(date_operation__lt=start).exists():
                raise serializers.ValidationError({"date_debut": "Le début doit précéder les opérations financières."})
            if self.instance.jalons.filter(Q(echeance__lt=start) | Q(echeance__gt=end)).exists():
                raise serializers.ValidationError({"date_fin": "Les dates doivent contenir tous les jalons."})
            if self.instance.theses.filter(
                Q(date_debut__lt=start) | Q(date_debut__gt=end) | Q(date_soutenance__gt=end),
            ).exists():
                raise serializers.ValidationError({"date_fin": "Les dates doivent contenir les encadrements."})
            if "membres" in attrs or "responsable" in attrs:
                responsible = attrs.get("responsable", self.instance.responsable)
                members = attrs.get("membres", self.instance.membres.all())
                ids = {responsible.pk, *(member.pk for member in members)}
                if self.instance.theses.exclude(directeur_id__in=ids).exists() or (
                    self.instance.theses.filter(co_directeur__isnull=False).exclude(co_directeur_id__in=ids).exists()
                ):
                    raise serializers.ValidationError({"membres": "Un encadrant doit rester chercheur du projet."})
        return attrs

    def get_membres_list(self, obj):
        return [{"id": member.pk, "nom": member.user.get_full_name()} for member in obj.membres.all()]

    def get_can_manage(self, obj):
        return not obj.archive and not obj.laboratoire.archive and access.allowed(self.request, access.MANAGE, projet=obj)

    def get_can_read_academic(self, obj):
        return access.can_read_academic(self.request, obj)

    def get_can_contribute(self, obj):
        return (
            not obj.archive and not obj.laboratoire.archive and obj.statut == "en_cours"
            and access.can_contribute(self.request, obj)
        )

    def get_can_finance(self, obj):
        return access.allowed(self.request, access.FINANCE, projet=obj)

    def get_productions(self, obj):
        return ProductionScientifiqueSerializer(
            access.visible_productions(self.request).filter(projet=obj), many=True, context=self.context,
        ).data

    def get_theses(self, obj):
        return TheseListSerializer(
            access.visible_theses(self.request).filter(projet=obj), many=True, context=self.context,
        ).data

    def to_representation(self, instance):
        if not access.can_read_academic(self.request, instance):
            keep = {
                "id", "titre", "acronyme", "laboratoire", "laboratoire_nom", "budget", "financeur",
                "date_debut", "date_fin", "statut", "statut_display", "version", "archive",
                "can_manage", "can_read_academic", "can_contribute", "can_finance",
            }
            return {
                name: self.fields[name].to_representation(self.fields[name].get_attribute(instance))
                for name in self.fields if name in keep
            }
        data = super().to_representation(instance)
        manage = data["can_manage"]
        for command, state in {
            "accepter": "propose", "demarrer": "accepte", "suspendre": "en_cours",
            "reprendre": "suspendu", "archiver": "termine",
        }.items():
            data[f"can_{command}"] = manage and instance.statut == state
        from .finance import project_has_open_commitments

        data["can_terminer"] = (
            manage and instance.statut == "en_cours"
            and not instance.jalons.exclude(statut="accepte").exists()
            and not project_has_open_commitments(instance)
        )
        data["can_archiver"] = data["can_archiver"] and not project_has_open_commitments(instance)
        data["can_add_jalon"] = manage and instance.statut in ("propose", "accepte", "en_cours")
        data["can_valider_jalon"] = (
            manage and instance.statut == "en_cours"
            and instance.jalons.filter(statut="soumis", livrables__isnull=False).exists()
        )
        return data


class ProjetRechercheListSerializer(ProjetRechercheDetailSerializer):
    class Meta(ProjetRechercheDetailSerializer.Meta):
        fields = [
            field for field in ProjetRechercheDetailSerializer.Meta.fields
            if field not in ("jalons", "productions", "theses")
        ]


class LinkedMetadata(ResearchMetadata):
    can_manage = serializers.SerializerMethodField()
    projet_version = serializers.IntegerField(source="projet.version", read_only=True, allow_null=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.request:
            self.related_fields(
                laboratoire=access.local_laboratories(self.request),
                projet=access.academic_projects(self.request),
            )

    def validate(self, attrs):
        attrs = super().validate(attrs)
        project = attrs.get("projet", getattr(self.instance, "projet", None))
        lab = attrs.get("laboratoire", getattr(self.instance, "laboratoire", None))
        if project is None and self.instance is None:
            raise serializers.ValidationError({"projet": "Un projet de recherche est obligatoire."})
        if self.instance and (
            ("projet" in attrs and getattr(project, "pk", None) != self.instance.projet_id)
            or ("laboratoire" in attrs and lab.pk != self.instance.laboratoire_id)
        ):
            raise serializers.ValidationError({"projet": "Le rattachement historique est immuable."})
        if lab is None or lab.archive or (project and project.archive):
            raise serializers.ValidationError({"laboratoire": "Le projet et le laboratoire doivent être actifs."})
        if project and project.laboratoire_id != lab.pk:
            raise serializers.ValidationError({"laboratoire": "Le laboratoire doit être celui du projet."})
        if not access.allowed(self.request, access.MANAGE, laboratoire=lab, projet=project):
            raise PermissionDenied("Gestion de ce dossier non autorisée.")
        return attrs

    def researchers(self, attrs):
        project = attrs.get("projet", getattr(self.instance, "projet", None))
        if project is None:
            return None
        return {project.responsable_id, *project.membres.values_list("pk", flat=True)}

    def get_can_manage(self, obj):
        return (
            not obj.archive and not obj.laboratoire.archive and (obj.projet is None or not obj.projet.archive)
            and access.allowed(self.request, access.MANAGE, laboratoire=obj.laboratoire, projet=obj.projet)
        )


class PublicationFileField(serializers.FileField):
    def to_representation(self, value):
        return f"/api/v1/recherche/productions-scientifiques/{value.instance.pk}/fichier/" if value else None


class ProductionScientifiqueSerializer(LinkedMetadata):
    type_display = serializers.CharField(source="get_type_display", read_only=True)
    laboratoire_nom = serializers.CharField(source="laboratoire.acronyme", read_only=True)
    projet_titre = serializers.CharField(source="projet.titre", read_only=True)
    auteurs_list = serializers.SerializerMethodField()
    fichier = PublicationFileField(required=False, allow_null=True, validators=[validate_exam_copy])

    class Meta:
        model = ProductionScientifique
        fields = [
            "id", "type", "type_display", "titre", "auteurs", "auteurs_list", "laboratoire", "laboratoire_nom",
            "projet", "projet_titre", "annee", "doi", "url_hal", "facteur_impact", "fichier", "created_at",
            "statut", "version", "archive", "can_manage", "projet_version",
        ]
        read_only_fields = ["id", "created_at", "statut", "archive"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.request:
            self.related_fields(auteurs=selectable_related(self.request, "enseignants"))

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if self.instance and self.instance.statut != "brouillon":
            raise serializers.ValidationError("Seul un brouillon peut être modifié.")
        authors = attrs.get("auteurs", self.instance.auteurs.all() if self.instance else [])
        if not authors:
            raise serializers.ValidationError({"auteurs": "Au moins un auteur enseignant est requis."})
        researchers = self.researchers(attrs)
        if researchers is not None and any(author.pk not in researchers for author in authors):
            raise serializers.ValidationError({"auteurs": "Les auteurs doivent être chercheurs du projet."})
        return attrs

    def get_auteurs_list(self, obj):
        return [{"id": author.pk, "nom": author.user.get_full_name()} for author in obj.auteurs.all()]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        for command, state in {
            "edit": "brouillon", "valider": "brouillon", "publier": "validee", "archiver": "publiee",
        }.items():
            data[f"can_{command}"] = data["can_manage"] and instance.statut == state
        if instance.projet_id is None:
            data["can_valider"] = data["can_publier"] = False
        elif data["can_valider"] or data["can_publier"]:
            researchers = {instance.projet.responsable_id, *instance.projet.membres.values_list("pk", flat=True)}
            valid_authors = instance.auteurs.exists() and not instance.auteurs.exclude(
                pk__in=researchers, user__is_active=True, user__etablissement_id=self.request.tenant.pk,
            ).exists()
            data["can_valider"] = data["can_valider"] and valid_authors
            data["can_publier"] = data["can_publier"] and valid_authors
        return data


class TheseDetailSerializer(LinkedMetadata):
    laboratoire_nom = serializers.CharField(source="laboratoire.acronyme", read_only=True)
    doctorant_nom = serializers.CharField(source="doctorant.user.get_full_name", read_only=True)
    directeur_nom = serializers.CharField(source="directeur.user.get_full_name", read_only=True)
    co_directeur_nom = serializers.CharField(source="co_directeur.user.get_full_name", read_only=True)
    statut_display = serializers.CharField(source="get_statut_display", read_only=True)

    class Meta:
        model = These
        fields = [
            "id", "titre", "resume", "mots_cles", "laboratoire", "laboratoire_nom", "projet",
            "doctorant", "doctorant_nom", "directeur", "directeur_nom", "co_directeur", "co_directeur_nom",
            "date_debut", "date_soutenance", "statut", "statut_display", "financement", "created_at",
            "version", "archive", "can_manage", "projet_version",
        ]
        read_only_fields = ["id", "created_at", "statut", "archive", "date_soutenance"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.request:
            self.related_fields(
                doctorant=selectable_related(self.request, "etudiants"),
                directeur=selectable_related(self.request, "enseignants"),
                co_directeur=selectable_related(self.request, "enseignants"),
            )

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if self.instance and self.instance.statut not in ("en_cours", "suspendue"):
            raise serializers.ValidationError("Un encadrement terminé ne peut plus être modifié.")
        director = attrs.get("directeur", getattr(self.instance, "directeur", None))
        co_director = attrs.get("co_directeur", getattr(self.instance, "co_directeur", None))
        student = attrs.get("doctorant", getattr(self.instance, "doctorant", None))
        if not local_students(self.request).filter(pk=getattr(student, "pk", None)).exists():
            raise serializers.ValidationError({"doctorant": "Un étudiant local actif est requis."})
        if self.instance and student.pk != self.instance.doctorant_id:
            raise serializers.ValidationError({"doctorant": "L'identité du doctorant est immuable."})
        if co_director and director and co_director.pk == director.pk:
            raise serializers.ValidationError({"co_directeur": "Les encadrants doivent être distincts."})
        researchers = self.researchers(attrs)
        if researchers is not None and any(
            teacher.pk not in researchers for teacher in (director, co_director) if teacher
        ):
            raise serializers.ValidationError({"directeur": "Les encadrants doivent être chercheurs du projet."})
        project = attrs.get("projet", getattr(self.instance, "projet", None))
        start = attrs.get("date_debut", getattr(self.instance, "date_debut", None))
        if project and start and not project.date_debut <= start <= project.date_fin:
            raise serializers.ValidationError({"date_debut": "Le début doit être dans la période du projet."})
        if "mots_cles" in attrs and (
            not isinstance(attrs["mots_cles"], list) or any(not isinstance(item, str) for item in attrs["mots_cles"])
        ):
            raise serializers.ValidationError({"mots_cles": "Une liste de textes est requise."})
        return attrs

    def to_representation(self, instance):
        data = super().to_representation(instance)
        for command, states in {
            "edit": ("en_cours", "suspendue"), "soutenir": ("en_cours",), "suspendre": ("en_cours",),
            "reprendre": ("suspendue",), "abandonner": ("en_cours", "suspendue"),
            "archiver": ("soutenue", "abandonnee"),
        }.items():
            data[f"can_{command}"] = data["can_manage"] and instance.statut in states
        return data


class TheseListSerializer(TheseDetailSerializer):
    pass
