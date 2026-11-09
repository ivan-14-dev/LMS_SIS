from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .authentication import ProvisioningAuthentication


class LMSCapabilitiesView(APIView):
    authentication_classes = [ProvisioningAuthentication]
    permission_classes = [IsAuthenticated]
    capabilities = {
        "accounts": "provision_accounts",
        "enrollments": "manage_enrollments",
        "teaching": "manage_teaching",
    }

    def get(self, request):
        return Response(
            {
                "contract": "sis-provisioning/v1",
                "capabilities": {
                    name: bool(request.user.is_active and request.user.has_perm(f"sis_provisioning.{permission}"))
                    for name, permission in self.capabilities.items()
                },
            }
        )


class CMSCapabilitiesView(LMSCapabilitiesView):
    capabilities = {"courses": "provision_courses", "publication": "publish_courses"}
