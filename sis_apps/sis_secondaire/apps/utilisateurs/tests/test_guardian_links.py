"""Parent affiliation lifecycle through the same HTTP surface used by the console."""

from unittest.mock import patch

import pytest
from apps.core.models import WorkflowEvent
from apps.eleves.models import EleveTuteur, Tuteur
from apps.etablissement.models import Etablissement
from apps.utilisateurs.models import Utilisateur
from django.contrib.auth.models import Permission
from django_tenants.utils import schema_context

from sis_common.tests.test_document_access import DocumentFixture

BASE = "/api/v1/utilisateurs/"


class GuardianLinkTests(DocumentFixture):
    def setUp(self):
        super().setUp()
        self.manager = Utilisateur.objects.create_user(
            "family-manager",
            role="personnel_administratif",
            etablissement=self.tenant,
        )
        self.manager.user_permissions.add(
            *Permission.objects.filter(
                content_type__app_label="eleves",
                codename__in=[
                    "view_tuteur",
                    "add_tuteur",
                    "change_tuteur",
                    "delete_tuteur",
                    "view_elevetuteur",
                    "add_elevetuteur",
                    "change_elevetuteur",
                    "delete_elevetuteur",
                ],
            ),
            Permission.objects.get(content_type__app_label="core", codename="view_workflowevent"),
        )
        self.parent = Utilisateur.objects.create_user("family-parent", role="parent", etablissement=self.tenant)
        self.client.force_authenticate(self.manager)
        response = self.client.post(
            f"{BASE}parents/",
            {
                "user": self.parent.pk,
                "nom": "Parent",
                "prenom": "Test",
                "lien_parente": "tuteur_legal",
                "telephone": "0100000000",
                "email": "parent@example.test",
            },
            format="json",
        )
        assert response.status_code == 201, response.data
        self.guardian = Tuteur.objects.get(pk=response.data["id"])
        self.learner = self.learners[0]

    def create_link(self, **overrides):
        return self.client.post(
            f"{BASE}liens-parent/",
            {
                "eleve": self.learner.pk,
                "tuteur": self.guardian.pk,
                "autorise_acces_portail": True,
                **overrides,
            },
            format="json",
        )

    def dossier(self, child=None):
        return self.client.get(
            "/api/v1/portail/apprenant/dossier_enfant/",
            {"enfant_id": child or self.learner.pk},
        )

    def test_create_revoke_restore_and_remove_cut_portal_api_and_pdf(self):
        self.create("notes.Note", evaluation=self.evaluation, eleve=self.learner, valeur=15)
        self.create("notes.Note", evaluation=self.evaluation, eleve=self.learners[1], valeur=3)
        slot = self.create(
            "emplois_du_temps.Creneau",
            classe=self.classe,
            matiere=self.subject,
            enseignant=self.author,
            jour=1,
            heure_debut="08:00",
            heure_fin="09:00",
        )
        roll = self.create("presences.Appel", creneau=slot, date=self.today, enseignant=self.author)
        self.create("presences.Presence", appel=roll, eleve=self.learner, statut="retard", retard_minutes=5)
        self.create("presences.Presence", appel=roll, eleve=self.learners[1], statut="absent")
        fee = self.create("paiements.TypeFrais", annee_scolaire=self.year, code="FAMILY", libelle="Frais", montant=100)
        invoice = self.create(
            "paiements.Facture",
            eleve=self.learner,
            type_frais=fee,
            numero="FAMILY-1",
            date_emission=self.today,
            date_echeance=self.today,
            montant=100,
            montant_paye=20,
        )
        self.create(
            "paiements.Facture",
            eleve=self.learners[1],
            type_frais=fee,
            numero="OTHER-1",
            date_emission=self.today,
            date_echeance=self.today,
            montant=200,
        )
        self.create(
            "paiements.Paiement",
            facture=invoice,
            numero="PAY-FAMILY-1",
            date_paiement=self.today,
            montant=20,
            mode="virement",
        )
        response = self.create_link()
        assert response.status_code == 201, response.data
        link_id = response.data["id"]
        url = f"{BASE}liens-parent/{link_id}/"
        pdf = f"/api/v1/bulletins/{self.documents['bulletins'][0].pk}/pdf_officiel/"
        self.client.force_authenticate(self.parent)
        response = self.dossier()
        assert response.status_code == 200, response.data
        assert response["Cache-Control"] == "private, no-store"
        assert response.data["enfant"]["id"] == self.learner.pk
        assert [row["note"] for row in response.data["notes"]] == [15]
        assert [row["statut"] for row in response.data["absences"]] == ["retard"]
        assert [row["id"] for row in response.data["planning"]] == [slot.pk]
        assert [row["numero"] for row in response.data["factures"]] == ["FAMILY-1"]
        assert response.data["factures"][0]["paiements"][0]["numero"] == "PAY-FAMILY-1"
        assert [item["id"] for item in response.data["bulletins"]] == [self.documents["bulletins"][0].pk]
        assert self.dossier(self.learners[1].pk).status_code == 404
        download = self.client.get(pdf)
        assert download.status_code == 200
        assert download.content.startswith(b"%PDF-")
        assert download["Cache-Control"] == "private, no-store"

        for enabled in (False, True):
            self.client.force_authenticate(self.manager)
            response = self.client.patch(url, {"autorise_acces_portail": enabled}, format="json")
            assert response.status_code == 200, response.data
            self.client.force_authenticate(self.parent)
            assert self.dossier().status_code == (200 if enabled else 404)
            assert self.client.get(pdf).status_code == (200 if enabled else 404)
            dashboard = self.client.get("/api/v1/portail/apprenant/tableau_bord/")
            assert len(dashboard.data["enfants"]) == (1 if enabled else 0)

        self.client.force_authenticate(self.manager)
        assert self.client.get(f"{url}historique/").data["count"] == 3
        assert self.client.delete(url).status_code == 204
        self.client.force_authenticate(self.parent)
        assert self.dossier().status_code == 404
        assert self.client.get(pdf).status_code == 404
        event = WorkflowEvent.objects.get(action="family_deleted", model="elevetuteur", object_id=str(link_id))
        assert event.actor_id == self.manager.pk
        assert event.tenant_id == self.tenant.pk
        assert event.metadata["before"]["tuteur_id"] == self.guardian.pk
        assert event.metadata["after"] is None

    def test_explicit_permission_is_required_even_for_staff_or_legacy_role(self):
        for role in ("parent", "direction", "vie_scolaire"):
            user = Utilisateur.objects.create_user(
                f"family-denied-{role}",
                role=role,
                is_staff=True,
                etablissement=self.tenant,
            )
            self.client.force_authenticate(user)
            assert self.client.get(f"{BASE}liens-parent/").status_code == 403
            assert self.create_link().status_code == 403
            assert self.client.get(f"{BASE}parents/").status_code == 403
        assert not EleveTuteur.objects.exists()

    def test_invalid_duplicate_and_foreign_references_do_not_change_affiliations(self):
        response = self.create_link()
        assert response.status_code == 201
        url = f"{BASE}liens-parent/{response.data['id']}/"
        assert self.create_link().status_code == 400
        assert self.create_link(eleve=999999).status_code == 400
        foreign = Etablissement(schema_name="family_foreign", nom="Other", type="college")
        foreign.auto_create_schema = False
        with schema_context("public"):
            foreign.save()
        other_user = Utilisateur.objects.create_user("foreign-child", role="eleve", etablissement=foreign)
        other = self.create(
            "eleves.Eleve",
            user=other_user,
            etablissement=foreign,
            matricule="FOREIGN",
            date_naissance="2014-01-01",
            date_inscription=self.today,
            sexe="F",
        )
        assert self.create_link(eleve=other.pk).status_code == 400
        assert self.client.patch(url, {"eleve": self.learners[1].pk}, format="json").status_code == 400
        assert EleveTuteur.objects.count() == 1

    def test_profile_cannot_be_attached_to_a_learner_or_transferred_to_another_parent(self):
        assert (
            self.client.post(
                f"{BASE}parents/",
                {
                    "user": self.learner.user_id,
                    "nom": "Parent",
                    "prenom": "Test",
                    "lien_parente": "mere",
                    "telephone": "0100000000",
                    "email": "parent@example.test",
                },
                format="json",
            ).status_code
            == 400
        )
        other = Utilisateur.objects.create_user("family-other-parent", role="parent", etablissement=self.tenant)
        response = self.client.patch(f"{BASE}parents/{self.guardian.pk}/", {"user": other.pk}, format="json")
        assert response.status_code == 400
        self.guardian.refresh_from_db()
        assert self.guardian.user_id == self.parent.pk

    def test_scopes_and_audit_failure_cannot_partially_grant_access(self):
        self.manager.attributs_acces = {
            "permission_scopes": {"eleves.add_elevetuteur": {"eleves": [self.learners[1].pk]}},
        }
        self.manager.save(update_fields=["attributs_acces"])
        assert self.create_link().status_code == 403
        self.manager.attributs_acces = {}
        self.manager.save(update_fields=["attributs_acces"])
        with patch("apps.utilisateurs.guardian_links.record_workflow_event", side_effect=RuntimeError("audit")):
            with pytest.raises(RuntimeError):
                self.create_link()
        assert not EleveTuteur.objects.exists()

    def test_malformed_child_id_and_revoked_read_scope_fail_closed(self):
        self.create_link()
        self.parent.attributs_acces = {"permission_scopes": {"eleves.view_eleve": {"eleves": []}}}
        self.parent.save(update_fields=["attributs_acces"])
        self.client.force_authenticate(self.parent)
        assert self.dossier().status_code == 404
        assert self.dossier("invalid").status_code == 400
        assert self.client.get("/api/v1/portail/apprenant/dossier_enfant/").status_code == 400
