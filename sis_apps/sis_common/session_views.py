from django.contrib.auth import authenticate, login, logout
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from sis_common.mfa import verify_code


class SessionCredentials(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)
    code = serializers.CharField(required=False, allow_blank=True)


@method_decorator(csrf_protect, name="dispatch")
class LocalSessionView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        if not request.user.is_authenticated:
            return Response({"authenticated": False})
        return Response(
            {
                "authenticated": True,
                "username": request.user.username,
                "role": request.user.role,
                "mfa_active": request.user.mfa_active,
            }
        )

    def post(self, request):
        serializer = SessionCredentials(data=request.data)
        serializer.is_valid(raise_exception=True)
        credentials = serializer.validated_data
        user = authenticate(
            request=request._request,
            username=credentials["username"],
            password=credentials["password"],
        )
        if user is None or not user.is_active or user.etablissement_id != request.tenant.pk:
            return Response({"detail": "Identifiants invalides."}, status=401)
        if user.mfa_active and not verify_code(user.mfa_secret, credentials.get("code", "")):
            return Response({"detail": "Code MFA requis ou invalide."}, status=401)
        login(request._request, user)
        return Response({"authenticated": True, "username": user.username, "role": user.role})

    def delete(self, request):
        logout(request._request)
        return Response({"authenticated": False})
