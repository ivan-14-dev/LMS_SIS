from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError, transaction
from rest_framework.exceptions import APIException
from sis_provisioning.models import ManagedCourse


class Command(BaseCommand):
    help = "Explicitly bind an existing Studio course without granting authoring rights or changing its content."

    def add_arguments(self, parser):
        parser.add_argument("--manager", required=True)
        parser.add_argument("--course-id", required=True)
        parser.add_argument("--confirm", action="store_true")

    def handle(self, *args, **options):
        if settings.SERVICE_VARIANT != "cms":
            raise CommandError("Run this command in Studio with manage.py cms.")
        if not options["confirm"]:
            raise CommandError("Review the SIS course mapping and repeat with --confirm.")
        from sis_provisioning.course_views import (
            OWNERSHIP_FIELD,
            check_binding,
            check_manager,
            course_lock,
            has_studio_write_access,
            modulestore,
            ownership,
            parse_course_key,
        )

        try:
            key = parse_course_key(options["course_id"])
            with transaction.atomic():
                manager = get_user_model().objects.select_for_update().get(username=options["manager"], is_active=True)
                check_manager(manager, key)
                if not has_studio_write_access(manager, key):
                    raise CommandError("Grant this service course authoring access explicitly in Studio first.")
                course = modulestore().get_course(key)
                if course is None:
                    raise CommandError("The course must already exist.")
                binding = ManagedCourse.objects.filter(course_id=str(key)).first()
                if binding is None:
                    if OWNERSHIP_FIELD in course.other_course_settings:
                        raise CommandError("The existing ownership marker requires manual reconciliation.")
                    binding = ManagedCourse.objects.create(course_id=str(key), manager=manager, adopted=True)
                check_binding(binding, manager, key)
                if not binding.initialized and not binding.adopted:
                    raise CommandError("Resume the unfinished native provisioning before binding this course.")
            with course_lock(binding):
                manager = get_user_model().objects.get(pk=manager.pk)
                check_manager(manager, key)
                if not has_studio_write_access(manager, key):
                    raise CommandError("The service no longer has course authoring access.")
                binding = ManagedCourse.objects.get(pk=binding.pk)
                check_binding(binding, manager, key)
                course = modulestore().get_course(key)
                if course is None:
                    raise CommandError("The course no longer exists.")
                marker = course.other_course_settings.get(OWNERSHIP_FIELD)
                if marker != ownership(binding):
                    if marker is not None or binding.initialized:
                        raise CommandError("The existing ownership marker must not be replaced.")
                    course.other_course_settings = {**course.other_course_settings, OWNERSHIP_FIELD: ownership(binding)}
                    modulestore().update_item(course, manager.pk)
                binding.initialized = True
                binding.save(update_fields=["initialized", "updated_at"])
        except (APIException, IntegrityError, get_user_model().DoesNotExist) as error:
            raise CommandError(str(error)) from error
        self.stdout.write("Course explicitly bound; authoring rights and content preserved.")
