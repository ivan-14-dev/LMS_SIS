"""Explicit, repeatable provisioning for the first institution."""

import getpass
import json
import re
import sys
from pathlib import Path

from django.apps import apps
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management import BaseCommand, CommandError, call_command
from django.core.validators import validate_email
from django.db import transaction
from django_tenants.utils import (
    get_tenant_domain_model,
    get_tenant_model,
    schema_context,
    tenant_context,
)


class BootstrapInstitutionCommand(BaseCommand):
    help = "Create an institution, its domain and administrator without resetting existing accounts."

    def add_arguments(self, parser):
        configuration = parser.add_mutually_exclusive_group(required=True)
        configuration.add_argument("--config", type=Path)
        configuration.add_argument(
            "--config-stdin", action="store_true", help="Read one JSON line before the password."
        )
        parser.add_argument("--password-stdin", action="store_true")

    def handle(self, *args, **options):
        try:
            configuration = json.loads(
                sys.stdin.readline() if options["config_stdin"] else options["config"].read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError) as exc:
            raise CommandError(f"Cannot read institution configuration: {exc}") from exc
        if not isinstance(configuration, dict):
            raise CommandError("Institution configuration must be a JSON object.")
        schema = configuration.get("schema_name", "")
        domain = configuration.get("domain", "")
        institution = configuration.get("institution")
        administrator = configuration.get("admin")
        if not isinstance(schema, str) or not re.fullmatch(r"[a-z][a-z0-9_]{0,62}", schema) or schema == "public":
            raise CommandError("schema_name must be a non-public lowercase PostgreSQL identifier.")
        if not isinstance(domain, str) or not re.fullmatch(r"[a-zA-Z0-9](?:[a-zA-Z0-9.-]*[a-zA-Z0-9])?", domain):
            raise CommandError("domain must be a hostname without scheme, port or path.")
        domain = domain.lower()
        if not isinstance(institution, dict) or not isinstance(administrator, dict):
            raise CommandError("institution and admin must be JSON objects.")
        username = administrator.get("username", "")
        email = administrator.get("email", "")
        if not isinstance(username, str) or not isinstance(email, str):
            raise CommandError("Administrator username and email must be strings.")
        if "edx_username" in administrator and not isinstance(administrator["edx_username"], str):
            raise CommandError("edx_username must be a string.")
        user_model = get_user_model()
        try:
            user_model._meta.get_field("username").clean(username, None)
            validate_email(email)
        except ValidationError as exc:
            raise CommandError(str(exc)) from exc

        tenant_model = get_tenant_model()
        allowed_fields = {
            field.name
            for field in tenant_model._meta.fields
            if field.editable and not field.primary_key and field.name != "schema_name"
        }
        if set(institution) - allowed_fields:
            raise CommandError("Unknown or protected institution fields.")

        call_command(
            "migrate_schemas",
            shared=True,
            interactive=False,
            verbosity=options["verbosity"],
        )
        with schema_context("public"):
            domain_model = get_tenant_domain_model()
            registered_domain = domain_model.objects.filter(domain=domain).select_related("tenant").first()
            if registered_domain and registered_domain.tenant.schema_name != schema:
                raise CommandError("This domain already belongs to another institution.")
            tenant = tenant_model.objects.filter(schema_name=schema).first()
            if tenant and tenant.nom != institution.get("nom"):
                raise CommandError("This schema already belongs to an institution with a different name.")
            if tenant is None:
                tenant = tenant_model(schema_name=schema, **institution)
                try:
                    tenant.full_clean()
                except ValidationError as exc:
                    raise CommandError(str(exc)) from exc
                tenant.save()
            else:
                call_command(
                    "migrate_schemas",
                    schema_name=schema,
                    interactive=False,
                    verbosity=options["verbosity"],
                )
            domain_model.objects.get_or_create(domain=domain, defaults={"tenant": tenant, "is_primary": True})

        with tenant_context(tenant):
            with transaction.atomic():
                user = user_model.objects.filter(username=username).first()
                if user and (not user.is_superuser or user.etablissement_id != tenant.pk or user.email != email):
                    raise CommandError(
                        "Existing account does not match the requested administrator; refusing to alter it."
                    )
                if user is None:
                    password = (
                        sys.stdin.readline().rstrip("\r\n")
                        if options["password_stdin"]
                        else getpass.getpass("Administrator password (never written to configuration): ")
                    )
                    user = user_model(
                        username=username,
                        email=email,
                        etablissement=tenant,
                        role="super_admin",
                        is_staff=True,
                        is_superuser=True,
                    )
                    try:
                        validate_password(password, user)
                    except ValidationError as exc:
                        raise CommandError(str(exc)) from exc
                    user.set_password(password)
                    user.save()
                if administrator.get("edx_username"):
                    mapping_model = apps.get_model("integration", "EdxUserMapping")
                    mapping = mapping_model.objects.filter(user_sis=user).first()
                    edx_username = administrator["edx_username"]
                    if mapping and mapping.username_edx != edx_username:
                        raise CommandError("The administrator is already mapped to a different LMS account.")
                    conflicting = (
                        mapping_model.objects.filter(username_edx=edx_username).exclude(user_sis=user).exists()
                    )
                    if conflicting:
                        raise CommandError("The LMS account is already associated with another SIS user.")
                    mapping_model.objects.get_or_create(
                        user_sis=user,
                        defaults={
                            "username_edx": edx_username,
                            "user_id_edx": administrator.get("edx_user_id"),
                        },
                    )
        self.stdout.write(self.style.SUCCESS(f"Institution ready: {schema} ({domain}); administrator: {username}"))
