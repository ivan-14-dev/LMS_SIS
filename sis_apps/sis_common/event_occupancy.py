"""One transaction lock for the agenda and the existing room occupancy writers."""

from datetime import UTC, datetime, time, timedelta

from django.apps import apps
from django.conf import settings
from django.db import connection, transaction
from django.utils import timezone
from django_tenants.utils import schema_context, schema_exists
from rest_framework.exceptions import ValidationError


def occupancy_lock():
    # Schema-local, transaction-scoped, including empty calendars and room swaps.
    # Writers must acquire this before any row lock, including academic parents.
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(current_schema() || ':institutional-room-occupancy', 0))"
        )


def room_model():
    return apps.get_model("salles" if settings.SIS_VARIANT == "secondaire" else "emplois_du_temps", "Salle")


def local_datetime(day, hour=time.min):
    return timezone.make_aware(datetime.combine(day, hour), timezone.get_default_timezone())


def overlaps(start, end, other_start, other_end):
    return start.astimezone(UTC) < other_end.astimezone(UTC) and end.astimezone(UTC) > other_start.astimezone(UTC)


def days_between(start, end, *, include_previous_day=False):
    day = timezone.localtime(start).date()
    if include_previous_day:
        day -= timedelta(days=1)
    last = timezone.localtime(end.astimezone(UTC) - timedelta(microseconds=1)).date()
    while day <= last:
        yield day
        day += timedelta(days=1)


def local_instants(day, hour):
    # Legacy wall times have no fold/offset: retain both interpretations at a
    # clock transition rather than silently declaring one of them available.
    wall = local_datetime(day, hour)
    return {wall.replace(fold=fold).astimezone(UTC) for fold in (0, 1)}


def dated_overlap(event, day, start=time.min, end=None, minutes=None):
    for left in local_instants(day, start):
        if minutes is not None:
            ends = (left + timedelta(minutes=minutes),)
        else:
            last_day = day + timedelta(days=1) if end is None or end <= start else day
            ends = local_instants(last_day, end or time.min)
        if any(left < right and overlaps(event.debut, event.fin, left, right) for right in ends):
            return True
    return False


def text_room_matches(label, room):
    """Unresolved nonempty legacy locations fail closed, never imply availability."""
    label = (label or "").strip().casefold()
    if not label:
        return False
    rooms = room_model().objects.all()
    if settings.SIS_VARIANT == "superieur":
        rooms = rooms.select_related("batiment")
    else:
        rooms = rooms.filter(etablissement_id=room.etablissement_id)
    matching = [
        item.pk
        for item in rooms
        if label in {item.code.strip().casefold(), item.nom.strip().casefold(), str(item).casefold()}
    ]
    return not matching or room.pk in matching


def course_overlaps(event, course):
    if settings.SIS_VARIANT == "secondaire":
        if not course.actif:
            return False
        start, end = course.heure_debut, course.heure_fin
        if course.date_specifique:
            return dated_overlap(event, course.date_specifique, start, end)
        period = course.classe.annee_scolaire
        weekday = course.jour - 1
    else:
        period = course.semestre
        weekday = course.jour
        start, end = course.creneau_horaire.heure_debut, course.creneau_horaire.heure_fin
    # Alternating/monthly week anchors are not defined consistently by the old
    # models. Conservatively occupy the matching weekday throughout the period.
    return any(
        period.date_debut <= day <= period.date_fin
        and day.weekday() == weekday
        and dated_overlap(event, day, start, end)
        for day in days_between(event.debut, event.fin, include_previous_day=True)
    )


