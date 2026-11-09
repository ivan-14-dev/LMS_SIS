from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from threading import Event
from unittest.mock import patch
from uuid import uuid4

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

    def publish_draft(self, draft=None):
        approved = self.validate(draft or self.create_draft())
        assert approved.status_code == 200, approved.data
        response = self.act(approved.data, "publier")
        assert response.status_code == 200, response.data
        return self.client.get(f"{self.base}{approved.data['id']}/", secure=True).data


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
        self.student.first_name = "Identité modifiée après publication"
        self.student.save()
        with patch("apps.notes.api.render_official_pdf", return_value=HttpResponse(b"%PDF-test")) as render:
            response = self.client.get(f"{self.base}{draft['id']}/pdf_officiel/", secure=True)
        assert response.status_code == 200
        sections = render.call_args.args[3]
        assert render.call_args.args[1] == f"Bulletin - {draft['calcul_detail']['eleve']['nom']}"
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

    def _assert_rectification_conflicts_with_lock(self, source):
        assert not connection.in_atomic_block
        published = self.publish_draft()
        model, pk = (Bulletin, published["id"]) if source == "bulletin" else (Evaluation, self.evaluation.pk)
        payload = {"motif": "Correction contrôlée.", "cle_idempotence": str(uuid4())}
        locked = Event()
        release = Event()

        def hold_source():
            try:
                with schema_context(self.tenant.schema_name), transaction.atomic():
                    model.objects.select_for_update().get(pk=pk)
                    locked.set()
                    assert release.wait(timeout=15), "La rectification a attendu un verrou concurrent."
            finally:
                connections["default"].close()

        with ThreadPoolExecutor(max_workers=1) as pool:
            holder = pool.submit(hold_source)
            try:
                assert locked.wait(timeout=10)
                response = self.act(published, "rectifier", **payload)
                assert response.status_code == 409, response.data
                assert Bulletin.objects.count() == 1
            finally:
                release.set()
            holder.result(timeout=10)
        created = self.act(published, "rectifier", **payload)
        assert created.status_code == 201, created.data
        repeated = self.act(published, "rectifier", **payload)
        assert repeated.status_code == 200, repeated.data
        assert repeated.data["id"] == created.data["id"]
        assert Bulletin.objects.count() == 2

    def test_rectification_never_waits_on_the_original_or_creates_a_partial_revision(self):
        self._assert_rectification_conflicts_with_lock("bulletin")

    def test_rectification_never_waits_on_sources_and_can_be_retried_after_release(self):
        self._assert_rectification_conflicts_with_lock("evaluation")


