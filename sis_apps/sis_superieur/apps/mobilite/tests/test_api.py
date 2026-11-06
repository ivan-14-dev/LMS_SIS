"""API tests for mobilite."""

from datetime import date, timedelta

from apps.etablissement.models import AnneeUniversitaire, Universite
from apps.etudiants.models import Etudiant
from apps.formations.models import Formation
from apps.integration.tests.tenant_test_case import TenantAPITestCase
from apps.mobilite.models import AccordEtudes, CandidatureMobilite, ProgrammeMobilite
from apps.structure.models import Departement, Faculte
from apps.utilisateurs.models import Utilisateur
from django.test import SimpleTestCase
from django.urls import resolve
from django.utils import timezone
from django_tenants.utils import schema_context


class MobiliteAPITestCase(SimpleTestCase):
    """Vérifie que les ViewSets `mobilite` sont bien routés (et non des stubs morts)."""

    def test_routes_are_registered(self):
        assert resolve("/api/v1/mobilite/programmes-mobilite/").url_name == "programme-mobilite-list"
        assert resolve("/api/v1/mobilite/candidatures-mobilite/").url_name == "candidature-mobilite-list"
        assert resolve("/api/v1/mobilite/accords-etudes/").url_name == "accord-etudes-list"


class CandidatureDecisionAPITestCase(TenantAPITestCase):
    def setUp(self):
        self.admin = Utilisateur.objects.create_superuser(
            "mobility-admin", role="super_admin", etablissement=self.tenant
        )
        self.client.force_authenticate(self.admin)
        student_user = Utilisateur.objects.create_user(
            "mobility-student", role="etudiant", etablissement=self.tenant
        )
        etudiant = Etudiant.objects.create(
            universite=self.tenant,
            user=student_user,
            matricule="MOB-001",
            date_naissance=date(2002, 1, 1),
            lieu_naissance="Paris",
            sexe="F",
            adresse="1 rue des Études",
            code_postal="75000",
            ville="Paris",
            telephone="0100000000",
        )
        today = timezone.localdate()
        year = AnneeUniversitaire.objects.create(
            universite=self.tenant,
            libelle=str(today.year),
            date_debut=date(today.year, 1, 1),
            date_fin=date(today.year, 12, 31),
        )
        formation = Formation.objects.create(code="MOB", nom="Licence", type="licence")
        programme = ProgrammeMobilite.objects.create(
            formation=formation,
            nom="Mobilité test",
            type="erasmus",
            universite_accueil="Université partenaire",
            pays="France",
            duree_mois=6,
            date_limite_candidature=today + timedelta(days=30),
            annee_universitaire=year,
        )
        self.candidature = CandidatureMobilite.objects.create(
            etudiant=etudiant,
            programme=programme,
            lettre_motivation="Candidature",
            cv="mobilite/cv/test.pdf",
            releve_notes="mobilite/releves/test.pdf",
            projet_personnel="Étudier à l'étranger",
        )
        self.url = f"/api/v1/mobilite/candidatures-mobilite/{self.candidature.pk}/"

    def test_decision_requires_submission_and_cannot_be_bypassed_by_patch(self):
        response = self.client.post(f"{self.url}decider/", {"decision": "acceptee"})
        assert response.status_code == 400, response.data
        self.candidature.refresh_from_db()
        assert self.candidature.statut == "brouillon"
        assert self.candidature.decision_par_id is None

        response = self.client.patch(
            self.url,
            {
                "statut": "soumise",
                "date_soumission": timezone.now().isoformat(),
                "decision_par": self.admin.pk,
                "motif_refus": "sans décision",
            },
            format="json",
        )
        assert response.status_code == 200, response.data
        self.candidature.refresh_from_db()
        assert self.candidature.statut == "brouillon"
        assert self.candidature.date_soumission is None
        assert self.candidature.decision_par_id is None
        assert self.candidature.motif_refus == ""

        response = self.client.post(f"{self.url}soumettre/")
        assert response.status_code == 200, response.data
        self.candidature.refresh_from_db()
        assert self.candidature.date_soumission is not None

        response = self.client.post(f"{self.url}decider/", {"decision": "preselectionne"})
        assert response.status_code == 200, response.data
        self.candidature.refresh_from_db()
        assert self.candidature.statut == "preselectionne"

        response = self.client.post(f"{self.url}decider/", {"decision": "acceptee"})
        assert response.status_code == 200, response.data
        self.candidature.refresh_from_db()
        assert self.candidature.statut == "acceptee"
        assert self.candidature.decision_par_id == self.admin.pk

        response = self.client.post(f"{self.url}decider/", {"decision": "acceptee"})
        assert response.status_code == 400, response.data
        self.candidature.refresh_from_db()
        assert self.candidature.statut == "acceptee"
        assert self.candidature.decision_par_id == self.admin.pk

        response = self.client.post(f"{self.url}decider/", {"decision": "refusee"})
        assert response.status_code == 400, response.data
        self.candidature.refresh_from_db()
        assert self.candidature.statut == "acceptee"

    def _foreign_records(self):
        other_tenant = Universite(
            schema_name="mobilite_foreign_test",
            nom="Université étrangère",
            type="universite_publique",
            adresse="2 rue des Tests",
            code_postal="75000",
            ville="Paris",
            telephone="0100000001",
            email="foreign@test-universite.example",
        )
        other_tenant.auto_create_schema = False
        with schema_context("public"):
            other_tenant.save()

        other_user = Utilisateur.objects.create_user(
            "mobility-foreign-student", role="etudiant", etablissement=self.tenant
        )
        foreign_student = Etudiant.objects.create(
            universite=other_tenant,
            user=other_user,
            matricule="MOB-FOREIGN",
            date_naissance=date(2002, 1, 1),
            lieu_naissance="Paris",
            sexe="F",
            adresse="2 rue des Études",
            code_postal="75000",
            ville="Paris",
            telephone="0100000001",
        )
        today = timezone.localdate()
        foreign_year = AnneeUniversitaire.objects.create(
            universite=other_tenant,
            libelle=str(today.year),
            date_debut=date(today.year, 1, 1),
            date_fin=date(today.year, 12, 31),
        )
        foreign_programme = ProgrammeMobilite.objects.create(
            formation=self.candidature.programme.formation,
            nom="Programme étranger",
            type="erasmus",
            universite_accueil="Université partenaire",
            pays="France",
            duree_mois=6,
            date_limite_candidature=today + timedelta(days=30),
            annee_universitaire=foreign_year,
        )
        foreign_faculte = Faculte.objects.create(
            universite=other_tenant, nom="Faculté étrangère", code="MOB-F"
        )
        foreign_departement = Departement.objects.create(
            faculte=foreign_faculte, nom="Département étranger", code="MOB-F"
        )
        foreign_formation = Formation.objects.create(
            departement=foreign_departement,
            code="MOB-F",
            nom="Formation étrangère",
            type="licence",
        )
        foreign_formation_programme = ProgrammeMobilite.objects.create(
            formation=foreign_formation,
            nom="Mobilité de formation étrangère",
            type="erasmus",
            universite_accueil="Université partenaire",
            pays="France",
            duree_mois=6,
            date_limite_candidature=today + timedelta(days=30),
            annee_universitaire=self.candidature.programme.annee_universitaire,
        )
        return foreign_student, foreign_year, foreign_programme, foreign_formation, foreign_formation_programme

    def test_foreign_programmes_are_hidden_and_not_writable(self):
        _, foreign_year, foreign_programme, foreign_formation, foreign_formation_programme = self._foreign_records()
        base = "/api/v1/mobilite/programmes-mobilite/"
        for programme in (foreign_programme, foreign_formation_programme):
            assert self.client.get(f"{base}{programme.pk}/").status_code == 404
            assert self.client.get(f"{base}{programme.pk}/candidatures/").status_code == 404
        response = self.client.get(base)
        assert response.status_code == 200, response.data
        assert [row["id"] for row in response.data["results"]] == [self.candidature.programme_id]
        response = self.client.get(f"{base}ouverts/")
        assert response.status_code == 200, response.data
        assert [row["id"] for row in response.data] == [self.candidature.programme_id]

        payload = {
            "formation": self.candidature.programme.formation_id,
            "nom": "Nouveau programme",
            "type": "erasmus",
            "universite_accueil": "Université partenaire",
            "pays": "France",
            "duree_mois": 6,
            "date_limite_candidature": (timezone.localdate() + timedelta(days=30)).isoformat(),
            "annee_universitaire": foreign_year.pk,
        }
        response = self.client.post(base, payload, format="json")
        assert response.status_code == 400, response.data
        assert "annee_universitaire" in response.data
        response = self.client.patch(
            f"{base}{self.candidature.programme_id}/",
            {"annee_universitaire": foreign_year.pk},
            format="json",
        )
        assert response.status_code == 400, response.data
        assert "annee_universitaire" in response.data
        payload["annee_universitaire"] = self.candidature.programme.annee_universitaire_id
        payload["formation"] = foreign_formation.pk
        response = self.client.post(base, payload, format="json")
        assert response.status_code == 400, response.data
        assert "formation" in response.data
        response = self.client.patch(
            f"{base}{self.candidature.programme_id}/",
            {"formation": foreign_formation.pk},
            format="json",
        )
        assert response.status_code == 400, response.data
        assert "formation" in response.data
        payload["formation"] = self.candidature.programme.formation_id
        response = self.client.post(base, payload, format="json")
        assert response.status_code == 201, response.data

    def test_foreign_candidatures_are_hidden_and_not_writable(self):
        foreign_student, _, foreign_programme, _, _ = self._foreign_records()
        base = "/api/v1/mobilite/candidatures-mobilite/"
        foreign_candidatures = []

        for etudiant, programme in (
            (foreign_student, self.candidature.programme),
            (self.candidature.etudiant, foreign_programme),
        ):
            candidature = CandidatureMobilite.objects.create(
                etudiant=etudiant,
                programme=programme,
                lettre_motivation="Candidature",
                cv="mobilite/cv/test.pdf",
                releve_notes="mobilite/releves/test.pdf",
                projet_personnel="Étudier à l'étranger",
                statut="soumise",
                date_soumission=timezone.now(),
            )
            foreign_candidatures.append(candidature)
            url = f"{base}{candidature.pk}/"
            assert self.client.get(url).status_code == 404
            for _ in range(2):
                response = self.client.post(f"{url}decider/", {"decision": "acceptee"})
                assert response.status_code == 404, response.data
            candidature.refresh_from_db()
            assert candidature.statut == "soumise"
            assert candidature.decision_par_id is None

        response = self.client.get(base)
        assert response.status_code == 200, response.data
        assert [row["id"] for row in response.data["results"]] == [self.candidature.pk]
        response = self.client.get(
            f"/api/v1/mobilite/programmes-mobilite/{self.candidature.programme_id}/candidatures/"
        )
        assert response.status_code == 200, response.data
        assert [row["id"] for row in response.data] == [self.candidature.pk]
        response = self.client.get("/api/v1/mobilite/programmes-mobilite/")
        assert response.status_code == 200, response.data
        assert response.data["results"][0]["nb_candidatures"] == 1
        assert response.data["results"][0]["places_restantes"] == self.candidature.programme.nb_places

        for field, foreign_id in (
            ("etudiant", foreign_student.pk),
            ("programme", foreign_programme.pk),
        ):
            payload = {
                "etudiant": self.candidature.etudiant_id,
                "programme": self.candidature.programme_id,
                "lettre_motivation": "Candidature",
                "projet_personnel": "Étudier à l'étranger",
                field: foreign_id,
            }
            response = self.client.post(base, payload, format="json")
            assert response.status_code == 400, response.data
            assert field in response.data
            response = self.client.patch(self.url, {field: foreign_id}, format="json")
            assert response.status_code == 400, response.data
            assert field in response.data
            response = self.client.put(self.url, payload, format="json")
            assert response.status_code == 400, response.data
            assert field in response.data
        self.candidature.refresh_from_db()
        assert self.candidature.etudiant_id != foreign_student.pk
        assert self.candidature.programme_id != foreign_programme.pk
        assert CandidatureMobilite.objects.filter(
            pk__in=[item.pk for item in foreign_candidatures], statut="soumise"
        ).count() == 2

        response = self.client.post(f"{self.url}soumettre/")
        assert response.status_code == 200, response.data
        response = self.client.post(f"{self.url}decider/", {"decision": "acceptee"})
        assert response.status_code == 200, response.data
        self.candidature.refresh_from_db()
        assert self.candidature.statut == "acceptee"

    def test_foreign_accords_are_hidden_and_not_writable(self):
        foreign_student, _, foreign_programme, _, _ = self._foreign_records()
        base = "/api/v1/mobilite/accords-etudes/"
        for etudiant, programme in (
            (foreign_student, self.candidature.programme),
            (self.candidature.etudiant, foreign_programme),
        ):
            candidature = CandidatureMobilite.objects.create(
                etudiant=etudiant,
                programme=programme,
                lettre_motivation="Candidature",
                cv="mobilite/cv/test.pdf",
                releve_notes="mobilite/releves/test.pdf",
                projet_personnel="Étudier à l'étranger",
            )
            accord = AccordEtudes.objects.create(candidature=candidature)
            assert self.client.get(f"{base}{accord.pk}/").status_code == 404
            for action in ("valider_origine", "valider_accueil"):
                response = self.client.post(f"{base}{accord.pk}/{action}/")
                assert response.status_code == 404, response.data
            accord.refresh_from_db()
            assert accord.statut == "brouillon"
        unassigned_foreign_candidature = CandidatureMobilite.objects.create(
            etudiant=foreign_student,
            programme=self.candidature.programme,
            lettre_motivation="Candidature",
            cv="mobilite/cv/test.pdf",
            releve_notes="mobilite/releves/test.pdf",
            projet_personnel="Étudier à l'étranger",
        )
        response = self.client.post(
            base, {"candidature": unassigned_foreign_candidature.pk}, format="json"
        )
        assert response.status_code == 400, response.data
        assert "candidature" in response.data
        response = self.client.post(
            base, {"candidature": self.candidature.pk}, format="json"
        )
        assert response.status_code == 201, response.data
        accord_id = response.data["id"]
        for method in (self.client.patch, self.client.put):
            response = method(
                f"{base}{accord_id}/",
                {"candidature": unassigned_foreign_candidature.pk},
                format="json",
            )
            assert response.status_code == 400, response.data
            assert "candidature" in response.data
        response = self.client.get(base)
        assert response.status_code == 200, response.data
        assert [row["id"] for row in response.data["results"]] == [accord_id]
        assert self.client.get(f"{base}{accord_id}/").status_code == 200
        for action in ("valider_origine", "valider_accueil"):
            response = self.client.post(f"{base}{accord_id}/{action}/")
            assert response.status_code == 200, response.data

    def test_accord_validation_cannot_be_forged_via_crud(self):
        base = "/api/v1/mobilite/accords-etudes/"
        validated_at = timezone.now().isoformat()
        response = self.client.post(
            base,
            {
                "candidature": self.candidature.pk,
                "statut": "valide_accueil",
                "date_validation_accueil": validated_at,
            },
            format="json",
        )
        assert response.status_code == 400, response.data
        assert "statut" in response.data
        assert not AccordEtudes.objects.filter(candidature=self.candidature).exists()

        response = self.client.post(
            base, {"candidature": self.candidature.pk, "statut": "soumis"}, format="json"
        )
        assert response.status_code == 201, response.data
        accord = AccordEtudes.objects.get(pk=response.data["id"])
        url = f"{base}{accord.pk}/"
        for method, payload in (
            (self.client.patch, {"statut": "valide_local"}),
            (self.client.put, {"candidature": self.candidature.pk, "statut": "valide_accueil"}),
        ):
            response = method(url, payload, format="json")
            assert response.status_code == 400, response.data
            assert "statut" in response.data
            accord.refresh_from_db()
            assert accord.statut == "soumis"

        response = self.client.patch(
            url,
            {
                "date_validation_origine": validated_at,
                "date_validation_accueil": validated_at,
            },
            format="json",
        )
        assert response.status_code == 200, response.data
        accord.refresh_from_db()
        assert accord.date_validation_origine is None
        assert accord.date_validation_accueil is None

        response = self.client.post(f"{url}valider_origine/")
        assert response.status_code == 200, response.data
        response = self.client.post(f"{url}valider_accueil/")
        assert response.status_code == 200, response.data
        accord.refresh_from_db()
        assert accord.statut == "valide_accueil"
        assert accord.date_validation_origine is not None
        assert accord.date_validation_accueil is not None
