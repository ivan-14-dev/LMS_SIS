from decimal import Decimal

from apps.utilisateurs.models import Utilisateur
from django.contrib.auth.models import Group, Permission

from sis_common.tests.test_grade_entry import GradeEntryFixture


class BusinessRoleSeparationTests(GradeEntryFixture):
    def setUp(self):
        super().setUp()
        self.accountant = Utilisateur.objects.create_user(
            "business-accountant", role="comptable", etablissement=self.tenant
        )
        response = self.save_grades([self.row(self.learners[0])])
        assert response.status_code == 200, response.data
        self.note = self.note_model.objects.get()
        self.note_url = f"/api/v1/notes/notes/{self.note.pk}/"
        fee = self.create(
            "paiements.TypeFrais" if self.secondary else "paiements.TypeFraisInscription",
            **{self.year_field: self.year},
            code="ROLE",
            libelle="Role separation",
            montant=100,
        )
        self.invoice = self.create(
            "paiements.Facture" if self.secondary else "paiements.FactureFrais",
            **{"eleve" if self.secondary else "etudiant": self.learners[0]},
            type_frais=fee,
            numero="ROLE-INVOICE",
            date_emission=self.today,
            date_echeance=self.today,
            montant=100,
        )
        self.payment_model = "paiements.Paiement" if self.secondary else "paiements.PaiementFrais"
        self.payment_url = "/api/v1/paiements/transactions/"
        self.payment_payload = {
            "facture": self.invoice.pk,
            "date_paiement": self.today.isoformat(),
            "montant": "10",
            "mode": "virement",
        }

    def authenticate(self, user, *, staff):
        user.is_staff = staff
        user.save(update_fields=["is_staff"])
        self.client.force_authenticate(Utilisateur.objects.get(pk=user.pk))

    def test_staff_accountant_cannot_read_or_change_academic_grades(self):
        for staff in (False, True):
            with self.subTest(staff=staff):
                self.authenticate(self.accountant, staff=staff)
                assert self.client.get(self.note_url).status_code == 404
                response = self.client.patch(self.note_url, {"valeur": "19"}, format="json")
                assert response.status_code == 403, response.data
                self.note.refresh_from_db()
                assert self.note.valeur == Decimal("14")

    def test_staff_teacher_cannot_manage_finance_but_accountant_can(self):
        for index, staff in enumerate((False, True), start=1):
            with self.subTest(staff=staff):
                payment = self.create(
                    self.payment_model,
                    facture=self.invoice,
                    numero=f"ROLE-PAYMENT-{index}",
                    date_paiement=self.today,
                    montant=10,
                    mode="virement",
                    statut="en_attente",
                )
                validation_url = f"{self.payment_url}{payment.pk}/valider/"
                self.authenticate(self.teacher, staff=staff)
                response = self.client.post(self.payment_url, self.payment_payload, format="json")
                assert response.status_code == 400, response.data
                assert "facture" in response.data
                response = self.client.patch(
                    f"/api/v1/paiements/factures/{self.invoice.pk}/", {"montant": "1"}, format="json"
                )
                assert response.status_code == 403, response.data
                assert self.client.post(validation_url).status_code == 403
                payment.refresh_from_db()
                self.invoice.refresh_from_db()
                assert payment.statut == "en_attente"
                assert self.invoice.montant == Decimal("100")
                assert self.invoice.montant_paye == Decimal(10 * (index - 1))
                self.authenticate(self.accountant, staff=staff)
                response = self.client.post(validation_url)
                assert response.status_code == 200, response.data
                payment.refresh_from_db()
                self.invoice.refresh_from_db()
                assert payment.statut == "valide"
                assert payment.verifie_par_id == self.accountant.pk
                assert self.invoice.montant_paye == Decimal(10 * index)
                assert type(payment).objects.count() == index

    def test_staff_learners_retain_personal_payment_submission_and_read_access(self):
        for staff in (False, True):
            with self.subTest(staff=staff):
                learner = self.learners[0].user
                self.authenticate(learner, staff=staff)
                response = self.client.post(self.payment_url, self.payment_payload, format="json")
                assert response.status_code == 201, response.data
                payment = self.invoice.paiements.latest("pk")
                assert payment.statut == "en_attente"
                assert self.client.get(f"{self.payment_url}{payment.pk}/").status_code == 200
                self.authenticate(self.learners[1].user, staff=staff)
                assert self.client.get(f"{self.payment_url}{payment.pk}/").status_code == 404
                response = self.client.post(self.payment_url, self.payment_payload, format="json")
                assert response.status_code == 400, response.data
                self.invoice.refresh_from_db()
                assert self.invoice.montant_paye == 0

    def test_staff_cannot_reassign_permissions_through_accounts_or_owned_groups(self):
        permission = Permission.objects.get(content_type__app_label="notes", codename="change_note")
        group = Group.objects.create(name="business-role-test")
        for actor in (self.teacher, self.accountant):
            actor.groups.add(group)
            for staff in (False, True):
                with self.subTest(role=actor.role, staff=staff):
                    self.authenticate(actor, staff=staff)
                    response = self.client.patch(
                        f"/api/v1/utilisateurs/comptes/{actor.pk}/",
                        {"role": "direction" if self.secondary else "scolarite", "user_permissions": [permission.pk]},
                        format="json",
                    )
                    assert response.status_code == 403, response.data
                    response = self.client.patch(
                        f"/api/v1/utilisateurs/groupes/{group.pk}/",
                        {"permissions": [permission.pk]},
                        format="json",
                    )
                    assert response.status_code == 403, response.data
                    assert self.client.get(f"/api/v1/utilisateurs/comptes/{self.admin.pk}/").status_code == 404
                    actor.refresh_from_db()
                    assert actor.role in ("enseignant", "comptable")
                    assert actor.is_staff is staff
                    assert not actor.is_superuser
                    assert not actor.user_permissions.exists()
                    assert not group.permissions.exists()
                    assert actor.groups.filter(pk=group.pk).exists()

    def test_staff_teacher_remains_limited_to_their_own_evaluations(self):
        other = Utilisateur.objects.create_user("business-other-teacher", role="enseignant", etablissement=self.tenant)
        for staff in (False, True):
            with self.subTest(staff=staff):
                self.authenticate(other, staff=staff)
                assert self.client.get(f"{self.url}apprenants/").status_code == 404
                assert self.save_grades([self.row(self.learners[0])]).status_code == 404
                response = self.client.post(self.base, self.payload, format="json")
                assert response.status_code == 400, response.data
                assert self.client.patch(self.note_url, {"valeur": "19"}, format="json").status_code == 404
                self.authenticate(self.teacher, staff=staff)
                assert self.client.get(f"{self.url}apprenants/").status_code == 200
                response = self.save_grades([self.row(self.learners[0], "15")])
                assert response.status_code == 200, response.data
                self.note.refresh_from_db()
                assert self.note.valeur == Decimal("15")

    def test_explicit_group_administration_permission_does_not_require_staff(self):
        group = Group.objects.create(name="explicitly-managed-group")
        permission = Permission.objects.get(content_type__app_label="auth", codename="change_group")
        note_permission = Permission.objects.get(content_type__app_label="notes", codename="view_note")
        self.accountant.user_permissions.add(permission)
        self.authenticate(self.accountant, staff=False)
        response = self.client.patch(
            f"/api/v1/utilisateurs/groupes/{group.pk}/",
            {"permissions": [note_permission.pk]},
            format="json",
        )
        assert response.status_code == 400, response.data
        assert not group.permissions.exists()
        self.accountant.user_permissions.add(note_permission)
        self.accountant.__dict__.pop("_perm_cache", None)
        self.accountant.__dict__.pop("_user_perm_cache", None)
        self.authenticate(self.accountant, staff=False)
        response = self.client.patch(
            f"/api/v1/utilisateurs/groupes/{group.pk}/",
            {"permissions": [note_permission.pk]},
            format="json",
        )
        assert response.status_code == 200, response.data
        assert list(group.permissions.values_list("pk", flat=True)) == [note_permission.pk]

    def test_teacher_ownership_is_intersected_with_configured_read_scopes(self):
        if self.secondary:
            subject = self.create("classes.Matiere", etablissement=self.tenant, code="ROLE-OTHER", nom="Other subject")
            self.create("classes.ProgrammeMatiere", classe=self.classe, matiere=subject)
            subject_field, scope = "matiere", "matieres"
        else:
            self.subject.credits_ects = 3
            self.subject.save(update_fields=["credits_ects"])
            subject = self.create(
                "ue_ecue.ECUE", ue=self.subject.ue, code="ROLE-OTHER", nom="Other ECUE", credits_ects=3
            )
            subject_field, scope = "ecue", "ecues"
        response = self.client.post(self.base, {**self.payload, subject_field: subject.pk}, format="json")
        assert response.status_code == 201, response.data
        excluded_evaluation = response.data["id"]
        response = self.client.post(
            f"{self.base}{excluded_evaluation}/saisir_notes/", [self.row(self.learners[0])], format="json"
        )
        assert response.status_code == 200, response.data
        excluded_note = self.note_model.objects.get(evaluation_id=excluded_evaluation)
        self.teacher.user_permissions.add(
            *Permission.objects.filter(content_type__app_label="notes", codename__in=["view_note", "view_evaluation"])
        )
        self.teacher.attributs_acces = {
            "permission_scopes": {
                permission: {scope: [self.subject.pk]} for permission in ("notes.view_note", "notes.view_evaluation")
            }
        }
        self.teacher.save(update_fields=["attributs_acces"])
        for staff in (False, True):
            with self.subTest(staff=staff):
                self.authenticate(self.teacher, staff=staff)
                for url, allowed, excluded in (
                    (self.base, self.evaluation.pk, excluded_evaluation),
                    ("/api/v1/notes/notes/", self.note.pk, excluded_note.pk),
                ):
                    response = self.client.get(url)
                    assert response.status_code == 200, response.data
                    assert [row["id"] for row in response.data["results"]] == [allowed]
                    assert self.client.get(f"{url}{allowed}/").status_code == 200
                    assert self.client.get(f"{url}{excluded}/").status_code == 404
                response = self.client.patch(
                    f"/api/v1/notes/notes/{excluded_note.pk}/", {"valeur": "19"}, format="json"
                )
                assert response.status_code == 404, response.data
                excluded_note.refresh_from_db()
                assert excluded_note.valeur == Decimal("14")

    def test_explicit_payment_permission_is_preserved_without_bypassing_constraints(self):
        codename = "add_paiement" if self.secondary else "add_paiementfrais"
        permission = Permission.objects.get(content_type__app_label="paiements", codename=codename)
        self.teacher.user_permissions.add(permission)
        self.authenticate(self.teacher, staff=False)
        response = self.client.post(self.payment_url, self.payment_payload, format="json")
        assert response.status_code == 201, response.data
        self.teacher.attributs_acces = {"permission_scopes": {f"paiements.{codename}": {"classes": []}}}
        self.teacher.save(update_fields=["attributs_acces"])
        self.authenticate(self.teacher, staff=True)
        response = self.client.post(self.payment_url, self.payment_payload, format="json")
        assert response.status_code == 400, response.data
        assert self.invoice.paiements.count() == 1

    def test_superuser_does_not_need_staff_to_manage_academic_records(self):
        self.admin.role = "enseignant"
        self.admin.save(update_fields=["role"])
        self.authenticate(self.admin, staff=False)
        assert self.client.get(f"{self.url}apprenants/").status_code == 200
        response = self.client.patch(self.note_url, {"valeur": "16"}, format="json")
        assert response.status_code == 200, response.data
        self.note.refresh_from_db()
        assert self.note.valeur == Decimal("16")