class BulletinRectificationTests(BulletinFixture):
    def rectify(self, published, **overrides):
        return self.act(published, "rectifier", **{
            "motif": "Erreur de transcription corrigée.",
            "cle_idempotence": str(uuid4()),
            **overrides,
        })

    def test_rectification_preserves_original_and_pdf_until_separately_validated_and_published(self):
        published = self.publish_draft()
        original = Bulletin.objects.values().get(pk=published["id"])
        with patch("apps.notes.api.render_official_pdf", return_value=HttpResponse(b"%PDF-test")) as render:
            assert self.client.get(f"{self.base}{published['id']}/pdf_officiel/", secure=True).status_code == 200
            original_pdf = render.call_args
        self.note.valeur = Decimal("18")
        self.note.save()
        response = self.rectify(published)
        assert response.status_code == 201, response.data
        draft = response.data
        assert draft["revision"] == 2
        assert draft["rectifie"] == published["id"]
        assert draft["rectification_demandee_par"] == self.manager.pk
        assert draft["valide_par"] is None
        assert draft["date_validation"] is None
        assert not draft["signe"]
        assert not draft["publie"]
        assert draft["decision"] == draft["appreciation_conseil"] == ""
        assert Decimal(draft["moyenne_generale"]) == Decimal("18")
        assert self.act(draft, "publier").status_code == 400
        self.client.force_authenticate(self.student)
        for action in ("", "pdf_officiel/", "historique/"):
            assert self.client.get(f"{self.base}{draft['id']}/{action}", secure=True).status_code == 404
        visible_original = self.client.get(f"{self.base}{published['id']}/", secure=True)
        assert visible_original.data["rectification_publiee"] is None
        history = self.client.get(f"{self.base}{published['id']}/historique/", secure=True)
        assert all(event["action"] != "rectification" for event in history.data)
        assert draft["motif_rectification"] not in str(history.data)
        self.client.force_authenticate(self.manager)
        corrected = self.publish_draft(draft)
        assert Bulletin.objects.values().get(pk=published["id"]) == original
        with patch("apps.notes.api.render_official_pdf", return_value=HttpResponse(b"%PDF-test")) as render:
            assert self.client.get(f"{self.base}{published['id']}/pdf_officiel/", secure=True).status_code == 200
            assert render.call_args == original_pdf
            assert self.client.get(f"{self.base}{corrected['id']}/pdf_officiel/", secure=True).status_code == 200
            assert any(section["title"] == "Rectification" for section in render.call_args.args[3])
        self.client.force_authenticate(self.student)
        listing = self.client.get(self.base, secure=True)
        assert {item["id"] for item in listing.data["results"]} == {published["id"], corrected["id"]}
        visible_original = self.client.get(f"{self.base}{published['id']}/", secure=True)
        assert visible_original.data["rectification_publiee"] == corrected["id"]

    def test_retry_is_idempotent_and_a_new_request_cannot_branch_or_rewrite_a_previous_revision(self):
        published = self.publish_draft()
        key = str(uuid4())
        first = self.rectify(published, cle_idempotence=key)
        assert first.status_code == 201, first.data
        retry = self.rectify(published, cle_idempotence=key)
        assert retry.status_code == 200, retry.data
        assert retry.data["id"] == first.data["id"]
        assert Bulletin.objects.count() == 2
        history = self.client.get(f"{self.base}{first.data['id']}/historique/", secure=True)
        assert [event["action"] for event in history.data] == ["rectification"]
        assert history.data[0]["metadata"]["rectifie"] == published["id"]
        assert self.rectify(published).status_code == 409
        assert self.rectify(published, cle_idempotence=key, motif="Autre motif").status_code == 409
        corrected = self.publish_draft(first.data)
        assert self.rectify(published, cle_idempotence=key).data["id"] == corrected["id"]
        successor = self.rectify(corrected)
        assert successor.status_code == 201, successor.data
        assert successor.data["revision"] == 3
        assert successor.data["rectifie"] == corrected["id"]
        assert Bulletin.objects.count() == 3

    def test_rectification_requires_a_reason_key_current_version_and_calculated_publication(self):
        draft = self.create_draft()
        assert self.rectify(draft).status_code == 400
        published = self.publish_draft(draft)
        for overrides in ({"motif": "  "}, {"cle_idempotence": "invalid"}, {"cle_idempotence": None}):
            assert self.rectify(published, **overrides).status_code == 400
        assert self.act(published, "rectifier", motif="Motif sans clé").status_code == 400
        assert self.rectify(published, version=draft["updated_at"]).status_code == 409
        Bulletin.objects.filter(pk=published["id"]).update(calcul_detail={})
        assert self.rectify(published).status_code == 400
        assert Bulletin.objects.count() == 1

    def test_rectification_sources_must_still_be_current_at_validation_and_publication(self):
        published = self.publish_draft()
        draft = self.rectify(published).data
        self.note.valeur = Decimal("19")
        self.note.save()
        assert self.validate(draft).status_code == 409
        refreshed = self.act(draft, "recalculer")
        assert refreshed.status_code == 200, refreshed.data
        assert refreshed.data["rectifie"] == published["id"]
        assert refreshed.data["motif_rectification"] == draft["motif_rectification"]
        assert self.validate(draft).status_code == 409
        approved = self.validate(refreshed.data)
        assert approved.status_code == 200, approved.data
        self.note.valeur = Decimal("17")
        self.note.save()
        assert self.act(approved.data, "publier").status_code == 409
        assert not Bulletin.objects.get(pk=draft["id"]).publie

    def test_explicit_scoped_permissions_are_enforced_and_matching_scopes_can_complete_the_workflow(self):
        published = self.publish_draft()
        self.client.force_authenticate(self.student)
        assert self.rectify(published).status_code == 403
        assert self.act(published, "publier").status_code == 403
        for permission in ("view_bulletin", "add_bulletin", "change_bulletin"):
            self.manager.attributs_acces = {
                "permission_scopes": {f"notes.{permission}": {"classes": [self.classe.pk + 100]}}
            }
            self.manager.save()
            self.client.force_authenticate(Utilisateur.objects.get(pk=self.manager.pk))
            assert self.rectify(published).status_code in (403, 404)
        self.manager.attributs_acces = {"permission_scopes": {
            f"notes.{permission}": {
                "classes": [self.classe.pk], "annees": [self.year.pk], "periodes": [self.period.pk],
            }
            for permission in ("view_bulletin", "add_bulletin", "change_bulletin")
        }}
        self.manager.save()
        self.client.force_authenticate(Utilisateur.objects.get(pk=self.manager.pk))
        draft = self.rectify(published)
        assert draft.status_code == 201, draft.data
        assert self.publish_draft(draft.data)["publie"]

    def test_legacy_direction_role_and_change_permission_do_not_replace_creation_permission(self):
        published = self.publish_draft()
        self.manager.user_permissions.remove(Permission.objects.get(
            content_type__app_label="notes", codename="add_bulletin",
        ))
        self.client.force_authenticate(Utilisateur.objects.get(pk=self.manager.pk))
        assert self.rectify(published).status_code == 403
        assert Bulletin.objects.count() == 1

    def test_provenance_cannot_be_forged_and_correction_drafts_cannot_be_deleted(self):
        published = self.publish_draft()
        draft = self.rectify(published).data
        for base in (self.base, "/api/v1/notes/bulletins/"):
            response = self.client.patch(f"{base}{draft['id']}/", {
                "rectifie": None, "revision": 1, "motif_rectification": "Faux motif", "moyenne_generale": "20",
            }, format="json", secure=True)
            assert response.status_code == 400, response.data
            response = self.client.post(base, {
                "eleve": self.pupil.pk, "classe": self.classe.pk, "periode": self.period.pk,
                "revision": 3, "rectifie": published["id"],
            }, format="json", secure=True)
            assert response.status_code == 400, response.data
            assert self.client.delete(f"{base}{draft['id']}/", secure=True).status_code == 400
        assert Bulletin.objects.count() == 2
