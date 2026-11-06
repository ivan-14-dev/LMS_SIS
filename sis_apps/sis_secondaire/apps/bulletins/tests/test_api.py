"""API tests for bulletins."""

import datetime
from types import SimpleNamespace
from unittest.mock import patch

from apps.bulletins.api import AppreciationsMatiereViewSet, BulletinsViewSet, IsEnseignantOrScolarite
from apps.bulletins.models import AppreciationMatiere
from apps.classes.models import Classe, Matiere
from apps.eleves.models import Eleve, EleveTuteur, Tuteur
from apps.etablissement.models import AnneeScolaire, Niveau, Periode
from apps.integration.tests.tenant_test_case import TenantAPITestCase
from apps.notes.models import Bulletin
from apps.utilisateurs.models import Utilisateur
from django.test import SimpleTestCase
from django.urls import resolve
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory


class BulletinsAPITestCase(SimpleTestCase):
    def test_bulletin_routes_are_registered(self):
        list_match = resolve("/api/v1/bulletins/")
        detail_match = resolve("/api/v1/bulletins/1/")
        pdf_match = resolve("/api/v1/bulletins/1/pdf_officiel/")
        history_match = resolve("/api/v1/bulletins/1/historique/")
        appreciations_match = resolve("/api/v1/bulletins/appreciations/")

        assert list_match.url_name == "bulletin-list"
        assert detail_match.url_name == "bulletin-detail"
        assert pdf_match.url_name == "bulletin-pdf-officiel"
        assert history_match.url_name == "bulletin-historique"
        assert appreciations_match.url_name == "appreciation-matiere-list"


class IsEnseignantOrScolaritePermissionTestCase(SimpleTestCase):
    """Vérifie la permission d'écriture des appréciations par matière."""

    def setUp(self):
        self.factory = APIRequestFactory()
        self.permission = IsEnseignantOrScolarite()

    def _view_stub(self):
        return SimpleNamespace()

    def test_read_only_methods_are_always_allowed_for_authenticated_users(self):
        user = SimpleNamespace(is_authenticated=True, is_staff=False, role="eleve")
        request = SimpleNamespace(method="GET", user=user)

        assert self.permission.has_permission(request, self._view_stub()) is True

    def test_plain_student_cannot_write(self):
        user = SimpleNamespace(is_authenticated=True, is_staff=False, role="eleve")
        request = SimpleNamespace(method="POST", user=user)

        assert self.permission.has_permission(request, self._view_stub()) is False

    def test_teacher_profile_can_write(self):
        user = SimpleNamespace(
            is_authenticated=True, is_staff=False, role="enseignant", enseignant_profile=object()
        )
        request = SimpleNamespace(method="POST", user=user)

        assert self.permission.has_permission(request, self._view_stub()) is True

    def test_scolarite_role_can_write_without_teacher_profile(self):
        user = SimpleNamespace(is_authenticated=True, is_staff=False, role="scolarite")
        request = SimpleNamespace(method="PATCH", user=user)

        assert self.permission.has_permission(request, self._view_stub()) is True

    def test_unauthenticated_user_is_denied(self):
        user = SimpleNamespace(is_authenticated=False, is_staff=False, role="")
        request = SimpleNamespace(method="GET", user=user)

        assert self.permission.has_permission(request, self._view_stub()) is False


