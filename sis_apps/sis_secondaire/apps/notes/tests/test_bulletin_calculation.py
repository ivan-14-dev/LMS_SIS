from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from threading import Event
from unittest.mock import patch

from apps.classes.models import Classe, Matiere, ProgrammeMatiere
from apps.eleves.models import Eleve, Inscription
from apps.enseignants.models import Personnel
from apps.etablissement.models import AnneeScolaire, Niveau, Periode
from apps.integration.tests.tenant_test_case import TenantAPITestCase
from apps.notes.bulletin_calculation import METHOD
from apps.notes.models import Bulletin, Evaluation, Note
from apps.utilisateurs.models import Utilisateur
from django.contrib.auth.models import Permission
from django.db import connection, connections, transaction
from django.http import HttpResponse
from django.test import TransactionTestCase
from django_tenants.utils import schema_context


class BulletinFixture(TenantAPITestCase):
    base = "/api/v1/bulletins/"

    def setUp(self):
        super().setUp()
        self.manager = Utilisateur.objects.create_user(
            "bulletin-manager", role="direction", etablissement=self.tenant
        )
        self.manager.user_permissions.add(*Permission.objects.filter(
            content_type__app_label="notes",
            codename__in=["view_bulletin", "add_bulletin", "change_bulletin"],
        ))
        self.teacher = Utilisateur.objects.create_user(
            "bulletin-teacher", role="enseignant", etablissement=self.tenant
        )
        personnel = Personnel.objects.create(
            user=self.teacher, matricule="BUL-PROF", date_embauche=date(2026, 9, 1)
        )
        self.student = Utilisateur.objects.create_user(
            "bulletin-student", role="eleve", etablissement=self.tenant
        )
        self.year = AnneeScolaire.objects.create(
            etablissement=self.tenant, libelle="2026-2027",
            date_debut=date(2026, 9, 1), date_fin=date(2027, 7, 1),
        )
        self.period = Periode.objects.create(
            annee_scolaire=self.year, type="trimestre", numero=1,
            date_debut=date(2026, 9, 1), date_fin=date(2026, 12, 31),
        )
        level = Niveau.objects.create(etablissement=self.tenant, code="6e", libelle="Sixième")
        self.level = level
        self.classe = Classe.objects.create(
            etablissement=self.tenant, niveau=level, annee_scolaire=self.year, nom="6e A"
        )
        self.pupil = Eleve.objects.create(
            etablissement=self.tenant, user=self.student, matricule="BUL-ELEVE",
            date_naissance=date(2013, 1, 1), lieu_naissance="Ville fictive", sexe="F",
            date_inscription=date(2026, 9, 1),
        )
        self.enrollment = Inscription.objects.create(
            eleve=self.pupil, classe=self.classe, annee_scolaire=self.year,
            date_inscription=date(2026, 9, 1), statut="validee",
        )
        self.subject = Matiere.objects.create(etablissement=self.tenant, code="MATH", nom="Mathématiques")
        self.evaluation = Evaluation.objects.create(
            classe=self.classe, matiere=self.subject, periode=self.period, enseignant=personnel,
            titre="Contrôle", date=date(2026, 11, 9),
        )
        self.note = Note.objects.create(evaluation=self.evaluation, eleve=self.pupil, valeur=Decimal("16.50"))
        self.client.force_authenticate(self.manager)

    def prepare(self):
        return self.client.post(f"{self.base}preparer/", {
            "eleve": self.pupil.pk, "classe": self.classe.pk, "periode": self.period.pk, "methode": METHOD,
        }, format="json", secure=True)

    def create_draft(self):
        response = self.prepare()
        assert response.status_code == 201, response.data
        return response.data

    def act(self, draft, action, **data):
        return self.client.post(f"{self.base}{draft['id']}/{action}/", {
            "version": draft["updated_at"], **data,
        }, format="json", secure=True)

    def validate(self, draft):
        return self.act(draft, "valider", confirmer=True, appreciation_conseil="Vérifié.", decision="")


