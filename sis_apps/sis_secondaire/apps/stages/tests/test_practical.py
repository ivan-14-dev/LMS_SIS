"""Secondary binding and legacy signer regressions on real enrolment records."""

from sis_common.tests.practical_fixtures import BASE, CONSULT, PracticalFixture


class SecondaryPracticalBindingTests(PracticalFixture):
    def test_real_inscription_not_current_class_or_free_text_partner_controls_selection(self):
        assert self.learner.classe_actuelle_id is None
        self.create_programme()
        path = f"{BASE}programmes/{self.programme['id']}/conventions/"
        self.registration.statut = "annulee"
        self.registration.save(update_fields=["statut"])
        response = self.client.get(path, {"revision": 1})
        assert response.status_code == 200, response.data
        assert response.data["count"] == 0
        self.registration.statut = "validee"
        self.registration.save(update_fields=["statut"])
        response = self.client.get(path, {"revision": 1})
        assert response.status_code == 200, response.data
        assert response.data["results"][0]["inscription"]["id"] == self.registration.pk
        assert response.data["results"][0]["partenaire_lie"] is None
        partners = self.client.get(path + f"{self.convention.pk}/partenaires/", {"revision": 1})
        assert partners.status_code == 200, partners.data
        assert self.partner.pk in {item["utilisateur"]["id"] for item in partners.data["results"]}
        assert self.learner_user.pk not in {item["utilisateur"]["id"] for item in partners.data["results"]}
        assert self.tutor.pk not in {item["utilisateur"]["id"] for item in partners.data["results"]}
        role = self.partner.role
        permissions = set(self.partner.user_permissions.values_list("pk", flat=True))
        dossier = self.open_dossier()
        assert dossier["partenaire"]["id"] == self.partner.pk
        self.partner.refresh_from_db()
        assert self.partner.role == role
        assert set(self.partner.user_permissions.values_list("pk", flat=True)) == permissions
        self.grant(self.outsider, CONSULT)
        self.login(self.outsider)
        assert self.client.get(self.url()).status_code == 404

    def test_changed_convention_fingerprint_is_rejected_without_opening_a_dossier(self):
        self.create_programme()
        payload = self.opening_payload()
        self.convention.missions = "Missions révisées après sélection"
        self.convention.save(update_fields=["missions"])
        before = self.state()
        response = self.client.post(f"{BASE}dossiers/", payload, format="json")
        self.assert_error(response, 409, "convention_modifiee")
        assert self.state() == before

    def test_legacy_signer_and_unrelated_legacy_changes_remain_usable(self):
        self.prepare()
        self.grant(self.manager, "stages.change_conventionstage")
        self.login(self.manager)
        root = "/api/v1/stages/conventions-stage/"
        before = self.state()
        response = self.client.patch(root + f"{self.convention.pk}/", {"missions": "Nouvelle mission"}, format="json")
        self.assert_error(response, 409, "structure_protegee")
        assert self.state() == before
        response = self.client.patch(root + f"{self.convention.pk}/", {"remuneration": "42.00"}, format="json")
        assert response.status_code == 200, response.data
        unlinked = self.make_convention(statut="signee_etablissement", date_signature_complete=None)
        response = self.client.post(root + f"{unlinked.pk}/signer/", {"signataire": "etablissement"}, format="json")
        assert response.status_code == 200, response.data
        unlinked.refresh_from_db()
        assert unlinked.statut == "complete"
        assert unlinked.date_signature_complete is not None
        assert self.state() == before