class AppreciationsMatiereActionsTestCase(SimpleTestCase):
    """Vérifie les actions personnalisées `par_eleve`/`par_classe`."""

    def setUp(self):
        self.factory = APIRequestFactory()

    def test_par_eleve_requires_both_query_params(self):
        request = Request(self.factory.get("/api/v1/bulletins/appreciations/par_eleve/"))
        view = AppreciationsMatiereViewSet()
        view.request = request
        view.format_kwarg = None

        response = view.par_eleve(request)

        assert response.status_code == 400

    def test_par_classe_requires_all_three_query_params(self):
        request = Request(self.factory.get("/api/v1/bulletins/par_classe/", {"classe": "1"}))
        view = BulletinsViewSet()
        view.request = request
        view.format_kwarg = None

        response = view.par_classe(request)

        assert response.status_code == 400

    @patch("apps.bulletins.api.AppreciationMatiere")
    def test_par_classe_queries_appreciation_matiere_not_bulletin(self, mock_model):
        """Régression : `par_classe` doit filtrer sur `AppreciationMatiere`, pas sur les bulletins.

        Avant correction, l'action appelait `self.get_queryset()` -- qui, sur ce
        ViewSet, renvoie un queryset de `Bulletin` (hérité de la vue notes) -- puis
        filtrait sur `matiere_id`, un champ inexistant sur `Bulletin`. Cela levait une
        `FieldError` Django à l'exécution. Ce test vérifie que le gestionnaire
        `AppreciationMatiere.objects` est bien utilisé.
        """
        queryset = mock_model.objects.select_related.return_value
        scoped_queryset = queryset.filter.return_value
        scoped_queryset.filter.return_value.order_by.return_value = []

        request = Request(
            self.factory.get(
                "/api/v1/bulletins/par_classe/",
                {"classe": "1", "matiere": "2", "periode": "3"},
            )
        )
        request.user = SimpleNamespace(
            role="direction", is_staff=True, is_superuser=False, etablissement_id=1
        )
        request.tenant = SimpleNamespace(pk=1)
        view = BulletinsViewSet()
        view.request = request
        view.format_kwarg = None

        response = view.par_classe(request)

        assert response.status_code == 200
        mock_model.objects.select_related.assert_called_once_with("eleve__user", "matiere", "periode")
        queryset.filter.assert_called_once_with(
            eleve__etablissement_id=1, periode__annee_scolaire__etablissement_id=1
        )
        scoped_queryset.filter.assert_called_once_with(
            eleve__classe_actuelle_id="1", matiere_id="2", periode_id="3"
        )


