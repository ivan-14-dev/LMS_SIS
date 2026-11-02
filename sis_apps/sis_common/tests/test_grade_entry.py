from types import SimpleNamespace
from unittest.mock import patch

import pytest
from apps.integration.tests.tenant_test_case import TenantAPITestCase
from apps.utilisateurs.models import Utilisateur
from django.apps import apps
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone
from django_tenants.utils import schema_context

from sis_common.institutional_profiles import institutional_profile_schema
from sis_common.learning_offerings import offering_grade_result


@pytest.mark.parametrize("answer", [True, False, None])
def test_partial_competency_answers_require_presence_but_unanswered_absence_is_allowed(answer):
    offering = next(
        item["template"] for item in institutional_profile_schema()["profiles"] if item["code"] == "primary"
    )
    offering["assessment"]["criteria"].append({"code": "writing", "label": "Écriture"})
    evaluation = SimpleNamespace(offre_configuration=offering)
    result = {"criteria": {"competence_1": answer}}
    assert offering_grade_result(evaluation, None, result, "presente")["status"] == "incomplete"
    if answer is None:
        assert offering_grade_result(evaluation, None, result, "absente")["status"] == "incomplete"
    else:
        with pytest.raises(ValidationError, match="Présentée"):
            offering_grade_result(evaluation, None, result, "absente")


