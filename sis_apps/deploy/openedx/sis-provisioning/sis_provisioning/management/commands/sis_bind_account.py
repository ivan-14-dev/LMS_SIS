from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from sis_provisioning.models import ManagedAccount


class Command(BaseCommand):
    help = "Bind an existing non-privileged LMS account to an authorized SIS service."

    def add_arguments(self, parser):
        parser.add_argument("--manager", required=True)
        parser.add_argument("--username", required=True)
        parser.add_argument("--confirm", action="store_true")

    @transaction.atomic
    def handle(self, *args, **options):
        if not options["confirm"]:
            raise CommandError("Review the SIS mapping and repeat with --confirm.")
        users = get_user_model().objects.select_for_update()
        try:
            manager = users.get(username=options["manager"], is_active=True)
            user = users.get(username=options["username"], is_active=True)
        except get_user_model().DoesNotExist as error:
            raise CommandError("Both accounts must exist and be active.") from error
        if not manager.has_perm("sis_provisioning.provision_accounts"):
            raise CommandError("The service account lacks the provisioning permission.")
        if user.is_staff or user.is_superuser or user.pk == manager.pk:
            raise CommandError("Privileged accounts cannot be adopted.")
        if ManagedAccount.objects.filter(username=user.username).exclude(user=user).exists():
            raise CommandError("The original binding must not be replaced.")
        binding, created = ManagedAccount.objects.get_or_create(
            user=user,
            defaults={"manager": manager, "username": user.username},
        )
        if binding.manager_id != manager.pk or binding.username != user.username:
            raise CommandError("The existing owner or username must not be changed.")
        self.stdout.write("Account explicitly bound." if created else "Binding already exists.")