def legacy_conflict(event):
    room = event.salle
    first = timezone.localtime(event.debut).date()
    last = timezone.localtime(event.fin.astimezone(UTC) - timedelta(microseconds=1)).date()
    secondary = settings.SIS_VARIANT == "secondaire"
    if secondary:
        unavailable = apps.get_model("salles", "IndisponibiliteSalle")
        if unavailable.objects.filter(salle=room, date_debut__lte=last, date_fin__gte=first).exists():
            return True
        courses = apps.get_model("emplois_du_temps", "Creneau").objects.filter(salle=room, actif=True)
        courses = courses.select_related("classe__annee_scolaire")
        constraints = apps.get_model("emplois_du_temps", "Contrainte").objects.filter(salle=room, type="indispo_salle")
        for item in constraints:
            if any(
                (item.jour is None or item.jour == day.isoweekday())
                and dated_overlap(event, day, item.heure_debut or time.min, item.heure_fin)
                for day in days_between(event.debut, event.fin, include_previous_day=True)
            ):
                return True
    else:
        if not room.disponible:
            return True
        courses = apps.get_model("emplois_du_temps", "CreneauCours").objects.filter(salle=room)
        courses = courses.select_related("semestre", "creneau_horaire")
        reservations = apps.get_model("emplois_du_temps", "Reservation").objects.filter(
            salle=room, statut="confirmee", date__range=(first - timedelta(days=1), last)
        )
        if any(dated_overlap(event, item.date, item.heure_debut, item.heure_fin) for item in reservations):
            return True
    if any(course_overlaps(event, item) for item in courses):
        return True

    exams = apps.get_model("examens", "EpreuveExamen").objects.filter(date__lte=last)
    for exam in exams:
        located = exam.salle_principale_id == room.pk if secondary else text_room_matches(exam.lieu, room)
        if not located:
            located = any(text_room_matches(label, room) for label in exam.convocations.values_list("salle", flat=True))
        if located and dated_overlap(event, exam.date, exam.heure_debut, minutes=exam.duree_minutes):
            return True
    if secondary:
        meetings = (
            apps.get_model("clubs", "SeanceClub")
            .objects.filter(date__range=(first - timedelta(days=1), last))
            .select_related("club")
        )
        for item in meetings:
            if text_room_matches(item.club.salle, room) and dated_overlap(
                event, item.date, item.heure_debut, item.heure_fin
            ):
                return True
        studies = apps.get_model("internat", "EtudeSurveillee").objects.filter(
            date__range=(first - timedelta(days=1), last)
        )
        for item in studies:
            if text_room_matches(item.salle, room) and dated_overlap(
                event, item.date, item.heure_debut, item.heure_fin
            ):
                return True
    else:
        juries = (
            apps.get_model("jurys", "Jury")
            .objects.exclude(statut="annule")
            .filter(date__gte=local_datetime(first), date__lt=local_datetime(last + timedelta(days=1)))
        )
        if any(text_room_matches(item.lieu, room) for item in juries):
            return True
        defenses = (
            apps.get_model("memoires", "SoutenanceMemoire").objects.exclude(statut="annulee").filter(date__lt=event.fin)
        )
        for item in defenses:
            if text_room_matches(item.lieu, room) and overlaps(
                event.debut, event.fin, item.date, item.date.astimezone(UTC) + timedelta(minutes=item.duree_minutes)
            ):
                return True
        library = (
            apps.get_model("bibliotheque", "ReservationSalle")
            .objects.filter(date__range=(first - timedelta(days=1), last))
            .select_related("salle")
        )
        for item in library:
            if text_room_matches(item.salle.nom, room) and dated_overlap(
                event, item.date, item.heure_debut, item.heure_fin
            ):
                return True
    return False


def room_conflict(event):
    events = (
        apps.get_model("core", "InstitutionalEvent")
        .objects.filter(salle=event.salle, statut="planifie", debut__lt=event.fin, fin__gt=event.debut)
        .exclude(pk=event.pk)
    )
    return events.exists() or legacy_conflict(event)


def validate_event_room(event):
    if event.effectif > event.salle.capacite:
        raise ValidationError({"effectif": "L'effectif dépasse la capacité de la salle."})
    if room_conflict(event):
        raise ValidationError({"salle": "La salle est occupée ou sa disponibilité ne peut pas être établie."})


def validate_existing_events():
    events = apps.get_model("core", "InstitutionalEvent").objects.filter(statut="planifie").select_related("salle")
    for event in events:
        wrong_owner = settings.SIS_VARIANT == "secondaire" and event.salle.etablissement_id != event.etablissement_id
        if wrong_owner or event.effectif > event.salle.capacite or legacy_conflict(event):
            raise ValidationError({"salle": "Cette modification empiète sur un événement institutionnel."})


class EventOccupancyGuard:
    """Existing writers retain their permissions, but cannot displace an event.

    Covers model save(), including admin and ordinary ORM creates/updates.
    QuerySet.update/bulk_create and external SQL are not reservation commands.
    """

    def save(self, *args, **kwargs):
        owner_path = None
        if self._meta.label_lower == "etablissement.anneescolaire":
            schema = self.etablissement.schema_name
            owner_path = "etablissement__schema_name"
        elif self._meta.label_lower == "etablissement.semestre":
            schema = self.annee_universitaire.universite.schema_name
            owner_path = "annee_universitaire__universite__schema_name"
        else:
            schema = connection.schema_name
        schemas = {schema}
        if owner_path:
            if self.pk:
                schemas.update(type(self).objects.filter(pk=self.pk).values_list(owner_path, flat=True))
            # Academic rows are shared and may precede their tenant schema.
            schemas = {name for name in schemas if name != "public" and schema_exists(name)}
        with transaction.atomic():
            for name in sorted(schemas):
                with schema_context(name):
                    occupancy_lock()
            result = super().save(*args, **kwargs)
            for name in sorted(schemas):
                with schema_context(name):
                    validate_existing_events()
            return result

    def delete(self, *args, **kwargs):
        if self._meta.label_lower not in ("salles.salle", "emplois_du_temps.salle", "emplois_du_temps.batiment"):
            return super().delete(*args, **kwargs)
        with transaction.atomic():
            occupancy_lock()
            result = super().delete(*args, **kwargs)
            # Deleting a name/code mapping can make another legacy location unresolved.
            validate_existing_events()
            return result