class AppreciationPublicationHTTPTestCase(TenantAPITestCase):
    def setUp(self):
        super().setUp()
        year = AnneeScolaire.objects.create(
            etablissement=self.tenant,
            libelle="2026-2027",
            date_debut=datetime.date(2026, 9, 1),
            date_fin=datetime.date(2027, 6, 30),
        )
        self.periods = [
            Periode.objects.create(
                annee_scolaire=year,
                type="trimestre",
                numero=number,
                date_debut=datetime.date(2026, 9, 1),
                date_fin=datetime.date(2027, 6, 30),
            )
            for number in (1, 2)
        ]
        level = Niveau.objects.create(etablissement=self.tenant, code="6e", libelle="Sixième")
        self.classe = Classe.objects.create(annee_scolaire=year, niveau=level, nom="6e A", etablissement=self.tenant)
        subject = Matiere.objects.create(etablissement=self.tenant, code="MATH", nom="Mathématiques")
        self.student = Utilisateur.objects.create_user(
            "appreciation-student", role="eleve", etablissement=self.tenant
        )
        other = Utilisateur.objects.create_user(
            "appreciation-other", role="eleve", etablissement=self.tenant
        )
        self.own = self._student(self.student, "BUL-OWN")
        someone_else = self._student(other, "BUL-OTHER")
        self.visible = self._appreciation(self.own, subject, self.periods[0], "Own published")
        self.draft = self._appreciation(self.own, subject, self.periods[1], "Own draft")
        self.other = self._appreciation(someone_else, subject, self.periods[0], "Other published")
        Bulletin.objects.create(eleve=self.own, classe=self.classe, periode=self.periods[0], publie=True)
        Bulletin.objects.create(eleve=self.own, classe=self.classe, periode=self.periods[1], publie=False)
        Bulletin.objects.create(eleve=someone_else, classe=self.classe, periode=self.periods[0], publie=True)

    def _student(self, user, matricule):
        return Eleve.objects.create(
            etablissement=self.tenant,
            user=user,
            matricule=matricule,
            classe_actuelle=self.classe,
            date_naissance=datetime.date(2012, 1, 1),
            lieu_naissance="Paris",
            sexe="M",
            date_inscription=datetime.date(2026, 9, 1),
        )

    @staticmethod
    def _appreciation(student, subject, period, text):
        return AppreciationMatiere.objects.create(
            eleve=student, matiere=subject, periode=period, appreciation=text
        )

    def test_student_cannot_read_other_students_or_own_unpublished_appreciations(self):
        self.client.force_authenticate(user=self.student)
        base = "/api/v1/bulletins/appreciations/"

        list_response = self.client.get(base)
        assert list_response.status_code == 200
        assert [row["id"] for row in list_response.data["results"]] == [self.visible.pk]
        assert self.client.get(f"{base}{self.visible.pk}/").status_code == 200
        assert self.client.get(f"{base}{self.draft.pk}/").status_code == 404
        assert self.client.get(f"{base}{self.other.pk}/").status_code == 404

        for student, period, expected in (
            (self.own, self.periods[0], [self.visible.pk]),
            (self.own, self.periods[1], []),
            (self.other.eleve, self.periods[0], []),
        ):
            response = self.client.get(f"{base}par_eleve/", {"eleve": student.pk, "periode": period.pk})
            assert response.status_code == 200
            assert [row["id"] for row in response.data] == expected

        response = self.client.get(
            "/api/v1/bulletins/par_classe/",
            {"classe": self.classe.pk, "matiere": self.visible.matiere_id, "periode": self.periods[0].pk},
        )
        assert response.status_code == 200
        assert [row["id"] for row in response.data] == [self.visible.pk]

    def test_parent_needs_authorized_link_and_publication(self):
        parent = Utilisateur.objects.create_user(
            "appreciation-parent", role="parent", etablissement=self.tenant
        )
        guardian = Tuteur.objects.create(
            etablissement=self.tenant, user=parent, nom="Parent", prenom="Test",
            lien_parente="mere", telephone="0100000000", email="parent@test.example",
        )
        link = EleveTuteur.objects.create(eleve=self.own, tuteur=guardian, autorise_acces_portail=False)
        self.client.force_authenticate(user=parent)
        base = "/api/v1/bulletins/appreciations/"

        assert self.client.get(f"{base}{self.visible.pk}/").status_code == 404
        link.autorise_acces_portail = True
        link.save(update_fields=["autorise_acces_portail"])
        assert self.client.get(f"{base}{self.visible.pk}/").status_code == 200
        assert self.client.get(f"{base}{self.draft.pk}/").status_code == 404
        assert self.client.get(f"{base}{self.other.pk}/").status_code == 404

    def test_published_appreciations_cannot_be_changed_through_http(self):
        staff = Utilisateur.objects.create_user(
            "appreciation-scolarite", role="scolarite", etablissement=self.tenant
        )
        self.client.force_authenticate(user=staff)
        base = "/api/v1/bulletins/appreciations/"

        response = self.client.patch(
            f"{base}{self.visible.pk}/", {"appreciation": "Changed after publication"},
            format="json", secure=True,
        )
        assert response.status_code == 400, response.data
        assert self.client.delete(f"{base}{self.visible.pk}/", secure=True).status_code == 400
        self.visible.refresh_from_db()
        assert self.visible.appreciation == "Own published"

        subject = Matiere.objects.create(etablissement=self.tenant, code="HIST", nom="Histoire")
        payload = {
            "eleve": self.own.pk,
            "matiere": subject.pk,
            "periode": self.periods[0].pk,
            "appreciation": "Added after publication",
        }
        response = self.client.post(base, payload, format="json", secure=True)
        assert response.status_code == 400, response.data
        assert not AppreciationMatiere.objects.filter(
            eleve=self.own, matiere=subject, periode=self.periods[0]
        ).exists()

        payload["periode"] = self.periods[1].pk
        response = self.client.post(base, payload, format="json", secure=True)
        assert response.status_code == 201, response.data
        draft_id = response.data["id"]
        response = self.client.patch(
            f"{base}{draft_id}/", {"periode": self.periods[0].pk},
            format="json", secure=True,
        )
        assert response.status_code == 400, response.data
        assert AppreciationMatiere.objects.get(pk=draft_id).periode_id == self.periods[1].pk
