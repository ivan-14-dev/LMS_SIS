"""API tests for bibliotheque."""

from datetime import timedelta

from apps.bibliotheque.models import Emprunt, Exemplaire, Livre, Reservation
from apps.integration.tests.tenant_test_case import TenantAPITestCase
from apps.utilisateurs.models import Utilisateur
from django.test import SimpleTestCase
from django.urls import resolve
from django.utils import timezone
from django_tenants.utils import schema_context


class BibliothequeAPITestCase(SimpleTestCase):
    """Vérifie que les ViewSets `bibliotheque` sont bien routés (et non des stubs morts)."""

    def test_routes_are_registered(self):
        assert resolve("/api/v1/bibliotheque/livres/").url_name == "livre-list"
        assert resolve("/api/v1/bibliotheque/exemplaires/").url_name == "exemplaire-list"
        assert resolve("/api/v1/bibliotheque/emprunts/").url_name == "emprunt-list"
        assert (
            resolve("/api/v1/bibliotheque/reservations-bibliotheque/").url_name
            == "reservation-bibliotheque-list"
        )
        assert resolve(
            "/api/v1/bibliotheque/reservations-bibliotheque/1/recuperer/"
        ).url_name == "reservation-bibliotheque-recuperer"


class EmpruntRenouveleAPITestCase(TenantAPITestCase):
    def setUp(self):
        self.bibliothecaire = Utilisateur.objects.create_user(
            "bibliothecaire-test", role="bibliothecaire", etablissement=self.tenant
        )
        self.emprunteur = Utilisateur.objects.create_user(
            "emprunteur-test", etablissement=self.tenant
        )
        self.client.force_authenticate(self.bibliothecaire)
        self.livre = Livre.objects.create(titre="Livre test", auteurs="Auteur test")
        self.exemplaire = Exemplaire.objects.create(
            livre=self.livre, code_barre="TEST-001"
        )
        self.today = timezone.now().date()
        self.emprunt = Emprunt.objects.create(
            exemplaire=self.exemplaire,
            emprunteur=self.emprunteur,
            date_emprunt=self.today,
            date_retour_prevue=self.today + timedelta(days=7),
        )
        self.emprunt_url = f"/api/v1/bibliotheque/emprunts/{self.emprunt.pk}/"

    def test_renewed_loan_remains_unavailable_and_can_be_returned(self):
        response = self.client.post(f"{self.emprunt_url}renouveler/")
        assert response.status_code == 200, response.data
        self.emprunt.refresh_from_db()
        assert self.emprunt.statut == "renouvele"

        exemplaire = self.client.get(
            f"/api/v1/bibliotheque/exemplaires/{self.exemplaire.pk}/"
        )
        assert exemplaire.status_code == 200, exemplaire.data
        assert exemplaire.data["disponible"] is False
        livre = self.client.get(f"/api/v1/bibliotheque/livres/{self.livre.pk}/")
        assert livre.data["nb_exemplaires_disponibles"] == 0
        livres = self.client.get("/api/v1/bibliotheque/livres/")
        assert livres.data["results"][0]["nb_exemplaires_disponibles"] == 0

        returned = self.client.post(f"{self.emprunt_url}rendre/")
        assert returned.status_code == 200, returned.data
        assert returned.data["exemplaire_disponible"] is True
        self.emprunt.refresh_from_db()
        assert self.emprunt.statut == "rendu"
        assert self.client.get(
            f"/api/v1/bibliotheque/exemplaires/{self.exemplaire.pk}/"
        ).data["disponible"] is True

    def test_renewed_overdue_loan_is_reported_and_can_be_renewed_again(self):
        self.emprunt.date_retour_prevue = self.today - timedelta(days=20)
        self.emprunt.save(update_fields=["date_retour_prevue"])

        first = self.client.post(f"{self.emprunt_url}renouveler/")
        assert first.status_code == 200, first.data
        overdue = self.client.get("/api/v1/bibliotheque/emprunts/en_retard/")
        assert overdue.status_code == 200, overdue.data
        assert [loan["id"] for loan in overdue.data] == [self.emprunt.pk]
        assert overdue.data[0]["jours_retard"] == 6

        second = self.client.post(f"{self.emprunt_url}renouveler/")
        assert second.status_code == 200, second.data
        third = self.client.post(f"{self.emprunt_url}renouveler/")
        assert third.status_code == 400
        self.emprunt.refresh_from_db()
        assert self.emprunt.nb_renouvellements == 2

    def test_return_reports_unavailable_copy_until_all_active_loans_are_returned(self):
        second = Emprunt.objects.create(
            exemplaire=self.exemplaire,
            emprunteur=self.emprunteur,
            date_emprunt=self.today,
            date_retour_prevue=self.today + timedelta(days=7),
        )
        response = self.client.post(f"{self.emprunt_url}rendre/")
        assert response.status_code == 200, response.data
        assert response.data["exemplaire_disponible"] is False
        assert self.client.get(
            f"/api/v1/bibliotheque/livres/{self.livre.pk}/"
        ).data["nb_exemplaires_disponibles"] == 0
        assert self.client.post(f"{self.emprunt_url}rendre/").status_code == 400
        assert self.client.get(
            f"/api/v1/bibliotheque/exemplaires/{self.exemplaire.pk}/"
        ).data["disponible"] is False
        response = self.client.post(f"/api/v1/bibliotheque/emprunts/{second.pk}/rendre/")
        assert response.status_code == 200, response.data
        assert response.data["exemplaire_disponible"] is True

    def test_return_does_not_make_lost_copy_available_and_replay_does_not_change_return(self):
        self.exemplaire.etat = "perdu"
        self.exemplaire.save(update_fields=["etat"])
        first = self.client.post(f"{self.emprunt_url}rendre/")
        assert first.status_code == 200, first.data
        assert first.data["exemplaire_disponible"] is False
        assert self.client.get(
            f"/api/v1/bibliotheque/livres/{self.livre.pk}/"
        ).data["nb_exemplaires_disponibles"] == 0
        self.emprunt.refresh_from_db()
        original_return_date = self.emprunt.date_retour_reelle
        replay = self.client.post(f"{self.emprunt_url}rendre/")
        assert replay.status_code == 400
        self.emprunt.refresh_from_db()
        assert self.emprunt.date_retour_reelle == original_return_date
        assert self.client.get(
            f"/api/v1/bibliotheque/exemplaires/{self.exemplaire.pk}/"
        ).data["disponible"] is False

    def test_only_local_librarian_can_return_a_loan(self):
        self.client.force_authenticate(self.emprunteur)
        assert self.client.post(f"{self.emprunt_url}rendre/").status_code == 403

        foreign = type(self.tenant)(schema_name="bibliotheque_foreign")
        self.setup_tenant(foreign)
        foreign.auto_create_schema = False
        with schema_context("public"):
            foreign.save()
        outsider = Utilisateur.objects.create_user(
            "foreign-bibliothecaire", role="bibliothecaire", etablissement=foreign
        )
        self.client.force_authenticate(outsider)
        assert self.client.post(f"{self.emprunt_url}rendre/").status_code == 403
        self.emprunt.refresh_from_db()
        assert self.emprunt.statut == "en_cours"

    def test_foreign_staff_cannot_read_local_loans(self):
        foreign = type(self.tenant)(schema_name="bibliotheque_loan_foreign")
        self.setup_tenant(foreign)
        foreign.auto_create_schema = False
        with schema_context("public"):
            foreign.save()
        outsider = Utilisateur.objects.create_user(
            "foreign-loan-staff", is_staff=True, etablissement=foreign
        )
        self.client.force_authenticate(outsider)
        base = "/api/v1/bibliotheque/emprunts/"
        assert self.client.get(base).status_code == 403
        assert self.client.get(self.emprunt_url).status_code == 403
        assert self.client.get(f"{base}en_retard/").status_code == 403

        self.client.force_authenticate(self.emprunteur)
        assert self.client.get(self.emprunt_url).status_code == 200
        assert self.client.post(f"{self.emprunt_url}renouveler/").status_code == 403
        self.client.force_authenticate(self.bibliothecaire)
        assert self.client.post(f"{self.emprunt_url}renouveler/").status_code == 200
        self.emprunt.refresh_from_db()
        assert self.emprunt.statut == "renouvele"


