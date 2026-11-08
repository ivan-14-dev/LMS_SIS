from concurrent.futures import ThreadPoolExecutor
from datetime import date
from threading import Barrier
from unittest.mock import patch

from apps.core.models import (
    EventInvitation,
    InstitutionalEvent,
    ModuleConfiguration,
    WorkflowEvent,
    WorkflowNotification,
)
from apps.integration.tests.tenant_test_case import TenantAPITestCase
from apps.utilisateurs.models import GroupLifecycle
from django.apps import apps
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.db import connection, connections, transaction
from django.test import TransactionTestCase, override_settings
from django_tenants.utils import get_tenant_domain_model, schema_context
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient

from sis_common.event_occupancy import room_model
from sis_common.institutional_events import CONSULT, MANAGE

URL = "/api/v1/core/evenements/"
NOTIFICATIONS = "/api/v1/core/notifications/"
BOUNDS = {"debut": "2027-03-01T00:00:00+01:00", "fin": "2027-04-01T00:00:00+02:00"}


class EventFixture(TenantAPITestCase):
    def setUp(self):
        self.users = get_user_model()
        self.manager = self.user("agenda-manager", "personnel_administratif")
        self.reader = self.user("agenda-reader", "eleve" if settings.SIS_VARIANT == "secondaire" else "etudiant")
        self.other = self.user("agenda-other", "enseignant", is_staff=True)
        self.manage_permission = Permission.objects.get(content_type__app_label="core", codename=MANAGE.split(".")[1])
        self.read_permission = Permission.objects.get(content_type__app_label="core", codename=CONSULT.split(".")[1])
        self.manager.user_permissions.add(self.manage_permission)
        self.reader.user_permissions.add(self.read_permission)
        self.other.user_permissions.add(self.read_permission)
        ModuleConfiguration.objects.update_or_create(
            etablissement=self.tenant, defaults={"enabled": {"sis.events": True}}
        )
        self.room = self.make_room("EV1", 10)
        self.room2 = self.make_room("EV2", 20)
        self.payload = {
            "titre": "Conférence privée",
            "description": "Invitation nominative",
            "type": "conference",
            "salle": self.room.pk,
            "debut": "2027-03-08T10:00:00+01:00",
            "fin": "2027-03-08T11:00:00+01:00",
            "effectif": 2,
            "participants": [self.reader.pk],
        }
        self.client.force_authenticate(self.manager)

    def user(self, username, role, **kwargs):
        return self.users.objects.create_user(username, role=role, etablissement=self.tenant, **kwargs)

    def make_room(self, code, capacity):
        values = {"code": code, "nom": code, "capacite": capacity}
        if settings.SIS_VARIANT == "secondaire":
            values["etablissement"] = self.tenant
        else:
            values["batiment"] = apps.get_model("emplois_du_temps", "Batiment").objects.get_or_create(
                code="EV", defaults={"nom": "Événements"}
            )[0]
        return room_model().objects.create(**values)

    def create_event(self, **changes):
        response = self.client.post(URL, {**self.payload, **changes}, format="json")
        assert response.status_code == 201, response.data
        return response.data

    def update(self, event, **changes):
        return self.client.post(
            f"{URL}{event['id']}/modifier/", {**self.payload, "version": event["version"], **changes}, format="json"
        )

    def counts(self):
        return tuple(
            model.objects.count()
            for model in (InstitutionalEvent, EventInvitation, WorkflowEvent, WorkflowNotification)
        )

    def course(self):
        def create(name, **values):
            return apps.get_model(name).objects.create(**values)

        if settings.SIS_VARIANT == "secondaire":
            year = create(
                "etablissement.AnneeScolaire",
                etablissement=self.tenant,
                libelle="Agenda",
                date_debut=date(2027, 1, 1),
                date_fin=date(2027, 12, 31),
            )
            level = create("etablissement.Niveau", etablissement=self.tenant, code="EV", libelle="Agenda")
            classe = create("classes.Classe", etablissement=self.tenant, niveau=level, annee_scolaire=year, nom="EV")
            subject = create("classes.Matiere", etablissement=self.tenant, code="EV", nom="Agenda")
            teacher = create("enseignants.Personnel", user=self.other, matricule="EV", date_embauche="2026-01-01")
            return create(
                "emplois_du_temps.Creneau",
                classe=classe,
                matiere=subject,
                enseignant=teacher,
                salle=self.room,
                jour=1,
                heure_debut="10:30",
                heure_fin="11:30",
            )
        year = create(
            "etablissement.AnneeUniversitaire",
            universite=self.tenant,
            libelle="Agenda",
            date_debut=date(2027, 1, 1),
            date_fin=date(2027, 12, 31),
        )
        semester = create(
            "etablissement.Semestre",
            annee_universitaire=year,
            numero=1,
            type="impair",
            date_debut=year.date_debut,
            date_fin=year.date_fin,
        )
        formation = create("formations.Formation", code="EV", nom="Agenda", type="licence")
        curriculum = create("formations.MaquetteFormation", formation=formation, annee_universitaire=year)
        ue = create("ue_ecue.UE", maquette=curriculum, semestre=semester, code="EV", nom="Agenda", credits_ects=6)
        ecue = create("ue_ecue.ECUE", ue=ue, code="EV", nom="Agenda", credits_ects=6)
        slot = create("emplois_du_temps.CreneauHoraire", heure_debut="10:30", heure_fin="11:30")
        return create(
            "emplois_du_temps.CreneauCours",
            semestre=semester,
            formation=formation,
            ecue=ecue,
            salle=self.room,
            jour=0,
            creneau_horaire=slot,
        )

    def occupancy(self):
        if settings.SIS_VARIANT == "secondaire":
            return apps.get_model("salles", "IndisponibiliteSalle").objects.create(
                salle=self.room, date_debut=date(2027, 3, 8), date_fin=date(2027, 3, 8)
            )
        return apps.get_model("emplois_du_temps", "Reservation").objects.create(
            salle=self.room,
            demandeur=self.other,
            date="2027-03-08",
            heure_debut="10:30",
            heure_fin="11:30",
            motif="reunion",
            statut="confirmee",
        )


