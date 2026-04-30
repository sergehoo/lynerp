"""
Vue ``/api/auth/exchange/``.

Cas d'usage : un client SPA récupère un access token via le flow standard
(Authorization Code + PKCE) puis appelle cet endpoint avec le Bearer pour
matérialiser une session Django (cookie). On vérifie alors :

1. La signature du JWT Keycloak (via ``KeycloakJWTAuthentication``).
2. L'existence d'un ``TenantUser`` actif sur le tenant courant.
3. La licence/siège : on tente d'attribuer un siège JIT si nécessaire.

Si tout OK, on `login()` l'utilisateur dans la session locale.
"""
from __future__ import annotations

import logging

from django.contrib.auth import get_user_model, login as dj_login
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .auth import KeycloakJWTAuthentication
from .auth_utils import ensure_seat_for_user
from tenants.models import TenantUser

logger = logging.getLogger(__name__)
User = get_user_model()


class ExchangeTokenView(APIView):
    """
    POST ``/api/auth/exchange/`` (header ``Authorization: Bearer <jwt>``).

    Crée/synchronise le user local + valide le tenant + matérialise une session.
    """

    authentication_classes = [KeycloakJWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        claims = request.auth or {}
        sub = claims.get("sub")
        email = claims.get("email") or claims.get("preferred_username") or sub
        username = email or sub
        if not username:
            return Response(
                {"detail": "Token Keycloak invalide.", "code": "invalid_token"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        first = claims.get("given_name") or ""
        last = claims.get("family_name") or ""

        user, _created = User.objects.get_or_create(
            username=username,
            defaults={"email": email or "", "first_name": first, "last_name": last},
        )
        update_fields = []
        if email and user.email != email:
            user.email = email
            update_fields.append("email")
        if first and user.first_name != first:
            user.first_name = first
            update_fields.append("first_name")
        if last and user.last_name != last:
            user.last_name = last
            update_fields.append("last_name")
        if update_fields:
            user.save(update_fields=update_fields)

        # Validation tenant
        tenant = getattr(request, "tenant", None)
        if tenant is None:
            return Response(
                {"detail": "Organisation manquante.", "code": "tenant_required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not user.is_superuser:
            membership = (
                TenantUser.objects
                .filter(user=user, tenant=tenant, is_active=True)
                .first()
            )
            if membership is None:
                logger.info(
                    "Exchange refusé : user=%s pas membre du tenant=%s",
                    user.pk,
                    tenant.slug,
                )
                return Response(
                    {
                        "detail": "Vous n'avez pas accès à cette organisation.",
                        "code": "tenant_access_denied",
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )

        # Siège JIT (silencieux, ne casse pas la session si erreur)
        try:
            if sub:
                ensure_seat_for_user(tenant, "rh", sub, user.email)
        except Exception:  # noqa: BLE001
            logger.exception("ensure_seat_for_user failed for user=%s", user.pk)

        # Matérialise la session
        user.backend = "django.contrib.auth.backends.ModelBackend"
        dj_login(request, user)

        return Response(
            {
                "ok": True,
                "user": {
                    "username": user.username,
                    "email": user.email,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                },
                "tenant": {"id": str(tenant.id), "slug": tenant.slug, "name": tenant.name},
            }
        )
