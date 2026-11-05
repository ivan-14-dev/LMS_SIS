import logging

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from rest_framework import serializers
from rest_framework.exceptions import APIException, NotFound, PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from .accounts import account_payload, create_account, update_profile
from .authentication import CanProvisionAccounts, ProvisioningAuthentication
from .models import ManagedAccount

logger = logging.getLogger(__name__)


class AccountConflict(APIException):
    status_code = 409
    default_detail = "An existing or revoked account requires an explicit administrative decision."
    default_code = "account_conflict"


class AccountFields(serializers.Serializer):
    email = serializers.EmailField(max_length=254)
    name = serializers.CharField(max_length=255)
    id = serializers.IntegerField(min_value=1, required=False)

    def to_internal_value(self, data):
        if not isinstance(data, dict) or set(data) - set(self.fields):
            raise ValidationError({"non_field_errors": ["Only email, name and the existing account id are accepted."]})
        return super().to_internal_value(data)


class AccountView(APIView):
    authentication_classes = [ProvisioningAuthentication]
    permission_classes = [CanProvisionAccounts]

    def post(self, request, username):
        return self._save(request, username, create=True)

    def patch(self, request, username):
        return self._save(request, username, create=False)

    def _save(self, request, username, *, create):
        fields = AccountFields(data=request.data)
        fields.is_valid(raise_exception=True)
        values = fields.validated_data
        if not create and "id" not in values:
            raise ValidationError({"id": "The existing LMS account id is required."})
        try:
            with transaction.atomic():
                manager = get_user_model().objects.select_for_update().get(pk=request.user.pk)
                if not manager.is_active or not manager.has_perm("sis_provisioning.provision_accounts"):
                    raise PermissionDenied()
                binding = ManagedAccount.objects.select_for_update().filter(username=username).first()
                created = binding is None
                if binding is None:
                    if not create:
                        raise NotFound("This account has not been explicitly bound to the SIS service.")
                    if "id" in values or get_user_model().objects.filter(username=username).exists():
                        raise AccountConflict()
                    user = create_account(username, values["email"], values["name"])
                    binding = ManagedAccount.objects.create(user=user, manager=manager, username=username)
                else:
                    if binding.manager_id != manager.pk:
                        raise PermissionDenied("This account belongs to another provisioning service.")
                    user = get_user_model().objects.select_for_update().get(pk=binding.user_id)
                    if (
                        user.username != username
                        or not user.is_active
                        or user.is_staff
                        or user.is_superuser
                        or ("id" in values and values["id"] != user.pk)
                    ):
                        raise AccountConflict()
                    update_profile(user, values["email"], values["name"])
                    binding.save(update_fields=["updated_at"])
                result = account_payload(user)
        except IntegrityError as error:
            logger.warning("SIS provisioning conflict for service id=%s", request.user.pk)
            raise AccountConflict() from error
        logger.info("SIS account provisioned service_id=%s account_id=%s created=%s", manager.pk, user.pk, created)
        return Response(result, status=201 if created else 200)
