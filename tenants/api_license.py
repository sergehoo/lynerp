"""
API ``/api/license/...`` :

- ``status/``       → état de la licence pour un tenant + module + user
- ``claim-seat/``   → attribution de siège JIT (si capacité disponible)

Les payloads sont conçus pour être consommés par le front RH (page d'accueil,
guard côté client).
"""
from __future__ import annotations

import logging
from datetime import date

from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import License, SeatAssignment, Tenant

logger = logging.getLogger(__name__)
DEFAULT_MODULE = "rh"


def _resolve_tenant(identifier: str | None):
    if not identifier:
        return None
    return (
        Tenant.objects
        .filter(slug=identifier).first()
        or Tenant.objects.filter(id=identifier).first()
    )


def _license_status_payload(
    lic: License | None,
    tenant: Tenant,
    module: str,
    user_sub: str | None,
) -> dict:
    today = date.today()
    active = bool(
        lic
        and lic.active
        and lic.valid_until
        and lic.valid_until >= today
    )
    seats_used = (
        SeatAssignment.objects
        .filter(tenant=tenant, module=module, active=True)
        .count()
        if active
        else 0
    )
    user_entitled = False
    if active and user_sub:
        user_entitled = SeatAssignment.objects.filter(
            tenant=tenant, module=module, user_sub=user_sub, active=True,
        ).exists()
    seats_total = lic.seats if lic else 0
    return {
        "active": active,
        "plan": getattr(lic, "plan", None),
        "valid_until": getattr(lic, "valid_until", None),
        "seats_total": seats_total,
        "seats_used": seats_used,
        "seats_available": max(seats_total - seats_used, 0),
        "user_entitled": user_entitled,
        "jit_allowed": active and seats_used < seats_total,
        "module": module,
        "tenant_id": str(tenant.id),
        "tenant_slug": tenant.slug,
    }


class LicenseStatusView(APIView):
    """
    GET ``/api/license/status/?tenant=<slug|uuid>&module=rh&user_sub=<sub>``

    Endpoint public (pas d'IsAuthenticated) car appelé par le front au moment
    du login pour conditionner la redirection. La licence ne peut pas être
    octroyée par un statut frauduleux (lecture seule).
    """

    permission_classes = [permissions.AllowAny]

    def get(self, request):
        tenant_identifier = request.query_params.get("tenant")
        module = request.query_params.get("module") or DEFAULT_MODULE
        user_sub = request.query_params.get("user_sub")

        tenant = _resolve_tenant(tenant_identifier)
        if tenant is None:
            return Response(
                {"detail": "Tenant introuvable.", "code": "tenant_not_found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        lic = (
            License.objects
            .filter(tenant=tenant, module=module)
            .order_by("-valid_until")
            .first()
        )
        return Response(_license_status_payload(lic, tenant, module, user_sub))


class LicenseClaimSeatView(APIView):
    """
    POST ``/api/license/claim-seat/`` body : ``{tenant, module, user_sub}``

    Attribue un siège à l'utilisateur si la licence est active et qu'il
    reste de la capacité.
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        data = request.data or {}
        tenant_identifier = data.get("tenant")
        module = data.get("module") or DEFAULT_MODULE
        user_sub = data.get("user_sub")

        if not tenant_identifier or not user_sub:
            return Response(
                {"detail": "tenant et user_sub sont requis.", "code": "missing_params"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        tenant = _resolve_tenant(tenant_identifier)
        if tenant is None:
            return Response(
                {"detail": "Tenant introuvable.", "code": "tenant_not_found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        lic = (
            License.objects
            .filter(tenant=tenant, module=module)
            .order_by("-valid_until")
            .first()
        )
        payload = _license_status_payload(lic, tenant, module, user_sub)

        if not payload["active"]:
            return Response(
                {"detail": "Licence invalide ou expirée.", "code": "license_invalid"},
                status=status.HTTP_403_FORBIDDEN,
            )
        if payload["user_entitled"]:
            return Response({**payload, "user_entitled": True})
        if not payload["jit_allowed"]:
            return Response(
                {"detail": "Aucun siège disponible.", "code": "seats_exhausted"},
                status=status.HTTP_403_FORBIDDEN,
            )

        SeatAssignment.objects.get_or_create(
            tenant=tenant,
            license=lic,
            module=module,
            user_sub=user_sub,
            defaults={
                "user_email": (request.user.email if request.user.is_authenticated else ""),
                "active": True,
                "activated_at": timezone.now(),
            },
        )
        # On recompte après l'insertion.
        new_payload = _license_status_payload(lic, tenant, module, user_sub)
        return Response(new_payload)
