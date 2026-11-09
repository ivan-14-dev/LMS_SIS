"""Upper binding, contact withdrawal and narrow linked-offer regressions."""

from django.core.exceptions import ValidationError
from django.db import transaction

from sis_common.tests.practical_fixtures import BASE, CONSULT, PracticalFixture


class UpperPracticalBindingTests(PracticalFixture):
    def test_validated_ia_and_coherent_formation_offer_are_required(self):
        self.create_programme()
        path = f"{BASE}programmes/{self.programme['id']}/conventions/"
        self.registration.statut = "provisoire"
        self.registration.save(update_fields=["statut"])
        assert self.client.get(path, {"revision": 1}).data["count"] == 0
        self.registration.statut = "validee"
        self.registration.save(update_fields=["statut"])
        offer = self.convention.offre
        offer.formation = None
        offer.save(update_fields=["formation"])
        assert self.client.get(path, {"revision": 1}).data["count"] == 0
        offer.formation = self.curriculum
        offer.save(update_fields=["formation"])
        response = self.client.get(path, {"revision": 1})
        assert response.status_code == 200, response.data
        assert response.data["results"][0]["inscription"]["id"] == self.registration.pk
        assert response.data["results"][0]["partenaire_lie"]["id"] == self.partner.pk
        assert self.client.get(path + f"{self.convention.pk}/partenaires/", {"revision": 1}).status_code == 404
        payload = self.opening_payload()
        before = self.state()
        self.assert_error(
            self.client.post(
                f"{BASE}dossiers/",
                {**payload, "partenaire_utilisateur": None},
                format="json",
            ),
            400,
            "validation_error",
        )
        assert self.state() == before
        dossier = self.open_dossier()
        assert dossier["partenaire"]["id"] == self.partner.pk
        assert dossier["inscription"]["type"] == "inscription_administrative"

    def test_contact_association_grants_no_permission_and_inactive_contact_is_not_selectable(self):
        self.create_programme()
        self.contact.actif = False
        self.contact.save(update_fields=["actif"])
        response = self.client.get(f"{BASE}programmes/{self.programme['id']}/conventions/", {"revision": 1})
        assert response.status_code == 200, response.data
        assert response.data["count"] == 0
        self.contact.actif = True
        self.contact.save(update_fields=["actif"])
        self.partner.user_permissions.clear()
        dossier = self.open_dossier()
        assert dossier["partenaire"] is None
        assert dossier["tuteur_interne"]["id"] == self.tutor.pk
        self.login(self.partner)
        assert self.client.get(self.url()).status_code == 404

    def test_contact_and_company_deactivation_immediately_withdraw_partner_but_not_management(self):
        self.prepare()
        self.login(self.partner)
        assert self.client.get(self.url()).status_code == 200
        for entity in (self.contact, self.company):
            entity.actif = False
            entity.save(update_fields=["actif"])
            assert self.client.get(self.url()).status_code == 404
            assert self.client.get(self.url("historique/")).status_code == 404
            entity.actif = True
            entity.save(update_fields=["actif"])
            assert self.client.get(self.url()).status_code == 200
        self.grant(self.outsider, CONSULT)
        self.contact.user = self.outsider
        try:
            with transaction.atomic():
                self.contact.save(update_fields=["user"])
        except ValidationError:
            self.contact.refresh_from_db()
        self.login(self.outsider)
        assert self.client.get(self.url()).status_code == 404
        if self.contact.user_id == self.outsider.pk:
            self.login(self.partner)
            assert self.client.get(self.url()).status_code == 404

    def test_linked_offer_guard_preserves_unrelated_offer_status_and_unbound_upserts(self):
        self.prepare()
        offer = self.convention.offre
        before = self.state()
        offer.formation = None
        model = type(offer)
        for attempt in (
            lambda: offer.save(update_fields=["formation"]),
            lambda: model.objects.filter(pk=offer.pk).update(formation=None),
            lambda: model.objects.bulk_update([offer], ["formation"]),
            lambda: model.objects.bulk_create(
                [offer],
                update_conflicts=True,
                update_fields=["formation"],
                unique_fields=["id"],
            ),
        ):
            with self.assertRaises(ValidationError), transaction.atomic():  # noqa: PT027
                attempt()
            assert model.objects.get(pk=offer.pk).formation_id == self.curriculum.pk
            assert self.state() == before
        offer.refresh_from_db()
        model.objects.bulk_update([offer], ["formation"])
        assert model.objects.filter(pk=offer.pk).update(statut="fermee") == 1
        assert model.objects.get(pk=offer.pk).statut == "fermee"
        unlinked = self.make_convention().offre
        unlinked.formation = None
        model.objects.bulk_update([unlinked], ["formation"])
        unlinked.formation = self.curriculum
        model.objects.bulk_create(
            [unlinked],
            update_conflicts=True,
            update_fields=["formation"],
            unique_fields=["id"],
        )
        assert model.objects.get(pk=unlinked.pk).formation_id == self.curriculum.pk
        assert self.state() == before

    def test_inactive_formation_reports_curriculum_blockage_and_disables_cancellation(self):
        self.prepare()
        self.curriculum.actif = False
        self.curriculum.save(update_fields=["actif"])
        before = self.state()
        self.login(self.manager)
        response = self.client.get(self.url())
        assert response.status_code == 200, response.data
        assert "curriculum_inactif" in response.data["blocages"]
        assert "acteur_inactif" not in response.data["blocages"]
        assert response.data["actions"]["can_cancel"] is False
        assert response.data["actions"]["can_enter_hours"] is False
        assert response.data["actions"]["can_evaluate"] is False
        assert self.report()["actions"]["can_cancel"] is False
        self.assert_error(self.command("annuler/", motif="Formation inactive"), 403, "contexte_inactif")
        assert self.state() == before