class ReservationLivreAPITestCase(TenantAPITestCase):
    base = "/api/v1/bibliotheque/"

    def setUp(self):
        self.bibliothecaire = Utilisateur.objects.create_user(
            "reserve-bibliothecaire", role="bibliothecaire", etablissement=self.tenant
        )
        self.lecteur = Utilisateur.objects.create_user(
            "reserve-lecteur", etablissement=self.tenant
        )
        self.autre = Utilisateur.objects.create_user(
            "reserve-autre", etablissement=self.tenant
        )
        self.porteur = Utilisateur.objects.create_user(
            "reserve-porteur", etablissement=self.tenant
        )
        self.livre = Livre.objects.create(titre="Titre réservé", auteurs="Auteur")
        self.exemplaire = Exemplaire.objects.create(
            livre=self.livre, code_barre="RES-001"
        )
        self.today = timezone.now().date()
        self.emprunt = Emprunt.objects.create(
            exemplaire=self.exemplaire, emprunteur=self.porteur,
            date_emprunt=self.today, date_retour_prevue=self.today + timedelta(days=7),
        )
        self.client.force_authenticate(self.lecteur)

    def _reclamer(self):
        return self.client.post(f"{self.base}livres/{self.livre.pk}/reserver/")

    def test_claim_is_owner_only_cancellable_and_replay_safe(self):
        claimed = self._reclamer()
        assert claimed.status_code == 201, claimed.data
        reservation = Reservation.objects.get(pk=claimed.data["id"])
        assert reservation.utilisateur_id == self.lecteur.pk
        assert claimed.data["position"] == 1
        assert self.client.post(
            f"{self.base}reservations-bibliotheque/",
            {"livre": self.livre.pk, "utilisateur": self.autre.pk, "statut": "recuperee"},
        ).status_code == 400
        assert self.client.post(
            f"{self.base}reservations-bibliotheque/", {"livre": self.livre.pk}
        ).status_code == 400
        assert self.client.patch(
            f"{self.base}reservations-bibliotheque/{reservation.pk}/",
            {"statut": "recuperee"},
        ).status_code == 405
        self.client.force_authenticate(self.autre)
        assert self.client.post(
            f"{self.base}reservations-bibliotheque/{reservation.pk}/annuler/"
        ).status_code == 404
        self.client.force_authenticate(self.lecteur)
        annuler = f"{self.base}reservations-bibliotheque/{reservation.pk}/annuler/"
        assert self.client.post(annuler).status_code == 200
        assert self.client.post(annuler).status_code == 400
        reservation.refresh_from_db()
        assert reservation.statut == "annulee"
        assert self.client.post(
            f"{self.base}reservations-bibliotheque/", {"livre": self.livre.pk}
        ).status_code == 201

    def test_return_preserves_fifo_hold_and_librarian_fulfils_selected_copy(self):
        first = self._reclamer().data["id"]
        self.client.force_authenticate(self.autre)
        second = self._reclamer().data["id"]
        self.client.force_authenticate(self.bibliothecaire)
        returned = self.client.post(f"{self.base}emprunts/{self.emprunt.pk}/rendre/")
        assert returned.status_code == 200, returned.data
        assert returned.data["exemplaire_disponible"] is False
        assert self.client.patch(
            f"{self.base}emprunts/{self.emprunt.pk}/", {"statut": "en_cours"}
        ).status_code == 405
        assert self.client.get(
            f"{self.base}livres/{self.livre.pk}/"
        ).data["nb_exemplaires_disponibles"] == 0
        assert self.client.get(
            f"{self.base}exemplaires/{self.exemplaire.pk}/"
        ).data["disponible"] is False
        assert self.client.post(
            f"{self.base}emprunts/",
            {"exemplaire": self.exemplaire.pk, "emprunteur": self.porteur.pk,
             "date_emprunt": str(self.today),
             "date_retour_prevue": str(self.today + timedelta(days=21))},
        ).status_code == 400
        assert self.client.post(
            f"{self.base}reservations-bibliotheque/{second}/recuperer/",
            {"exemplaire": self.exemplaire.pk},
        ).status_code == 400
        wrong = Exemplaire.objects.create(
            livre=Livre.objects.create(titre="Autre titre", auteurs="Auteur"),
            code_barre="RES-OTHER",
        )
        first_url = f"{self.base}reservations-bibliotheque/{first}/recuperer/"
        assert self.client.post(first_url, {"exemplaire": wrong.pk}).status_code == 400
        self.client.force_authenticate(self.lecteur)
        assert self.client.post(first_url, {"exemplaire": self.exemplaire.pk}).status_code == 403
        self.client.force_authenticate(self.bibliothecaire)
        fulfilled = self.client.post(first_url, {"exemplaire": self.exemplaire.pk})
        assert fulfilled.status_code == 200, fulfilled.data
        assert Emprunt.objects.get(pk=fulfilled.data["emprunt"]).emprunteur_id == self.lecteur.pk
        assert self.client.post(first_url, {"exemplaire": self.exemplaire.pk}).status_code == 400
        assert Reservation.objects.get(pk=first).statut == "recuperee"
        assert Reservation.objects.get(pk=second).statut == "en_attente"

        assert self.client.post(
            f"{self.base}emprunts/{fulfilled.data['emprunt']}/rendre/"
        ).status_code == 200
        last = self.client.post(
            f"{self.base}reservations-bibliotheque/{second}/recuperer/",
            {"exemplaire": self.exemplaire.pk},
        )
        assert last.status_code == 200, last.data
        assert Emprunt.objects.get(pk=last.data["emprunt"]).emprunteur_id == self.autre.pk

    def test_claim_rejects_unusable_or_available_stock(self):
        self.exemplaire.etat = "perdu"
        self.exemplaire.save(update_fields=["etat"])
        assert self._reclamer().status_code == 400
        assert not Reservation.objects.exists()
        self.exemplaire.etat = "bon"
        self.exemplaire.save(update_fields=["etat"])
        self.client.force_authenticate(self.bibliothecaire)
        assert self.client.post(
            f"{self.base}emprunts/{self.emprunt.pk}/rendre/"
        ).status_code == 200
        self.client.force_authenticate(self.lecteur)
        assert self._reclamer().status_code == 400
        assert not Reservation.objects.exists()
        self.client.force_authenticate(self.bibliothecaire)
        loan = self.client.post(
            f"{self.base}emprunts/",
            {"exemplaire": self.exemplaire.pk, "emprunteur": self.lecteur.pk,
             "date_emprunt": str(self.today),
             "date_retour_prevue": str(self.today + timedelta(days=21))},
        )
        assert loan.status_code == 201, loan.data
        assert self.client.post(
            f"{self.base}emprunts/",
            {"exemplaire": self.exemplaire.pk, "emprunteur": self.autre.pk,
             "date_emprunt": str(self.today),
             "date_retour_prevue": str(self.today + timedelta(days=21))},
        ).status_code == 400

    def test_overdue_loan_occupies_copy_and_can_be_returned_for_a_hold(self):
        self.emprunt.statut = "en_retard"
        self.emprunt.save(update_fields=["statut"])
        claimed = self._reclamer()
        assert claimed.status_code == 201, claimed.data
        self.client.force_authenticate(self.bibliothecaire)
        assert self.client.post(
            f"{self.base}emprunts/{self.emprunt.pk}/renouveler/"
        ).status_code == 400
        returned = self.client.post(f"{self.base}emprunts/{self.emprunt.pk}/rendre/")
        assert returned.status_code == 200, returned.data
        assert returned.data["exemplaire_disponible"] is False

    def test_foreign_claimant_and_staff_cannot_change_local_hold(self):
        foreign = type(self.tenant)(schema_name="bibliotheque_hold_foreign")
        self.setup_tenant(foreign)
        foreign.auto_create_schema = False
        with schema_context("public"):
            foreign.save()
        outsider = Utilisateur.objects.create_user(
            "foreign-reserver", etablissement=foreign
        )
        foreign_hold = Reservation.objects.create(livre=self.livre, utilisateur=outsider)
        foreign_loan = Emprunt.objects.create(
            exemplaire=self.exemplaire, emprunteur=outsider,
            date_emprunt=self.today, date_retour_prevue=self.today + timedelta(days=7),
        )
        self.client.force_authenticate(outsider)
        assert self._reclamer().status_code == 403
        assert Reservation.objects.count() == 1
        self.client.force_authenticate(self.lecteur)
        reservation = self._reclamer().data["id"]
        foreign_staff = Utilisateur.objects.create_user(
            "foreign-reserver-staff", role="bibliothecaire", etablissement=foreign
        )
        self.client.force_authenticate(foreign_staff)
        assert self.client.get(
            f"{self.base}reservations-bibliotheque/"
        ).status_code == 403
        assert self.client.post(
            f"{self.base}reservations-bibliotheque/{reservation}/recuperer/",
            {"exemplaire": self.exemplaire.pk},
        ).status_code == 403
        self.client.force_authenticate(self.bibliothecaire)
        assert self.client.get(
            f"{self.base}reservations-bibliotheque/{foreign_hold.pk}/"
        ).status_code == 404
        assert self.client.get(f"{self.base}emprunts/{foreign_loan.pk}/").status_code == 404
        assert all(
            item["id"] != foreign_hold.pk
            for item in self.client.get(f"{self.base}reservations-bibliotheque/").data["results"]
        )
        self.client.force_authenticate(self.lecteur)
        assert self.client.patch(
            f"{self.base}livres/{self.livre.pk}/", {"titre": "Altéré"}, format="json"
        ).status_code == 403
        assert Reservation.objects.get(pk=reservation).statut == "en_attente"