class InstitutionalEventTests(EventFixture):
    def test_conference_ceremony_invitations_rescheduling_and_cancellation(self):
        first = self.create_event()
        assert first["type"] == "conference"
        ceremony = self.create_event(type="ceremonie", salle=self.room2.pk, participants=[self.other.pk])
        assert ceremony["type"] == "ceremonie"
        self.client.force_authenticate(self.reader)
        result = self.client.get(URL, BOUNDS)
        assert result.status_code == 200, result.data
        assert [row["id"] for row in result.data["results"]] == [first["id"]]
        detail = self.client.get(f"{URL}{first['id']}/").data
        assert "participants" not in detail
        assert detail["can_manage"] is False
        assert self.client.get(f"{URL}{ceremony['id']}/").status_code == 404
        assert self.client.get(NOTIFICATIONS).data["count"] == 1
        self.client.force_authenticate(self.manager)
        changed = self.update(first, debut="2027-03-08T12:00:00+01:00", fin="2027-03-08T13:00:00+01:00")
        assert changed.status_code == 200, changed.data
        assert changed.data["version"] == 2
        assert self.update(first).status_code == 409
        self.client.force_authenticate(self.reader)
        assert self.client.get(NOTIFICATIONS).data["count"] == 2
        self.client.force_authenticate(self.manager)
        cancelled = self.client.post(f"{URL}{first['id']}/annuler/", {"version": 2}, format="json")
        assert cancelled.status_code == 200, cancelled.data
        assert cancelled.data["statut"] == "annule"
        assert self.update(cancelled.data).status_code == 409
        self.create_event()

    def test_capacity_conflict_and_failed_moves_leave_no_partial_writes(self):
        event = self.create_event()
        counts = self.counts()
        for changes in ({"effectif": 11}, {}, {"effectif": 1, "participants": [self.reader.pk, self.other.pk]}):
            response = self.client.post(URL, {**self.payload, **changes}, format="json")
            assert response.status_code == 400, response.data
            assert self.counts() == counts
        second = self.create_event(salle=self.room2.pk, participants=[self.other.pk])
        counts = self.counts()
        assert self.update(second, participants=[self.reader.pk, self.other.pk]).status_code == 400
        assert self.counts() == counts
        persisted = InstitutionalEvent.objects.get(pk=second["id"])
        assert persisted.salle_id == self.room2.pk
        assert persisted.version == 1
        assert list(persisted.invitations.values_list("utilisateur_id", flat=True)) == [self.other.pk]
        assert InstitutionalEvent.objects.get(pk=event["id"]).salle_id == self.room.pk

    def test_adjacent_intervals_are_available_and_same_instants_in_other_zones_conflict(self):
        self.create_event()
        response = self.client.post(
            URL, {**self.payload, "debut": "2027-03-08T09:30:00Z", "fin": "2027-03-08T10:30:00Z"}, format="json"
        )
        assert response.status_code == 400
        self.create_event(debut="2027-03-08T11:00:00+01:00", fin="2027-03-08T12:00:00+01:00")

    def test_notification_failure_rolls_back_creation_and_update(self):
        with patch.object(WorkflowNotification.objects, "create", side_effect=RuntimeError("notification unavailable")):
            with self.assertRaises(RuntimeError):  # noqa: PT027 -- Django's existing unittest runner.
                self.client.post(URL, self.payload, format="json")
        assert self.counts() == (0, 0, 0, 0)
        event = self.create_event()
        counts = self.counts()
        with patch.object(WorkflowNotification.objects, "create", side_effect=RuntimeError("notification unavailable")):
            with self.assertRaises(RuntimeError):  # noqa: PT027
                self.update(event, participants=[self.other.pk], salle=self.room2.pk)
        assert self.counts() == counts
        persisted = InstitutionalEvent.objects.get()
        assert persisted.salle_id == self.room.pk
        assert persisted.version == 1
        assert list(persisted.invitations.filter(revoked_at__isnull=True).values_list("utilisateur_id", flat=True)) == [
            self.reader.pk
        ]

    def test_permissions_are_explicit_and_revoked_on_next_request_without_relogin(self):
        event = self.create_event()
        self.client.force_authenticate(self.other)
        assert self.client.get(URL, BOUNDS).data["count"] == 0
        assert self.client.get(f"{URL}{event['id']}/").status_code == 404
        assert self.client.post(URL, self.payload, format="json").status_code == 403
        assert self.client.get(f"{URL}salles/").status_code == 403
        self.client.force_authenticate(self.reader)
        assert self.update(event).status_code == 403
        assert self.client.get(f"{URL}{event['id']}/").status_code == 200
        self.reader.user_permissions.clear()
        assert self.client.get(f"{URL}{event['id']}/").status_code == 404
        assert self.client.get(NOTIFICATIONS).data["count"] == 0
        self.client.force_authenticate(self.manager)
        assert self.client.get(f"{URL}{event['id']}/").status_code == 200
        self.manager.user_permissions.clear()
        assert self.client.get(f"{URL}{event['id']}/").status_code == 404
        assert self.update(event).status_code == 404

    def test_invitation_withdrawal_and_group_deactivation_hide_notifications_and_detail(self):
        event = self.create_event()
        self.reader.user_permissions.clear()
        group = Group.objects.create(name="Agenda lecteurs")
        group.permissions.add(self.read_permission)
        self.reader.groups.add(group)
        self.client.force_authenticate(self.reader)
        assert self.client.get(f"{URL}{event['id']}/").status_code == 200
        lifecycle = GroupLifecycle.objects.create(group=group, actif=False)
        assert self.client.get(f"{URL}{event['id']}/").status_code == 404
        lifecycle.actif = True
        lifecycle.save()
        assert self.client.get(NOTIFICATIONS).data["count"] == 1
        self.client.force_authenticate(self.manager)
        assert self.update(event, participants=[]).status_code == 200
        self.client.force_authenticate(self.reader)
        assert self.client.get(URL, BOUNDS).data["count"] == 0
        assert self.client.get(f"{URL}{event['id']}/").status_code == 404
        assert self.client.get(NOTIFICATIONS).data["count"] == 0
        assert EventInvitation.objects.get().revoked_at is not None

    def test_abac_scopes_cover_lists_ids_mutations_selectors_and_unknown_attributes(self):
        first = self.create_event()
        second = self.create_event(salle=self.room2.pk)
        self.manager.attributs_acces = {
            "permission_scopes": {MANAGE: {"etablissement_id": [self.tenant.pk], "evenement_id": [first["id"]]}}
        }
        self.manager.save(update_fields=["attributs_acces"])
        assert self.client.get(URL, BOUNDS).data["count"] == 1
        assert self.client.get(f"{URL}{second['id']}/").status_code == 404
        assert self.update(second).status_code == 404
        assert self.client.get(f"{URL}salles/").status_code == 403
        assert self.client.get(f"{URL}salles/", {"evenement_id": first["id"]}).status_code == 200
        assert self.client.get(f"{URL}participants/", {"evenement_id": first["id"], "q": "agenda"}).status_code == 200
        assert self.client.post(URL, self.payload, format="json").status_code == 403
        self.manager.attributs_acces = {"permission_scopes": {MANAGE: {"salle_id": [self.room.pk]}}}
        self.manager.save(update_fields=["attributs_acces"])
        assert self.update(first, salle=self.room2.pk).status_code == 403
        assert InstitutionalEvent.objects.get(pk=first["id"]).salle_id == self.room.pk
        for invalid in (
            {"unsupported": ["any"]},
            {"etablissement_id": [str(self.tenant.pk)]},
            {"evenement_id": ["invalid"]},
            {"salle_id": [True]},
        ):
            self.manager.attributs_acces = {"permission_scopes": {MANAGE: invalid}}
            self.manager.save(update_fields=["attributs_acces"])
            assert self.client.get(URL, BOUNDS).data["count"] == 0
            assert self.client.get(f"{URL}{first['id']}/").status_code == 404
        self.reader.attributs_acces = {"permission_scopes": {CONSULT: {"evenement_id": [second["id"]]}}}
        self.reader.save(update_fields=["attributs_acces"])
        self.client.force_authenticate(self.reader)
        assert self.client.get(f"{URL}{first['id']}/").status_code == 404
        assert self.client.get(URL, BOUNDS).data["count"] == 1
        assert self.client.get(NOTIFICATIONS).data["count"] == 1

    def test_foreign_accounts_relations_and_disabled_module_fail_closed(self):
        event = self.create_event()
        foreign = type(self.tenant)(schema_name="wave38_foreign")
        self.setup_tenant(foreign)
        foreign.auto_create_schema = False
        with schema_context("public"):
            foreign.save()
        self.other.etablissement = foreign
        self.other.save(update_fields=["etablissement"])
        candidates = self.client.get(f"{URL}participants/", {"q": "agenda"}).data["results"]
        assert self.other.pk not in {row["id"] for row in candidates}
        assert all(set(row) == {"id", "nom"} for row in candidates)
        counts = self.counts()
        assert self.update(event, participants=[self.other.pk]).status_code == 400
        assert self.counts() == counts
        self.client.force_authenticate(self.other)
        assert self.client.get(URL, BOUNDS).status_code == 403
        self.client.force_authenticate(self.reader)
        InstitutionalEvent.objects.filter(pk=event["id"]).update(etablissement=foreign)
        assert self.client.get(f"{URL}{event['id']}/").status_code == 404
        assert self.client.get(NOTIFICATIONS).data["count"] == 0
        ModuleConfiguration.objects.filter(etablissement=self.tenant).update(enabled={"sis.events": False})
        assert self.client.get(URL, BOUNDS).status_code == 403

    def test_calendar_requires_bounded_aware_dates_and_disallows_generic_writes(self):
        event = self.create_event()
        for query in ({}, {**BOUNDS, "fin": "2028-01-01T00:00:00Z"}, {**BOUNDS, "debut": "2027-03-01T00:00:00"}):
            assert self.client.get(URL, query).status_code == 400
        assert self.client.get(URL, {**BOUNDS, "page_size": 1}).data["count"] == 1
        for changes in (
            {"debut": "2027-03-08T10:00:00"},
            {"fin": "2028-01-01T00:00:00Z"},
            {"participants": [self.reader.pk, self.reader.pk]},
            {"statut": "annule"},
        ):
            assert self.client.post(URL, {**self.payload, **changes}, format="json").status_code == 400
        assert self.client.patch(f"{URL}{event['id']}/", {}, format="json").status_code == 405
        assert self.client.delete(f"{URL}{event['id']}/").status_code == 405
        assert self.client.get(f"{URL}exporter/", BOUNDS).status_code == 404

    def test_existing_courses_block_events_and_reverse_edits_are_atomic(self):
        course = self.course()
        before = self.counts()
        assert self.client.post(URL, self.payload, format="json").status_code == 400
        assert self.counts() == before
        event = self.create_event(salle=self.room2.pk)
        course.salle = self.room2
        with self.assertRaises(ValidationError), transaction.atomic():  # noqa: PT027
            course.save()
        course.refresh_from_db()
        assert course.salle_id == self.room.pk
        assert InstitutionalEvent.objects.get(pk=event["id"]).version == 1

    def test_existing_unavailability_or_confirmed_reservations_cannot_be_ignored(self):
        occupied = self.occupancy()
        assert self.client.post(URL, self.payload, format="json").status_code == 400
        occupied.delete()
        self.create_event()
        with self.assertRaises(ValidationError), transaction.atomic():  # noqa: PT027
            self.occupancy()
        assert type(occupied).objects.count() == 0
        self.room.capacite = 1
        with self.assertRaises(ValidationError), transaction.atomic():  # noqa: PT027
            self.room.save(update_fields=["capacite"])
        self.room.refresh_from_db()
        assert self.room.capacite == 10
        if settings.SIS_VARIANT == "superieur":
            response = self.client.get(
                f"/api/v1/edt/salles/{self.room.pk}/disponibilite/",
                {"date": "2027-03-08", "heure_debut": "10:00", "heure_fin": "11:00"},
            )
            assert response.status_code == 200
            assert response.data == {"disponible": False, "conflits": []}

    def test_shared_calendar_extension_cannot_displace_a_reserved_event(self):
        course = self.course()
        period = course.classe.annee_scolaire if settings.SIS_VARIANT == "secondaire" else course.semestre
        period.date_fin = date(2027, 3, 1)
        period.save(update_fields=["date_fin"])
        self.create_event()
        period.date_fin = date(2027, 12, 31)
        with self.assertRaises(ValidationError), transaction.atomic():  # noqa: PT027
            period.save(update_fields=["date_fin"])
        period.refresh_from_db()
        assert period.date_fin == date(2027, 3, 1)

    def test_legacy_named_and_unresolved_locations_fail_closed_without_exposing_details(self):
        if settings.SIS_VARIANT == "secondaire":
            club = apps.get_model("clubs", "Club").objects.create(
                nom="Club", salle=self.room.code, date_creation="2027-01-01", responsable=self.other
            )
            source = apps.get_model("clubs", "SeanceClub").objects.create(
                club=club, date="2027-03-08", heure_debut="10:15", heure_fin="10:45", activite="Privée"
            )
        else:
            room = apps.get_model("bibliotheque", "SalleTravail").objects.create(nom=self.room.code)
            source = apps.get_model("bibliotheque", "ReservationSalle").objects.create(
                salle=room, utilisateur=self.other, date="2027-03-08", heure_debut="10:15", heure_fin="10:45"
            )
        response = self.client.post(URL, self.payload, format="json")
        assert response.status_code == 400
        assert set(response.data) == {"salle"}
        self.create_event(salle=self.room2.pk)
        with self.assertRaises(ValidationError), transaction.atomic():  # noqa: PT027
            self.room.delete()
        assert room_model().objects.filter(code="EV1").exists()
        location = source.club if settings.SIS_VARIANT == "secondaire" else source.salle
        field = "salle" if settings.SIS_VARIANT == "secondaire" else "nom"
        setattr(location, field, "Lieu historique non résolu")
        with self.assertRaises(ValidationError), transaction.atomic():  # noqa: PT027
            location.save(update_fields=[field])

    def test_global_workflow_lists_do_not_expose_private_events(self):
        self.create_event()
        auditor = self.user("agenda-auditor", "personnel_administratif", is_staff=True, is_superuser=True)
        self.client.force_authenticate(auditor)
        response = self.client.get("/api/v1/core/workflow-events/", {"model": "institutionalevent"})
        assert response.status_code == 200, response.data
        assert response.data["count"] == 0
        assert WorkflowEvent.objects.filter(model="institutionalevent").count() == 1

    def test_existing_exam_duration_is_reserved_without_rewriting_specialized_records(self):
        course = self.course()
        if settings.SIS_VARIANT == "secondaire":
            session = apps.get_model("examens", "SessionExamen").objects.create(
                annee_scolaire=course.classe.annee_scolaire,
                nom="Examen historique",
                type="controle",
                date_debut="2027-03-08",
                date_fin="2027-03-08",
            )
            fields = {"matiere": course.matiere, "salle_principale": self.room2}
        else:
            session = apps.get_model("examens", "SessionExamen").objects.create(
                semestre=course.semestre, numero=1, date_debut="2027-03-08", date_fin="2027-03-08"
            )
            fields = {"ecue": course.ecue, "lieu": self.room2.code}
        exam = apps.get_model("examens", "EpreuveExamen").objects.create(
            session=session, date="2027-03-08", heure_debut="10:30", duree_minutes=120, **fields
        )
        response = self.client.post(URL, {**self.payload, "salle": self.room2.pk}, format="json")
        assert response.status_code == 400
        self.create_event(salle=self.room2.pk, debut="2027-03-08T12:30:00+01:00", fin="2027-03-08T13:00:00+01:00")
        exam.duree_minutes = 150
        with self.assertRaises(ValidationError), transaction.atomic():  # noqa: PT027
            exam.save(update_fields=["duree_minutes"])
        exam.refresh_from_db()
        assert exam.duree_minutes == 120

    def test_real_second_schema_does_not_inherit_same_identifier_authorization(self):
        hosts = override_settings(ALLOWED_HOSTS=[*settings.ALLOWED_HOSTS, "wave38-other.test"])
        hosts.enable()
        self.addCleanup(hosts.disable)
        event = self.create_event()
        foreign = type(self.tenant)(schema_name="wave38_events_other")
        self.setup_tenant(foreign)
        with schema_context("public"):
            foreign.save(verbosity=0)
            get_tenant_domain_model().objects.create(tenant=foreign, domain="wave38-other.test", is_primary=True)
        try:
            with schema_context(foreign.schema_name):
                local_reader = self.users.objects.create_user(
                    "other-schema-reader", pk=self.reader.pk, etablissement=foreign
                )
                local_reader.user_permissions.add(
                    Permission.objects.get(content_type__app_label="core", codename=CONSULT.split(".")[1])
                )
                ModuleConfiguration.objects.create(etablissement=foreign, enabled={"sis.events": True})
                room_values = {"pk": self.room.pk, "code": "EV1", "nom": "Salle étrangère", "capacite": 10}
                if settings.SIS_VARIANT == "secondaire":
                    room_values["etablissement"] = foreign
                else:
                    room_values["batiment"] = apps.get_model("emplois_du_temps", "Batiment").objects.create(
                        code="EV", nom="Campus étranger"
                    )
                foreign_room = room_model().objects.create(**room_values)
                InstitutionalEvent.objects.create(
                    id=event["id"],
                    etablissement=foreign,
                    cree_par=local_reader,
                    salle=foreign_room,
                    titre="Événement étranger privé",
                    type="conference",
                    effectif=2,
                    debut=self.payload["debut"],
                    fin=self.payload["fin"],
                )
            client = APIClient(SERVER_NAME="wave38-other.test")
            client.force_authenticate(self.reader)
            assert client.get(f"{URL}{event['id']}/").status_code == 403
            client.force_authenticate(local_reader)
            assert client.get(URL, BOUNDS).data["count"] == 0
            assert client.get(f"{URL}{event['id']}/").status_code == 404
            assert client.get(NOTIFICATIONS).data["count"] == 0
        finally:
            with schema_context("public"):
                with connection.cursor() as cursor:
                    cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")
                foreign._drop_schema(force_drop=True)
            connection.set_tenant(self.tenant)


