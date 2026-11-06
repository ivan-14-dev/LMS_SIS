"""API tests for bibliotheque."""

from datetime import timedelta

from django.test import SimpleTestCase
from django.urls import resolve
from django.utils import timezone
from django_tenants.utils import schema_context

from apps.bibliotheque.models import Emprunt, Exemplaire, Livre, Reservation
from apps.integration.tests.tenant_test_case import TenantAPITestCase
from apps.utilisateurs.models import Utilisateur


class BibliothequeAPITestCase(SimpleTestCase):
    """Vérifie que les ViewSets `bibliotheque` sont bien routés (et non des stubs morts)."""

    def test_routes_are_registered(self):
        assert resolve("/api/v1/bibliotheque/livres/").url_name == "livre-list"
        assert resolve("/api/v1/bibliotheque/exemplaires/").url_name == "exemplaire-list"
        assert resolve("/api/v1/bibliotheque/emprunts/").url_name == "emprunt-list"
        assert resolve("/api/v1/bibliotheque/reservations/").url_name == "reservation-list"
        assert resolve("/api/v1/bibliotheque/reservations/1/fulfil/").url_name == "reservation-fulfil"


class ExemplaireAvailabilityAPITestCase(TenantAPITestCase):
    def test_unusable_copies_are_not_available_without_active_loans(self):
        user = Utilisateur.objects.create_user(
            "library-reader", role="eleve", etablissement=self.tenant
        )
        self.client.force_authenticate(user)
        livre = Livre.objects.create(titre="Livre de test", auteurs="Auteur de test")

        for etat in ("perdu", "détérioré"):
            with self.subTest(etat=etat):
                exemplaire = Exemplaire.objects.create(
                    livre=livre, code_barre=f"EX-{etat}", etat=etat
                )
                response = self.client.get(
                    f"/api/v1/bibliotheque/exemplaires/{exemplaire.pk}/"
                )
                assert response.status_code == 200, response.data
                assert response.data["disponible"] is False