class GradeEntryWorkflowTest(TenantAPITestCase):
    def create(self, model, **values):
        return apps.get_model(model).objects.create(**values)

    def setUp(self):
        self.secondary = settings.SIS_VARIANT == "secondaire"
        self.today = timezone.localdate()
        self.admin = Utilisateur.objects.create_superuser("grades-admin", role="super_admin", etablissement=self.tenant)
        self.teacher = Utilisateur.objects.create_user("grades-teacher", role="enseignant", etablissement=self.tenant)
        self.client.force_authenticate(self.admin)
        self.year_values = {
            "libelle": str(self.today.year),
            "date_debut": self.today.replace(month=1, day=1),
            "date_fin": self.today.replace(month=12, day=31),
        }
        self.year_model = "etablissement.AnneeScolaire" if self.secondary else "etablissement.AnneeUniversitaire"
        self.owner_field = "etablissement" if self.secondary else "universite"
        self.year = self.create(self.year_model, **{self.owner_field: self.tenant}, **self.year_values)
        self.period_values = {
            "type": "trimestre" if self.secondary else "impair",
            "numero": 1,
            "date_debut": self.year.date_debut,
            "date_fin": self.year.date_fin,
        }
        self.period_model = "etablissement.Periode" if self.secondary else "etablissement.Semestre"
        self.year_field = "annee_scolaire" if self.secondary else "annee_universitaire"
        self.period = self.create(self.period_model, **{self.year_field: self.year}, **self.period_values)
        self.payload = {"titre": "Contrôle continu", "date": self.today.isoformat(), "bareme": "20", "coefficient": "1"}
        if self.secondary:
            level = self.create("etablissement.Niveau", etablissement=self.tenant, code="6e", libelle="Sixième")
            self.classe = self.create(
                "classes.Classe", etablissement=self.tenant, annee_scolaire=self.year, niveau=level, nom="6A"
            )
            self.subject = self.create("classes.Matiere", etablissement=self.tenant, code="MAT", nom="Mathématiques")
            self.author = self.create(
                "enseignants.Personnel", user=self.teacher, matricule="ENS-01", date_embauche=self.today
            )
            self.create("classes.ProgrammeMatiere", classe=self.classe, matiere=self.subject)
            self.payload.update(classe=self.classe.pk, matiere=self.subject.pk, periode=self.period.pk, type="ds")
        else:
            self.formation = self.create("formations.Formation", code="F1", nom="Licence", type="licence")
            maquette = self.create(
                "formations.MaquetteFormation", formation=self.formation, annee_universitaire=self.year
            )
            ue = self.create(
                "ue_ecue.UE", maquette=maquette, semestre=self.period, code="UE1", nom="UE", credits_ects=6
            )
            self.subject = self.create("ue_ecue.ECUE", ue=ue, code="EC1", nom="ECUE", credits_ects=6)
            self.author = self.teacher
            self.payload.update(ecue=self.subject.pk, semestre=self.period.pk, modalite="cc")
        self.payload["enseignant"] = self.author.pk
        self.learners = []
        for index in range(3):
            user = Utilisateur.objects.create_user(
                f"grade-learner-{index}",
                first_name="Test",
                last_name=f"Learner {index}",
                role="eleve" if self.secondary else "etudiant",
                etablissement=self.tenant,
            )
            values = {
                self.owner_field: self.tenant,
                "user": user,
                "matricule": f"GRADE-{index}",
                "date_naissance": "2005-01-01",
                "lieu_naissance": "Test",
                "sexe": "F",
            }
            if self.secondary:
                values.update(date_inscription=self.today, classe_actuelle=self.classe if index < 2 else None)
            learner = self.create("eleves.Eleve" if self.secondary else "etudiants.Etudiant", **values)
            self.learners.append(learner)
            if not self.secondary and index < 2:
                enrollment = self.create(
                    "etudiants.InscriptionPedagogique",
                    inscription_admin=self.enroll(learner),
                    semestre=self.period,
                    statut="validee",
                )
                enrollment.ues.add(self.subject.ue)
        self.base = "/api/v1/notes/evaluations/"
        response = self.client.post(self.base, self.payload, format="json")
        assert response.status_code == 201, response.data
        self.evaluation = apps.get_model("notes.Evaluation").objects.get(pk=response.data["id"])
        self.url = f"{self.base}{self.evaluation.pk}/"
        self.note_model = apps.get_model("notes.Note")
        self.learner_field = "eleve_id" if self.secondary else "etudiant_id"

    def enroll(self, learner):
        return self.create(
            "etudiants.InscriptionAdministrative",
            etudiant=learner,
            annee_universitaire=self.year,
            formation=self.formation,
            date_inscription=self.today,
            statut="validee",
        )

    def row(self, learner, value="14", **extra):
        return {self.learner_field: learner.pk, "valeur": value, **extra}

    def save_grades(self, rows):
        return self.client.post(f"{self.url}saisir_notes/", rows, format="json")

    def bind_offering(self, profile):
        offering = next(
            item["template"] for item in institutional_profile_schema()["profiles"] if item["code"] == profile
        )
        if offering["assessment"]["mode"] == "numeric":
            offering["assessment"].update(minimum=5, maximum=100, pass_mark=75)
        self.tenant.configuration_academique["learning_offerings"] = [offering]
        self.tenant.save(update_fields=["configuration_academique"])
        parent = self.classe if self.secondary else self.formation
        self.parent_url = (
            f"/api/v1/classes/classes/{parent.pk}/" if self.secondary else f"/api/v1/formations/formations/{parent.pk}/"
        )
        response = self.client.patch(self.parent_url, {"offre_code": offering["code"]}, format="json")
        assert response.status_code == 200, response.data
        assert response.data["offre_configuration"] == offering
        response = self.client.post(self.base, self.payload, format="json")
        assert response.status_code == 201, response.data
        self.evaluation = apps.get_model("notes.Evaluation").objects.get(pk=response.data["id"])
        self.url = f"{self.base}{self.evaluation.pk}/"
        return offering

    def test_numeric_offer_is_inherited_and_snapshot_survives_catalogue_edits(self):
        legacy = self.evaluation
        offering = self.bind_offering("secondary")
        legacy.refresh_from_db()
        assert legacy.offre_configuration == {}
        assert legacy.bareme == 20
        assert self.evaluation.bareme == 100
        assert self.evaluation.offre_configuration == offering
        assert self.save_grades([self.row(self.learners[0], "4")]).status_code == 400
        response = self.save_grades([self.row(self.learners[0], "75")])
        assert response.status_code == 200, response.data
        self.tenant.configuration_academique["learning_offerings"][0]["assessment"]["pass_mark"] = 90
        self.tenant.save(update_fields=["configuration_academique"])
        note = self.client.get(f"{self.url}notes/").data[0]
        assert note["resultat_offre"]["status"] == "passed"
        assert note["valeur"] == "75.00"
        assert self.client.patch(self.url, {"bareme": 20}, format="json").status_code == 400
        self.evaluation.refresh_from_db()
        assert self.evaluation.bareme == 100
        assert self.evaluation.offre_configuration["assessment"]["pass_mark"] == 75

    def test_new_enrollment_inherits_offer_without_rewriting_existing_records(self):
        offering = self.bind_offering("vocational")
        if self.secondary:
            response = self.client.post(
                "/api/v1/eleves/inscriptions/",
                {
                    "eleve": self.learners[2].pk,
                    "classe": self.classe.pk,
                    "annee_scolaire": self.year.pk,
                    "date_inscription": self.today.isoformat(),
                },
                format="json",
            )
        else:
            response = self.client.post(
                "/api/v1/inscriptions/",
                {
                    "etudiant": self.learners[2].pk,
                    "formation": self.formation.pk,
                    "annee_universitaire": self.year.pk,
                    "date_inscription": self.today.isoformat(),
                },
                format="json",
            )
            previous = apps.get_model("etudiants.InscriptionAdministrative").objects.get(etudiant=self.learners[0])
            assert previous.offre_configuration == {}
        assert response.status_code == 201, response.data
        assert response.data["offre_configuration"] == offering
        assert response.data["offre_configuration"]["credits"] is None
        if self.secondary:
            enrollment_id = response.data["id"]
            self.client.force_authenticate(self.learners[0].user)
            assert self.client.get("/api/v1/eleves/inscriptions/").data["count"] == 0
            assert self.client.get(f"/api/v1/eleves/inscriptions/{enrollment_id}/").status_code == 404
            assert self.client.post(f"/api/v1/eleves/inscriptions/{enrollment_id}/valider/").status_code == 403

    def test_competency_results_are_persisted_without_fabricated_numeric_grades(self):
        self.bind_offering("vocational")
        first, second = self.learners[:2]
        response = self.save_grades(
            [
                self.row(first, None, resultat={"criteria": {"competence_1": True}}),
                self.row(second, None, resultat={"criteria": {"competence_1": None}}),
            ]
        )
        assert response.status_code == 200, response.data
        notes = self.client.get(f"{self.url}notes/").data
        assert [note["valeur"] for note in notes] == [None, None]
        assert [note["resultat_offre"]["status"] for note in notes] == ["passed", "incomplete"]
        response = self.save_grades([self.row(first, None, resultat={"criteria": {"competence_1": False}})])
        assert response.status_code == 200, response.data
        assert self.client.get(f"{self.url}notes/").data[0]["resultat_offre"]["status"] == "failed"
        notes_count = self.note_model.objects.count()
        assert self.client.get(f"{self.url}modele_import_notes/").status_code == 400
        assert self.note_model.objects.count() == notes_count

    def test_invalid_typed_results_and_numeric_substitutes_are_rejected_atomically(self):
        self.bind_offering("primary")
        valid = self.row(self.learners[0], None, resultat={"criteria": {"competence_1": True}})
        invalid_results = [
            self.row(self.learners[1], "20", resultat={"criteria": {"competence_1": True}}),
            self.row(self.learners[1], None, resultat={"criteria": {"unknown": True}}),
            self.row(self.learners[1], None, resultat={"criteria": {"competence_1": "true"}}),
            self.row(self.learners[1], None, statut="absente", resultat={"criteria": {"competence_1": True}}),
        ]
        for invalid in invalid_results:
            response = self.save_grades([valid, invalid])
            assert response.status_code == 400, response.data
            assert not self.evaluation.notes.exists()

    def test_explicit_pass_fail_and_direct_note_updates_use_the_same_policy(self):
        self.bind_offering("custom")
        response = self.save_grades([self.row(self.learners[0], None, resultat={"passed": False})])
        assert response.status_code == 200, response.data
        note = self.client.get(f"{self.url}notes/").data[0]
        assert note["resultat_offre"]["status"] == "failed"
        url = f"/api/v1/notes/notes/{note['id']}/"
        response = self.client.patch(url, {"resultat": {"passed": "false"}}, format="json")
        assert response.status_code == 400, response.data
        response = self.client.patch(url, {"resultat": {"passed": True}}, format="json")
        assert response.status_code == 200, response.data
        assert response.data["resultat_offre"]["status"] == "passed"
        self.client.force_authenticate(self.learners[0].user)
        assert self.client.patch(url, {"resultat": {"passed": False}}, format="json").status_code == 403

    def test_binding_rejects_unknown_offers_and_ignores_forged_rule_snapshots(self):
        offering = self.bind_offering("higher_education")
        response = self.client.patch(self.parent_url, {"offre_code": "other-institution"}, format="json")
        assert response.status_code == 400, response.data
        response = self.client.patch(
            self.url, {"offre_configuration": {**offering, "profile": "forged"}}, format="json"
        )
        assert response.status_code == 200, response.data
        assert response.data["offre_configuration"] == offering
        self.client.force_authenticate(self.teacher)
        response = self.client.get("/api/v1/etablissement/learning-offerings/")
        assert response.status_code == 200, response.data
        assert response.data == [offering]
        assert self.client.get("/api/v1/etablissement/current/").status_code == 403

    def test_roster_pages_match_eligible_learners_and_grades_preserve_zero_and_absence(self):
        response = self.client.get(f"{self.url}apprenants/", {"page_size": 1, "page": 2})
        assert response.status_code == 200, response.data
        assert response.data["count"] == 2
        assert response.data["results"] == [
            {"id": self.learners[1].pk, "matricule": "GRADE-1", "nom": "Test Learner 1"}
        ]
        response = self.save_grades(
            [
                self.row(self.learners[0], "0"),
                self.row(self.learners[1], None, statut="absente"),
            ]
        )
        assert response.status_code == 200, response.data
        assert response.data["notes_creees"] == 2
        assert [note["valeur"] for note in self.client.get(f"{self.url}notes/").data] == ["0.00", None]
        response = self.save_grades([self.row(self.learners[0], "15", appreciation="Corrigé")])
        assert response.status_code == 200, response.data
        assert response.data["notes_modifiees"] == 1
        notes = self.client.get(f"{self.url}notes/").data
        assert notes[0]["valeur"] == "15.00"
        assert notes[0]["appreciation"] == "Corrigé"
        assert notes[1]["valeur"] is None
        assert notes[1]["statut"] == "absente"

    def test_invalid_batch_never_writes_partial_grades(self):
        first, second, outsider = self.learners
        cases = [
            [],
            [self.row(first), self.row(second, "-1")],
            [self.row(first), self.row(second, "21")],
            [self.row(first), self.row(outsider)],
            [self.row(first), self.row(first, "12")],
        ]
        for rows in cases:
            with self.subTest(rows=rows):
                response = self.save_grades(rows)
                assert response.status_code == 400, response.data
                assert self.note_model.objects.count() == 0

    def test_storage_failure_rolls_back_already_written_rows(self):
        original = self.note_model.objects.update_or_create
        calls = []

        def write(**kwargs):
            calls.append(kwargs)
            if len(calls) == 2:
                raise RuntimeError("Simulated storage failure")
            return original(**kwargs)

        with patch.object(self.note_model.objects, "update_or_create", side_effect=write):
            with pytest.raises(RuntimeError, match="Simulated storage failure"):
                self.save_grades([self.row(self.learners[0]), self.row(self.learners[1])])
        assert self.note_model.objects.count() == 0

    def test_teacher_ownership_and_student_permissions_are_enforced(self):
        other = Utilisateur.objects.create_user("other-grader", role="enseignant", etablissement=self.tenant)
        self.client.force_authenticate(other)
        assert self.client.get(f"{self.url}apprenants/").status_code == 404
        assert self.save_grades([self.row(self.learners[0])]).status_code == 404
        response = self.client.post(self.base, self.payload, format="json")
        assert response.status_code == 400, response.data
        self.client.force_authenticate(self.learners[0].user)
        assert self.client.get(f"{self.url}apprenants/").status_code == 404
        assert self.save_grades([self.row(self.learners[0])]).status_code == 403
        self.client.force_authenticate(self.teacher)
        assert self.client.get(f"{self.url}apprenants/").status_code == 200
        assert self.save_grades([self.row(self.learners[0])]).status_code == 200

    def test_foreign_period_and_invalid_scale_are_rejected(self):
        foreign = type(self.tenant)(schema_name="foreign_grades")
        self.setup_tenant(foreign)
        foreign.auto_create_schema = False
        with schema_context("public"):
            foreign.save()
        year = self.create(self.year_model, **{self.owner_field: foreign}, **self.year_values)
        period = self.create(self.period_model, **{self.year_field: year}, **self.period_values)
        for changes in [
            {"periode" if self.secondary else "semestre": period.pk},
            {"bareme": 0},
            {"coefficient": -1},
        ]:
            with self.subTest(changes=changes):
                response = self.client.post(self.base, {**self.payload, **changes}, format="json")
                assert response.status_code == 400, response.data

    def test_closed_period_blocks_grade_writes(self):
        setattr(self.period, "cloturee" if self.secondary else "cloture", True)
        self.period.save()
        response = self.save_grades([self.row(self.learners[0])])
        assert response.status_code == 400, response.data
        assert self.note_model.objects.count() == 0

    def test_individual_assignments_are_limited_to_their_target(self):
        if self.secondary:
            response = self.client.patch(self.url, {"eleve_cible": self.learners[0].pk}, format="json")
            assert response.status_code == 200, response.data
            response = self.client.get(f"{self.url}apprenants/")
            assert [row["id"] for row in response.data["results"]] == [self.learners[0].pk]
            assert self.save_grades([self.row(self.learners[1])]).status_code == 400
        else:
            other_period = self.create(
                self.period_model, **{self.year_field: self.year}, **{**self.period_values, "numero": 2}
            )
            assignment = self.create(
                "etudiants.AffectationECUEIndividuelle",
                inscription_admin=self.enroll(self.learners[2]),
                semestre_cible=other_period,
                ecue=self.subject,
            )
            assert self.save_grades([self.row(self.learners[2])]).status_code == 400
            assignment.semestre_cible = self.period
            assignment.save()
            response = self.client.get(f"{self.url}apprenants/")
            assert response.data["count"] == 3
            assert self.save_grades([self.row(self.learners[2])]).status_code == 200
            self.evaluation.anonyme = True
            self.evaluation.save()
            assert self.client.get(f"{self.url}apprenants/").status_code == 400