class EventConcurrencyTests(EventFixture):
    @classmethod
    def _fixture_setup(cls):
        TransactionTestCase._fixture_setup.__func__(cls)

    def _fixture_teardown(self):
        with schema_context(self.tenant.schema_name):
            TransactionTestCase._fixture_teardown(self)

    def race(self, commands):
        assert not connection.in_atomic_block
        barrier = Barrier(len(commands))

        def submit(command):
            url, payload = command
            try:
                with schema_context(self.tenant.schema_name):
                    actor = self.users.objects.get(pk=self.manager.pk)
                    client = APIClient(SERVER_NAME=self.get_test_tenant_domain())
                    client.force_authenticate(actor)
                    barrier.wait(timeout=10)
                    response = client.post(url, payload, format="json")
                    return response.status_code
            finally:
                connections["default"].close()

        with ThreadPoolExecutor(max_workers=len(commands)) as pool:
            return list(pool.map(submit, commands))

    def test_simultaneous_creations_reserve_once_with_one_invitation_and_notification(self):
        assert sorted(self.race([(URL, self.payload), (URL, self.payload)])) == [201, 400]
        assert self.counts() == (1, 1, 1, 1)

    def test_concurrent_updates_cannot_overwrite_an_invitation_or_hour(self):
        event = self.create_event()
        url = f"{URL}{event['id']}/modifier/"
        payload = {**self.payload, "version": 1}
        assert sorted(
            self.race(
                [
                    (url, {**payload, "participants": [self.other.pk]}),
                    (url, {**payload, "debut": "2027-03-08T12:00:00+01:00", "fin": "2027-03-08T13:00:00+01:00"}),
                ]
            )
        ) == [200, 409]
        assert InstitutionalEvent.objects.get().version == 2
        assert WorkflowEvent.objects.count() == 2
        assert WorkflowNotification.objects.count() == 2

    def test_two_events_moving_into_one_room_serialize(self):
        event = self.create_event()
        second = self.create_event(salle=self.room2.pk)
        target = self.make_room("EV3", 10)
        commands = [
            (f"{URL}{item['id']}/modifier/", {**self.payload, "version": 1, "salle": target.pk})
            for item in (event, second)
        ]
        assert sorted(self.race(commands)) == [200, 400]
        assert InstitutionalEvent.objects.filter(salle=target).count() == 1

    def test_existing_reservation_writer_and_new_event_share_the_transaction_lock(self):
        barrier = Barrier(2)

        def reserve(legacy):
            try:
                with schema_context(self.tenant.schema_name):
                    barrier.wait(timeout=10)
                    if legacy:
                        try:
                            self.occupancy()
                            return 201
                        except ValidationError:
                            return 400
                    client = APIClient(SERVER_NAME=self.get_test_tenant_domain())
                    client.force_authenticate(self.users.objects.get(pk=self.manager.pk))
                    return client.post(URL, self.payload, format="json").status_code
            finally:
                connections["default"].close()

        with ThreadPoolExecutor(max_workers=2) as pool:
            assert sorted(pool.map(reserve, [True, False])) == [201, 400]
        assert InstitutionalEvent.objects.count() in (0, 1)
        assert WorkflowEvent.objects.count() == InstitutionalEvent.objects.count()