class EmpruntTenantAPITestCase(TenantAPITestCase):
    def setUp(self):
        self.librarian = Utilisateur.objects.create_user(
            "library-loan-staff", role="bibliothecaire", etablissement=self.tenant
        )
        self.reader = Utilisateur.objects.create_user(
            "library-loan-reader", role="eleve", etablissement=self.tenant
        )
        self.book = Livre.objects.create(titre="Emprunts", auteurs="Test")
        self.copy = Exemplaire.objects.create(livre=self.book, code_barre="LOAN-1")
        self.url = "/api/v1/bibliotheque/emprunts/"
        self.today = timezone.localdate()

    def loan_payload(self, borrower):
        return {
            "exemplaire": self.copy.pk,
            "emprunteur": borrower.pk,
            "date_emprunt": self.today.isoformat(),
            "date_retour_prevue": (self.today + timedelta(days=14)).isoformat(),
        }

    def test_borrower_sees_own_loans_only_while_librarian_sees_all_local_loans(self):
        other_reader = Utilisateur.objects.create_user(
            "library-other-reader", role="eleve", etablissement=self.tenant
        )
        other_copy = Exemplaire.objects.create(livre=self.book, code_barre="LOAN-2")
        own_loan = Emprunt.objects.create(
            exemplaire=self.copy, emprunteur=self.reader,
            date_emprunt=self.today - timedelta(days=10),
            date_retour_prevue=self.today - timedelta(days=5),
        )
        other_loan = Emprunt.objects.create(
            exemplaire=other_copy, emprunteur=other_reader,
            date_emprunt=self.today - timedelta(days=11),
            date_retour_prevue=self.today - timedelta(days=5),
        )
        self.client.force_authenticate(self.reader)

        listed = self.client.get(self.url)
        assert listed.status_code == 200, listed.data
        assert [item["id"] for item in listed.data.get("results", listed.data)] == [own_loan.pk]
        assert self.client.get(f"{self.url}{own_loan.pk}/").status_code == 200
        assert self.client.get(f"{self.url}{other_loan.pk}/").status_code == 404
        overdue = self.client.get(f"{self.url}en_retard/")
        assert overdue.status_code == 200, overdue.data
        assert [item["id"] for item in overdue.data] == [own_loan.pk]
        assert self.client.post(f"{self.url}{other_loan.pk}/retourner/").status_code == 403
        assert self.client.post(f"{self.url}{other_loan.pk}/renouveler/").status_code == 403
        other_loan.refresh_from_db()
        assert other_loan.statut == "en_cours"

        self.client.force_authenticate(self.librarian)
        listed = self.client.get(self.url)
        assert listed.status_code == 200, listed.data
        assert {item["id"] for item in listed.data.get("results", listed.data)} == {
            own_loan.pk, other_loan.pk,
        }
        assert self.client.get(f"{self.url}{other_loan.pk}/").status_code == 200
        overdue = self.client.get(f"{self.url}en_retard/")
        assert overdue.status_code == 200, overdue.data
        assert {item["id"] for item in overdue.data} == {own_loan.pk, other_loan.pk}

    def test_foreign_identity_cannot_read_or_return_local_loan(self):
        loan = Emprunt.objects.create(
            exemplaire=self.copy, emprunteur=self.reader,
            date_emprunt=self.today, date_retour_prevue=self.today + timedelta(days=14),
        )
        foreign = Utilisateur.objects.create_user(
            "library-loan-outsider", role="bibliothecaire", etablissement=self.tenant
        )
        foreign.etablissement_id = self.tenant.pk + 100
        self.client.force_authenticate(foreign)

        assert self.client.get(self.url).status_code == 403
        assert self.client.get(f"{self.url}{loan.pk}/").status_code == 403
        assert self.client.post(f"{self.url}{loan.pk}/retourner/").status_code == 403
        loan.refresh_from_db()
        assert loan.statut == "en_cours"

        self.client.force_authenticate(self.librarian)
        assert self.client.get(f"{self.url}{loan.pk}/").status_code == 200
        assert self.client.post(f"{self.url}{loan.pk}/retourner/").status_code == 200
        loan.refresh_from_db()
        assert loan.statut == "rendu"

    def test_foreign_borrower_is_hidden_and_cannot_be_assigned_to_a_loan(self):
        foreign_tenant = type(self.tenant)(schema_name="library_other")
        self.setup_tenant(foreign_tenant)
        foreign_tenant.auto_create_schema = False
        with schema_context("public"):
            foreign_tenant.save()
        foreign_reader = Utilisateur.objects.create_user(
            "library-foreign-borrower", role="eleve", etablissement=foreign_tenant
        )
        foreign_copy = Exemplaire.objects.create(livre=self.book, code_barre="LOAN-FOREIGN")
        foreign_loan = Emprunt.objects.create(
            exemplaire=foreign_copy, emprunteur=foreign_reader,
            date_emprunt=self.today - timedelta(days=30),
            date_retour_prevue=self.today - timedelta(days=1),
        )
        self.client.force_authenticate(self.librarian)

        denied = self.client.post(self.url, self.loan_payload(foreign_reader), format="json")
        assert denied.status_code == 400, denied.data
        assert "emprunteur" in denied.data
        assert Emprunt.objects.count() == 1

        created = self.client.post(self.url, self.loan_payload(self.reader), format="json")
        assert created.status_code == 201, created.data
        loan_url = f"{self.url}{created.data['id']}/"
        listed = self.client.get(self.url)
        assert listed.status_code == 200, listed.data
        results = listed.data.get("results", listed.data)
        assert [item["id"] for item in results] == [created.data["id"]]
        assert self.client.get(f"{self.url}{foreign_loan.pk}/").status_code == 404
        assert self.client.get(f"{self.url}en_retard/").data == []
        assert self.client.post(f"{self.url}{foreign_loan.pk}/retourner/").status_code == 404
        assert self.client.post(f"{self.url}{foreign_loan.pk}/renouveler/").status_code == 404
        assert self.client.patch(
            loan_url, {"emprunteur": foreign_reader.pk}, format="json"
        ).status_code == 400
        foreign_loan.refresh_from_db()
        assert foreign_loan.statut == "en_cours"
        assert self.client.post(f"{loan_url}retourner/").status_code == 200
        local_loan = Emprunt.objects.get(pk=created.data["id"])
        assert local_loan.emprunteur_id == self.reader.pk
        assert local_loan.statut == "rendu"


