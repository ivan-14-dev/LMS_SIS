import secrets

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import ValidationError


def create_account(username, email, name):
    from common.djangoapps.student.helpers import AccountValidationError, do_create_account
    from openedx.core.djangoapps.user_authn.views.registration_form import AccountCreationForm

    form = AccountCreationForm(
        data={"username": username, "email": email, "name": name, "password": secrets.token_urlsafe(48)},
        tos_required=False,
    )
    try:
        user, profile, _registration = do_create_account(form)
    except DjangoValidationError as error:
        raise ValidationError(getattr(error, "message_dict", error.messages)) from error
    except AccountValidationError as error:
        raise ValidationError("The username or email cannot be provisioned.") from error
    # The administrator provisions access, not consent or a shared password.
    # The user must set their password through the native email recovery flow.
    user.is_active = True
    user.save(update_fields=["is_active"])
    return user


def update_profile(user, email, name):
    from common.djangoapps.student.models import email_exists_or_retired
    from openedx.core.djangoapps.user_authn.views.registration_form import validate_name

    try:
        validate_name(name)
    except DjangoValidationError as error:
        raise ValidationError({"name": error.messages}) from error
    if user.email.casefold() != email.casefold() and email_exists_or_retired(email):
        raise ValidationError({"email": "This email is already assigned or retired."})
    user.email = email
    user.save(update_fields=["email"])
    user.profile.name = name
    user.profile.save(update_fields=["name"])


def account_payload(user):
    return {
        "id": user.pk,
        "username": user.username,
        "email": user.email,
        "name": user.profile.name,
        "is_active": user.is_active,
        "is_staff": user.is_staff,
        "is_superuser": user.is_superuser,
    }
