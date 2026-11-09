"""Real tenant/enrolment fixtures shared by the two practical API suites."""

import json
from copy import deepcopy
from datetime import UTC, date, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from apps.core.models import ModuleConfiguration
from apps.integration.tests.tenant_test_case import TenantAPITestCase
from django.apps import apps
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.files.uploadedfile import SimpleUploadedFile

from sis_common.exam_files import PrivateExamStorage
from sis_common.institutional_profiles import institutional_profile_schema

BASE = "/api/v1/stages/pratique/"
MANAGE = "stages.gerer_suivi_pratique"
CONSULT = "stages.consulter_suivi_pratique"
ENTER = "stages.saisir_heures_pratiques"
VALIDATE = "stages.valider_heures_pratiques"
EVALUATE = "stages.evaluer_competences_pratiques"
NOW = datetime(2026, 11, 8, 12, tzinfo=UTC)
PDF = b"%PDF-1.4\npractical evidence\n%%EOF\n"
MODELS = (
    "ProgrammePratique",
    "RevisionProgrammePratique",
    "DossierPratique",
    "HeurePratique",
    "DecisionHeurePratique",
    "EvaluationCompetencePratique",
    "AuditPratique",
)


def practical_model(name):
    return apps.get_model("stages", name)


class PracticalFixture(TenantAPITestCase):
    def setUp(self):
        self.secondary = settings.SIS_VARIANT == "secondaire"
        clock = patch("django.utils.timezone.now", return_value=NOW)
        self.clock = clock.start()
        self.addCleanup(clock.stop)
        self.tenant.fuseau_horaire = "Europe/Paris"
        self.tenant.save(update_fields=["fuseau_horaire"])
        ModuleConfiguration.objects.update_or_create(
            etablissement=self.tenant, defaults={"enabled": {"sis.practical_training": True}}
        )
        self.manager = self.user("practical-manager", "personnel_administratif")
        self.learner_user = self.user("practical-learner", "eleve" if self.secondary else "etudiant")
        self.tutor = self.user("practical-tutor", "enseignant")
        self.partner = self.user("practical-partner", "personnel_administratif")
        self.outsider = self.user("practical-outsider", "enseignant", is_staff=True)
        self.grant(self.manager, MANAGE)
        self.grant(self.learner_user, CONSULT, ENTER)
        self.grant(self.tutor, CONSULT, ENTER, VALIDATE, EVALUATE)
        self.grant(self.partner, CONSULT, ENTER, VALIDATE, EVALUATE)
        self.make_curriculum()
        self.company = self.create(
            "stages.Entreprise" if self.secondary else "entreprises.Entreprise",
            raison_sociale="Atelier pratique",
            adresse="1 rue des Ateliers",
            code_postal="75000",
            ville="Paris",
            telephone="0100000000",
        )
        if not self.secondary:
            self.teacher = self.create("enseignants.EnseignantChercheur", user=self.tutor, specialite="Pratique")
            self.contact = self.create(
                "entreprises.ContactEntreprise",
                entreprise=self.company,
                user=self.partner,
                nom="Partenaire",
                prenom="Test",
                email="partner@example.test",
                telephone="0100000000",
            )
        self.convention = self.make_convention()
        temporary = TemporaryDirectory(prefix="sis-practical-tests-")
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name)
        self.storage = PrivateExamStorage(location=self.folder)
        for name in ("HeurePratique", "EvaluationCompetencePratique"):
            field = practical_model(name)._meta.get_field("fichier")
            self.addCleanup(setattr, field, "storage", field.storage)
            field.storage = self.storage

    def create(self, name, **values):
        return apps.get_model(name).objects.create(**values)

    def user(self, username, role="personnel_administratif", **values):
        return get_user_model().objects.create_user(username=username, role=role, etablissement=self.tenant, **values)

    def grant(self, user, *names):
        for name in names:
            label, codename = name.split(".")
            user.user_permissions.add(Permission.objects.get(content_type__app_label=label, codename=codename))

    def login(self, user):
        self.client.force_authenticate(user)

    def make_curriculum(self):
        year_values = {"date_debut": date(2026, 1, 1), "date_fin": date(2026, 12, 31)}
        year_model = apps.get_model(
            "etablissement.AnneeScolaire" if self.secondary else "etablissement.AnneeUniversitaire"
        )
        ownership = {"etablissement": self.tenant} if self.secondary else {"universite": self.tenant}
        # etablissement is shared: its years survive a FastTenantTestCase tenant flush.
        self.year, _ = year_model.objects.get_or_create(
            libelle="Pratique 2026",
            defaults=year_values,
            **ownership,
        )
        assert self.year.date_debut == year_values["date_debut"]
        assert self.year.date_fin == year_values["date_fin"]
        profile = "secondary" if self.secondary else "higher_education"
        offering = deepcopy(
            next(row["template"] for row in institutional_profile_schema()["profiles"] if row["code"] == profile)
        )
        offering["assessment"] = {"mode": "numeric", "minimum": 0, "maximum": 20, "pass_mark": 10}
        learner_values = {
            "user": self.learner_user,
            "matricule": "PR40",
            "date_naissance": date(2008, 1, 1),
            "lieu_naissance": "Paris",
            "sexe": "F",
            "statut": "inscrit",
        }
        if self.secondary:
            level, _ = apps.get_model("etablissement.Niveau").objects.get_or_create(
                etablissement=self.tenant,
                code="PR40",
                defaults={"libelle": "Pratique"},
            )
            self.curriculum = self.create(
                "classes.Classe",
                etablissement=self.tenant,
                niveau=level,
                annee_scolaire=self.year,
                nom="Pratique",
                offre_configuration=offering,
            )
            self.learner = self.create(
                "eleves.Eleve", etablissement=self.tenant, date_inscription=self.year.date_debut, **learner_values
            )
            self.registration = self.create(
                "eleves.Inscription",
                eleve=self.learner,
                classe=self.curriculum,
                annee_scolaire=self.year,
                date_inscription=self.year.date_debut,
                statut="validee",
            )
        else:
            faculty = self.create("structure.Faculte", universite=self.tenant, code="PR40", nom="Pratique")
            department = self.create("structure.Departement", faculte=faculty, code="PR40", nom="Pratique")
            self.curriculum = self.create(
                "formations.Formation",
                departement=department,
                code="PR40",
                nom="Pratique",
                type="licence",
                offre_configuration=offering,
            )
            self.learner = self.create(
                "etudiants.Etudiant",
                universite=self.tenant,
                adresse="1 rue Élève",
                code_postal="75000",
                ville="Paris",
                telephone="0100000001",
                **learner_values,
            )
            self.registration = self.create(
                "etudiants.InscriptionAdministrative",
                etudiant=self.learner,
                formation=self.curriculum,
                annee_universitaire=self.year,
                date_inscription=self.year.date_debut,
                statut="validee",
            )

    def make_convention(self, **changes):
        values = {
            "entreprise": self.company,
            "date_debut": self.year.date_debut,
            "date_fin": self.year.date_fin,
            "missions": "Observer, réaliser et vérifier une installation.",
            "statut": "complete",
            "date_signature_complete": datetime(2026, 1, 1, tzinfo=UTC),
            "pdf_path": "legacy/private-convention.pdf",
        }
        if self.secondary:
            values.update(
                eleve=self.learner,
                maitre_stage_etablissement=self.tutor,
                duree_heures=999,
                tuteur_entreprise="Texte libre sans droit",
                telephone_tuteur="0100000000",
                email_tuteur="legacy@example.test",
            )
        else:
            offer = self.create(
                "stages.OffreStage",
                formation=self.curriculum,
                entreprise=self.company,
                titre="Stage pratique",
                type="application",
                description="Pratique",
                duree_mois=12,
                date_debut=self.year.date_debut,
                date_fin=self.year.date_fin,
                date_limite_candidature=self.year.date_debut,
                lieu="Paris",
            )
            values.update(
                etudiant=self.learner, offre=offer, maitre_stage=self.contact, tuteur_pedagogique=self.teacher
            )
        return self.create("stages.ConventionStage", **{**values, **changes})

    def programme_payload(self, **changes):
        return {
            "version": 0,
            "curriculum": self.curriculum.pk,
            "code": "pratique",
            "titre": "Pratique professionnelle",
            "minutes_requises": 120,
            "competences": [{"code": "securite", "label": "Travailler en sécurité"}],
            **changes,
        }

    def create_programme(self, **changes):
        self.login(self.manager)
        response = self.client.post(f"{BASE}programmes/", self.programme_payload(**changes), format="json")
        assert response.status_code == 201, response.data
        self.programme = response.data["programme"]
        response = self.client.post(
            f"{BASE}programmes/{self.programme['id']}/publier/",
            {"version": self.programme["version"]},
            format="json",
        )
        assert response.status_code == 200, response.data
        self.programme = response.data["programme"]
        return self.programme

    def opening_payload(self, convention=None):
        self.login(self.manager)
        convention = convention or self.convention
        revision = self.programme["revision_publiee"]["numero"]
        response = self.client.get(f"{BASE}programmes/{self.programme['id']}/conventions/", {"revision": revision})
        assert response.status_code == 200, response.data
        candidate = next(row for row in response.data["results"] if row["id"] == convention.pk)
        payload = {
            "version": 0,
            "programme": self.programme["id"],
            "programme_version": self.programme["version"],
            "revision": revision,
            "convention": convention.pk,
            "convention_empreinte": candidate["empreinte"],
        }
        if self.secondary:
            payload["partenaire_utilisateur"] = self.partner.pk
        return payload

    def open_dossier(self, convention=None):
        response = self.client.post(f"{BASE}dossiers/", self.opening_payload(convention), format="json")
        assert response.status_code == 201, response.data
        self.dossier = response.data["dossier"]
        return self.dossier

    def prepare(self):
        self.create_programme()
        return self.open_dossier()

    def url(self, tail=""):
        return f"{BASE}dossiers/{self.dossier['id']}/{tail}"

    def command(self, tail, user=None, **values):
        self.login(user or self.manager)
        response = self.client.post(self.url(tail), {"version": self.dossier["version"], **values}, format="json")
        if response.status_code < 300:
            self.dossier.update(response.data.get("dossier", {}))
            self.dossier["version"] = response.data["version"]
        return response

    def hour_payload(self, **changes):
        return {
            "version": self.dossier["version"],
            "date": "2026-11-07",
            "heure_debut": "09:00",
            "heure_fin": "11:00",
            "pause_minutes": 0,
            "activite": "Installation observée",
            **changes,
        }

    def record(self, user=None, **changes):
        response = self.command("heures/", user or self.learner_user, **self.hour_payload(**changes))
        assert response.status_code == 201, response.data
        return response.data["heure"]

    def assessment(self, **changes):
        return self.command(
            "competences/securite/evaluer/",
            self.tutor,
            **{
                "acquise": True,
                "contexte_professionnel": "Protection contrôlée sur le poste.",
                "date_observation": "2026-11-07",
                **changes,
            },
        )

    def report(self):
        self.login(self.manager)
        response = self.client.get(self.url("rapport/"))
        assert response.status_code == 200, response.data
        return response.data

    def complete(self):
        hour = self.record()
        for action, user in (("soumettre", self.learner_user), ("valider", self.tutor)):
            response = self.command(f"heures/{hour['id']}/{action}/", user)
            assert response.status_code == 200, response.data
        response = self.assessment()
        assert response.status_code == 201, response.data

    def upload(self, tail="heures/", user=None, payload=None, content=PDF, name="preuve.pdf"):
        self.login(user or self.learner_user)
        response = self.client.post(
            self.url(tail),
            {
                "payload": json.dumps(payload if payload is not None else self.hour_payload()),
                "fichier": SimpleUploadedFile(name, content, content_type="application/pdf"),
            },
            format="multipart",
        )
        if response.status_code < 300:
            self.dossier["version"] = response.data["version"]
        return response

    def state(self):
        return {
            "rows": {name: list(practical_model(name).objects.order_by("pk").values()) for name in MODELS},
            "files": {
                str(path.relative_to(self.folder)): path.read_bytes()
                for path in self.folder.rglob("*")
                if path.is_file()
            },
        }

    def assert_error(self, response, status, code=None):
        assert response.status_code == status, getattr(response, "data", response.status_code)
        assert set(response.data) == {"detail", "code", "errors", "current_version", "criteres_non_satisfaits"}
        if code:
            assert response.data["code"] == code, response.data
        if code != "version_perimee":
            assert response.data["current_version"] is None