class ReservationAPITestCase(TenantAPITestCase):
    def setUp(self):
        self.reader = Utilisateur.objects.create_user(
            "library-reservation-reader", role="eleve", etablissement=self.tenant
        )
        self.second_reader = Utilisateur.objects.create_user(
            "library-reservation-second", role="eleve", etablissement=self.tenant
        )
        self.librarian = Utilisateur.objects.create_user(
            "library-reservation-staff", role="bibliothecaire", etablissement=self.tenant
        )
        self.livre = Livre.objects.create(titre="Réservations", auteurs="Test")
        self.copy = Exemplaire.objects.create(livre=self.livre, code_barre="RES-1")
        self.url = "/api/v1/bibliotheque/reservations/"

    def claim(self, user=None, payload=None):
        self.client.force_authenticate(user or self.reader)
        return self.client.post(
            self.url, payload if payload is not None else {"livre": self.livre.pk},
            format="json",
        )

    def fulfil(self, reservation_id, copy=None):
        return self.client.post(
            f"{self.url}{reservation_id}/fulfil/",
            {
                "exemplaire": (copy or self.copy).pk,
                "date_retour_prevue": (timezone.localdate() + timedelta(days=14)).isoformat(),
            },
            format="json",
        )

    def test_claim_and_fulfil_issue_existing_loan_and_update_availability(self):
        claimed = self.claim()
        assert claimed.status_code == 201, claimed.data
        assert claimed.data["utilisateur"] == self.reader.pk
        assert claimed.data["statut"] == "en_attente"
        loan_url = "/api/v1/bibliotheque/emprunts/"
        self.client.force_authenticate(self.librarian)
        blocked = self.client.post(
            loan_url,
            {
                "exemplaire": self.copy.pk, "emprunteur": self.second_reader.pk,
                "date_emprunt": timezone.localdate().isoformat(),
                "date_retour_prevue": (timezone.localdate() + timedelta(days=14)).isoformat(),
            },
            format="json",
        )
        assert blocked.status_code == 400, blocked.data
        assert Emprunt.objects.count() == 0
        fulfilled = self.fulfil(claimed.data["id"])
        assert fulfilled.status_code == 200, fulfilled.data
        assert fulfilled.data["statut"] == "honoree"
        loan = Emprunt.objects.get(pk=fulfilled.data["emprunt"])
        assert loan.emprunteur_id == self.reader.pk
        assert loan.exemplaire_id == self.copy.pk
        assert loan.statut == "en_cours"
        self.client.force_authenticate(self.reader)
        availability = self.client.get(f"/api/v1/bibliotheque/exemplaires/{self.copy.pk}/")
        assert availability.status_code == 200, availability.data
        assert availability.data["disponible"] is False
        assert self.client.get(f"/api/v1/bibliotheque/livres/{self.livre.pk}/").data[
            "exemplaires"
        ][0]["disponible"] is False
        assert self.claim().status_code == 400
        self.client.force_authenticate(self.librarian)
        assert self.fulfil(claimed.data["id"]).status_code == 400

    def test_only_owner_or_staff_can_cancel_and_only_staff_can_fulfil(self):
        self.client.force_authenticate(None)
        assert self.client.post(self.url, {"livre": self.livre.pk}).status_code in (401, 403)
        claimed = self.claim()
        assert claimed.status_code == 201, claimed.data
        reservation_url = f"{self.url}{claimed.data['id']}/"
        assert self.fulfil(claimed.data["id"]).status_code == 403
        assert self.claim(payload={
            "livre": self.livre.pk, "utilisateur": self.second_reader.pk
        }).status_code == 400
        self.client.force_authenticate(self.second_reader)
        assert self.client.get(reservation_url).status_code == 404
        assert self.client.post(f"{reservation_url}cancel/").status_code == 404
        self.client.force_authenticate(self.reader)
        cancelled = self.client.post(f"{reservation_url}cancel/")
        assert cancelled.status_code == 200, cancelled.data
        assert cancelled.data["statut"] == "annulee"
        assert self.client.post(f"{reservation_url}cancel/").status_code == 400
        assert self.claim().status_code == 201

    def test_double_claim_and_fifo_even_when_another_copy_is_available(self):
        first = self.claim()
        assert first.status_code == 201, first.data
        assert self.claim().status_code == 400
        second = self.claim(self.second_reader)
        assert second.status_code == 201, second.data
        second_copy = Exemplaire.objects.create(livre=self.livre, code_barre="RES-2")
        self.client.force_authenticate(self.librarian)
        assert self.fulfil(second.data["id"], second_copy).status_code == 400
        assert self.fulfil(first.data["id"]).status_code == 200
        assert self.fulfil(second.data["id"], second_copy).status_code == 200
        assert Reservation.objects.filter(statut="honoree").count() == 2

    def test_unavailable_or_wrong_copy_does_not_consume_hold(self):
        claimed = self.claim()
        assert claimed.status_code == 201, claimed.data
        wrong_book = Livre.objects.create(titre="Autre titre", auteurs="Test")
        wrong_copy = Exemplaire.objects.create(livre=wrong_book, code_barre="RES-WRONG")
        self.client.force_authenticate(self.librarian)
        assert self.fulfil(claimed.data["id"], wrong_copy).status_code == 400
        self.copy.etat = "perdu"
        self.copy.save(update_fields=["etat"])
        assert self.fulfil(claimed.data["id"]).status_code == 400
        assert Reservation.objects.get(pk=claimed.data["id"]).statut == "en_attente"
        assert Emprunt.objects.count() == 0

    def test_cancellation_releases_queue_for_regular_loan_workflow(self):
        claimed = self.claim()
        self.client.force_authenticate(self.librarian)
        assert self.client.post(f"{self.url}{claimed.data['id']}/cancel/").status_code == 200
        loan = self.client.post(
            "/api/v1/bibliotheque/emprunts/",
            {
                "exemplaire": self.copy.pk, "emprunteur": self.second_reader.pk,
                "date_emprunt": timezone.localdate().isoformat(),
                "date_retour_prevue": (timezone.localdate() + timedelta(days=14)).isoformat(),
            },
            format="json",
        )
        assert loan.status_code == 201, loan.data
        assert self.client.post(
            f"/api/v1/bibliotheque/emprunts/{loan.data['id']}/retourner/"
        ).status_code == 200
        assert self.client.get(f"/api/v1/bibliotheque/exemplaires/{self.copy.pk}/").data[
            "disponible"
        ] is True

    def test_other_tenant_identity_cannot_claim_or_read_a_hold(self):
        claimed = self.claim()
        assert claimed.status_code == 201, claimed.data
        foreign = Utilisateur.objects.create_user(
            "library-foreign", role="bibliothecaire", etablissement=self.tenant
        )
        foreign.etablissement_id = self.tenant.pk + 100
        self.client.force_authenticate(foreign)
        assert self.client.get(self.url).status_code == 403
        assert self.client.get(f"{self.url}{claimed.data['id']}/").status_code == 403
        assert self.client.post(self.url, {"livre": self.livre.pk}).status_code == 403
        assert self.fulfil(claimed.data["id"]).status_code == 403
        assert Reservation.objects.count() == 1
