# hr/views_auth.py
from django.contrib.auth import get_user_model, login
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions
from .auth import KeycloakJWTAuthentication  # ton fichier hr/auth.py

User = get_user_model()


class ExchangeTokenView(APIView):
    authentication_classes = [KeycloakJWTAuthentication]  # vérifie le Bearer JWT
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        claims = request.auth or {}
        sub = claims.get("sub")
        email = claims.get("email") or claims.get("preferred_username") or sub
        username = email or sub

        # Crée/maj l'utilisateur local
        user, _ = User.objects.get_or_create(
            username=username,
            defaults={"email": email or ""}
        )
        # Optionnel: MAJ nom, email, etc.

        # Force un backend pour login()
        user.backend = "django.contrib.auth.backends.ModelBackend"
        login(request, user)

        return Response({"ok": True, "user": {"username": user.username}})
