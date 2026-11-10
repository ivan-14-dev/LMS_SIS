from datetime import timedelta

from apps.integration.models import EdxAccessIntent
from apps.integration.tests.tenant_test_case import TenantAPITestCase
from apps.integration.tests.test_sync_service import EnrollmentFixtureMixin
from django.apps import apps
from django.contrib.auth import get_user_model
from django.test import override_settings
from django.utils import timezone

from sis_common.lms_access_sync import learner_model


class PersonalLearningTests(EnrollmentFixtureMixin, TenantAPITestCase):
    def setUp(self):
        super().setUp()
        self.user.etablissement = self.tenant
        self.user.save(update_fields=["etablissement"])
        self.user_mapping.user_id_edx = 123
        self.user_mapping.date_sync = timezone.now()
        self.user_mapping.save()
        self.client.force_authenticate(self.user)
        _, self.learner_field = learner_model()
        self.learner = getattr(self, self.learner_field)

    def intent(self, kind="enrollment"):
        now = timezone.now()
        return EdxAccessIntent.objects.create(
            user=self.user,
            mapping=self.user_mapping,
            course=self.course_mapping,
            kind=kind,
            is_active=True,
            requested_at=now,
            applied_requested_at=now,
        )

    def access(self):
        response = self.client.get("/api/v1/integration/my-learning/")
        self.assertEqual(response.status_code, 200, response.data)
        return response.data

    def teacher(self):
        self.user.role = "enseignant"
        self.user.save(update_fields=["role"])
        if self.learner_field == "eleve":
            model = apps.get_model("enseignants", "Personnel")
            return model.objects.create(user=self.user, matricule="TEACHER", date_embauche="2023-09-01")
        model = apps.get_model("enseignants", "EnseignantChercheur")
        return model.objects.create(user=self.user, specialite="Informatique")

    def test_learner_only_sees_confirmed_current_courses_and_never_studio(self):
        intent = self.intent()
        self.assertEqual(
            self.access()["courses"],
            [
                {
                    "course_id": self.course_mapping.course_id,
                    "name": self.course_mapping.course_name,
                    "can_edit": False,
                }
            ],
        )
        self.assertFalse(self.access()["can_open_studio"])
        for changes in (
            {"applied_requested_at": None},
            {"requested_at": intent.requested_at + timedelta(seconds=1)},
            {"is_active": False},
        ):
            with self.subTest(changes=changes):
                EdxAccessIntent.objects.filter(pk=intent.pk).update(**changes)
                self.assertEqual(self.access()["courses"], [])

    def test_teacher_requires_confirmed_course_access_not_only_a_role(self):
        self.teacher()
        self.assertFalse(self.access()["can_open_studio"])
        intent = self.intent("teaching")
        self.assertTrue(self.access()["can_open_studio"])
        self.assertTrue(self.access()["courses"][0]["can_edit"])
        intent.is_active = False
        intent.save(update_fields=["is_active"])
        self.assertFalse(self.access()["can_open_studio"])

    def test_parents_and_sis_administrators_cannot_use_learning_endpoint(self):
        self.teacher()
        self.intent("teaching")
        for role in ("parent", "super_admin", "chercheur"):
            self.user.role = role
            self.user.is_staff = True
            self.user.is_superuser = True
            self.user.save()
            with self.subTest(role=role):
                self.assertEqual(self.client.get("/api/v1/integration/my-learning/").status_code, 403)

    def test_mapping_schooling_and_institution_revocations_take_effect_immediately(self):
        self.intent()
        self.learner.statut = "suspendu"
        self.learner.save(update_fields=["statut"])
        self.assertEqual(self.access()["courses"], [])
        self.user_mapping.actif = False
        self.user_mapping.save(update_fields=["actif"])
        self.assertEqual(self.access()["state"], "unmapped")
        self.user.etablissement = None
        self.user.save(update_fields=["etablissement"])
        self.assertEqual(self.client.get("/api/v1/integration/my-learning/").status_code, 403)

    @override_settings(EDX_LMS_URL="")
    def test_standalone_reports_unconfigured_without_calling_the_lms(self):
        self.assertEqual(self.access(), {"state": "not_configured", "courses": [], "can_open_studio": False})

    def test_missing_identity_confirmation_and_anonymous_access(self):
        self.user_mapping.date_sync = None
        self.user_mapping.save(update_fields=["date_sync"])
        self.assertEqual(self.access()["state"], "unmapped")
        self.client.force_authenticate(None)
        self.assertIn(self.client.get("/api/v1/integration/my-learning/").status_code, (401, 403))

    def timetable_fixture(self):
        teacher_user = get_user_model().objects.create_user(
            username="schedule_teacher", role="enseignant", etablissement=self.tenant
        )
        if self.learner_field == "eleve":
            staff = apps.get_model("enseignants", "Personnel").objects.create(
                user=teacher_user, matricule="TIMETABLE", date_embauche="2023-09-01"
            )
            self.learner.classe_actuelle = self.classe
            self.learner.save(update_fields=["classe_actuelle"])
            model = apps.get_model("emplois_du_temps", "Creneau")
            selected = model.objects.create(
                classe=self.classe,
                matiere=self.matiere,
                enseignant=staff,
                jour=1,
                heure_debut="08:00",
                heure_fin="09:00",
            )
            model.objects.create(
                classe=self.classe,
                matiere=self.matiere,
                enseignant=staff,
                jour=2,
                heure_debut="08:00",
                heure_fin="09:00",
                actif=False,
            )
            other_class = apps.get_model("classes", "Classe").objects.create(
                etablissement=self.tenant,
                annee_scolaire=self.classe.annee_scolaire,
                niveau=self.classe.niveau,
                nom="Autre classe",
            )
            model.objects.create(
                classe=other_class,
                matiere=self.matiere,
                enseignant=staff,
                jour=3,
                heure_debut="08:00",
                heure_fin="09:00",
            )
        else:
            ecue = self.course_mapping.ecue
            year = ecue.ue.semestre.annee_universitaire
            self.learner.annee_universitaire_actuelle = year
            self.learner.save(update_fields=["annee_universitaire_actuelle"])
            registration = apps.get_model("etudiants", "InscriptionAdministrative").objects.create(
                etudiant=self.learner,
                annee_universitaire=year,
                formation=ecue.ue.maquette.formation,
                date_inscription="2023-09-01",
                statut="validee",
            )
            choice = apps.get_model("etudiants", "InscriptionPedagogique").objects.create(
                inscription_admin=registration,
                semestre=ecue.ue.semestre,
                statut="validee",
                groupe_td="A",
            )
            choice.ecues.add(ecue)
            hour = apps.get_model("emplois_du_temps", "CreneauHoraire").objects.create(
                heure_debut="08:00",
                heure_fin="09:00",
            )
            model = apps.get_model("emplois_du_temps", "CreneauCours")
            selected = model.objects.create(
                semestre=ecue.ue.semestre,
                formation=registration.formation,
                ecue=ecue,
                jour=0,
                creneau_horaire=hour,
                type_cours="TD",
                groupe="A",
            )
            model.objects.create(
                semestre=ecue.ue.semestre,
                formation=registration.formation,
                ecue=ecue,
                jour=1,
                creneau_horaire=hour,
                type_cours="TD",
                groupe="B",
            )
        return selected

    def test_personal_timetable_excludes_other_classes_or_groups_and_suspended_schooling(self):
        slot = self.timetable_fixture()
        response = self.client.get("/api/v1/portail/apprenant/emploi_du_temps/?eleve_id=999&etudiant_id=999")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual([row["id"] for row in response.data], [slot.pk])
        self.assertEqual(response.data[0]["jour"], "Lundi")
        self.learner.statut = "suspendu"
        self.learner.save(update_fields=["statut"])
        self.assertEqual(self.client.get("/api/v1/portail/apprenant/emploi_du_temps/").data, [])

    def test_parent_cannot_request_a_learner_timetable_by_identifier(self):
        self.user.role = "parent"
        self.user.save(update_fields=["role"])
        self.assertEqual(
            self.client.get(f"/api/v1/portail/apprenant/emploi_du_temps/?eleve_id={self.learner.pk}").status_code,
            403,
        )