class CalculatedBulletinTests(BulletinFixture):
    def test_numeric_weights_and_scale_are_explicit_and_no_decision_is_invented(self):
        self.note.valeur = Decimal("10")
        self.note.save()
        second = Evaluation.objects.create(
            classe=self.classe, matiere=self.subject, periode=self.period,
            enseignant=self.evaluation.enseignant, titre="Deuxième contrôle",
            date=self.evaluation.date, bareme=10, coefficient=3,
        )
        Note.objects.create(evaluation=second, eleve=self.pupil, valeur=10)
        french = Matiere.objects.create(etablissement=self.tenant, code="FR", nom="Français")
        third = Evaluation.objects.create(
            classe=self.classe, matiere=french, periode=self.period,
            enseignant=self.evaluation.enseignant, titre="Français", date=self.evaluation.date,
        )
        Note.objects.create(evaluation=third, eleve=self.pupil, valeur=10)
        ProgrammeMatiere.objects.create(classe=self.classe, matiere=self.subject, coefficient=2)
        ProgrammeMatiere.objects.create(classe=self.classe, matiere=french, coefficient=1)
        draft = self.create_draft()
        assert Decimal(draft["moyenne_generale"]) == Decimal("15.00")
        assert draft["calcul_detail"]["matieres"][0]["moyenne"] == "17.50"
        assert draft["decision"] == ""
        assert draft["rang"] is None
        assert draft["publie"] is False
        assert self.prepare().status_code == 409

    def test_validation_is_required_and_only_publication_exposes_the_frozen_result(self):
        draft = self.create_draft()
        assert self.act(draft, "publier").status_code == 400
        self.client.force_authenticate(self.student)
        assert self.client.get(f"{self.base}{draft['id']}/", secure=True).status_code == 404
        self.client.force_authenticate(self.manager)
        approved = self.validate(draft)
        assert approved.status_code == 200, approved.data
        assert approved.data["valide_par"] == self.manager.pk
        assert self.act(approved.data, "publier").status_code == 200
        self.client.force_authenticate(self.student)
        assert self.client.get(f"{self.base}{draft['id']}/", secure=True).status_code == 200
        self.note.valeur = Decimal("5")
        self.note.save()
        with patch("apps.notes.api.render_official_pdf", return_value=HttpResponse(b"%PDF-test")) as render:
            response = self.client.get(f"{self.base}{draft['id']}/pdf_officiel/", secure=True)
        assert response.status_code == 200
        sections = render.call_args.args[3]
        assert any("16.50/20" in str(section) for section in sections)
        assert "private" in response["Cache-Control"]

    def test_changed_sources_and_stale_versions_require_recalculation_and_new_validation(self):
        draft = self.create_draft()
        self.note.valeur = Decimal("18")
        self.note.save()
        assert self.validate(draft).status_code == 409
        refreshed = self.act(draft, "recalculer")
        assert refreshed.status_code == 200, refreshed.data
        assert self.validate(draft).status_code == 409
        approved = self.validate(refreshed.data)
        assert approved.status_code == 200
        self.note.valeur = Decimal("19")
        self.note.save()
        assert self.act(approved.data, "publier").status_code == 409
        recalculated = self.act(approved.data, "recalculer")
        assert recalculated.status_code == 200
        assert recalculated.data["valide_par"] is None
        assert recalculated.data["date_validation"] is None
        assert recalculated.data["appreciation_conseil"] == ""
        assert self.act(recalculated.data, "publier").status_code == 400

    def test_generated_fields_cannot_be_forged_or_patched(self):
        draft = self.create_draft()
        for route in (self.base, "/api/v1/notes/bulletins/"):
            response = self.client.patch(f"{route}{draft['id']}/", {
                "moyenne_generale": "20", "valide_par": self.manager.pk,
            }, format="json", secure=True)
            assert response.status_code == 400, response.data
        bulletin = Bulletin.objects.get(pk=draft["id"])
        assert bulletin.moyenne_generale == Decimal("16.5")
        assert bulletin.valide_par_id is None
        approved = self.validate(draft)
        assert self.act(approved.data, "publier").status_code == 200
        published = self.client.get(f"{self.base}{draft['id']}/", secure=True).data
        assert self.act(published, "recalculer").status_code == 400
        assert self.client.delete(f"{self.base}{draft['id']}/", secure=True).status_code == 400

    def test_pending_enrollment_and_incomplete_grades_are_not_silently_averaged(self):
        self.enrollment.statut = "en_cours"
        self.enrollment.save()
        assert self.prepare().status_code == 400
        self.enrollment.statut = "validee"
        self.enrollment.save()
        for status in ("absente", "non_rendue", "triche"):
            self.note.statut = status
            self.note.save()
            assert self.prepare().status_code == 400
        self.note.delete()
        assert self.prepare().status_code == 400
        assert not Bulletin.objects.exists()

    def test_explicit_permissions_and_their_scopes_are_required_even_for_staff(self):
        self.teacher.is_staff = True
        self.teacher.save()
        self.client.force_authenticate(self.teacher)
        assert self.prepare().status_code == 403
        self.manager.attributs_acces = {
            "permission_scopes": {"notes.change_bulletin": {"classes": [self.classe.pk + 100]}}
        }
        self.manager.save()
        self.client.force_authenticate(self.manager)
        assert self.prepare().status_code == 403
        assert not Bulletin.objects.exists()

    def test_period_from_another_year_is_rejected(self):
        other = AnneeScolaire.objects.create(
            etablissement=self.tenant, libelle="2027-2028",
            date_debut=date(2027, 9, 1), date_fin=date(2028, 7, 1),
        )
        self.period.annee_scolaire = other
        self.period.save()
        assert self.prepare().status_code == 400

    def test_explicit_dispensation_is_excluded_but_an_unassessed_required_subject_blocks(self):
        sport = Matiere.objects.create(etablissement=self.tenant, code="EPS", nom="Sport")
        ProgrammeMatiere.objects.create(classe=self.classe, matiere=sport, coefficient=2)
        assert self.prepare().status_code == 400
        evaluation = Evaluation.objects.create(
            classe=self.classe, matiere=sport, periode=self.period,
            enseignant=self.evaluation.enseignant, titre="Sport", date=self.evaluation.date,
        )
        Note.objects.create(evaluation=evaluation, eleve=self.pupil, statut="dispensee")
        draft = self.create_draft()
        assert draft["calcul_detail"]["moyenne_generale"] == "16.50"
        assert draft["calcul_detail"]["exclusions"][0]["motif"] == "dispense"

    def test_legacy_teacher_role_cannot_delete_a_generated_draft_without_the_new_permissions(self):
        draft = self.create_draft()
        self.classe.prof_principal = self.teacher
        self.classe.save()
        self.client.force_authenticate(self.teacher)
        assert self.client.delete(f"{self.base}{draft['id']}/", secure=True).status_code == 403
        assert Bulletin.objects.filter(pk=draft["id"]).exists()


class BulletinConcurrencyTests(BulletinFixture):
    @classmethod
    def _fixture_setup(cls):
        TransactionTestCase._fixture_setup.__func__(cls)

    def _fixture_teardown(self):
        with schema_context(self.tenant.schema_name):
            TransactionTestCase._fixture_teardown(self)
            self.period.delete()
            self.year.delete()
            self.level.delete()

    def test_locked_source_returns_a_retryable_conflict_without_creating_a_partial_report(self):
        assert not connection.in_atomic_block
        locked = Event()
        release = Event()

        def hold_evaluation():
            try:
                with schema_context(self.tenant.schema_name), transaction.atomic():
                    Evaluation.objects.select_for_update().get(pk=self.evaluation.pk)
                    locked.set()
                    assert release.wait(timeout=15), "The calculation waited on a source writer."
            finally:
                connections["default"].close()

        with ThreadPoolExecutor(max_workers=1) as pool:
            holder = pool.submit(hold_evaluation)
            try:
                assert locked.wait(timeout=10)
                response = self.prepare()
                assert response.status_code == 409, response.data
                assert not Bulletin.objects.exists()
            finally:
                release.set()
            holder.result(timeout=10)
        assert self.prepare().status_code == 201
