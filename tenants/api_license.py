# tenants/api_license.py
from __future__ import annotations

from datetime import date
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from .models import License, SeatAssignment, Tenant

MODULE_PARAM = "rh"  # ou lis le module depuis settings/env


def _license_status_payload(lic: License, tenant_slug: str, module: str, user_sub: str | None):
    today = date.today()
    active = bool(lic and lic.active and lic.valid_until and lic.valid_until >= today)
    seats_used = SeatAssignment.objects.filter(
        tenant=tenant_slug, module=module, active=True
    ).count() if active else 0
    user_entitled = False
    if active and user_sub:
        user_entitled = SeatAssignment.objects.filter(
            tenant=tenant_slug, module=module, user_sub=user_sub, active=True
        ).exists()
    return {
        "active": active,
        "plan": getattr(lic, "plan", None),
        "valid_until": getattr(lic, "valid_until", None),
        "seats_total": getattr(lic, "seats", 0) if lic else 0,
        "seats_used": seats_used,
        "user_entitled": user_entitled,
        "jit_allowed": active and seats_used < (lic.seats if lic else 0),
        "module": module,
        "tenant": tenant_slug,
    }


class LicenseStatusView(APIView):
    """
    GET /api/rh/license/status/?tenant=<slug>&module=rh&user_sub=<sub>
    """
    permission_classes = [permissions.AllowAny]  # endpoint public (ton check se fait côté vues protégées)

    def get(self, request):
        tenant_slug = request.query_params.get("tenant")
        module = request.query_params.get("module") or MODULE_PARAM
        user_sub = request.query_params.get("user_sub")

        if not tenant_slug:
            return Response({"detail": "tenant requis"}, status=400)

        lic = License.objects.filter(tenant=tenant_slug, module=module).order_by("-valid_until").first()
        payload = _license_status_payload(lic, tenant_slug, module, user_sub)
        return Response(payload, status=200)


class LicenseClaimSeatView(APIView):
    """
    POST /api/rh/license/claim-seat
    body: {tenant, module, user_sub}
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        data = request.data or {}
        tenant_slug = data.get("tenant")
        module = data.get("module") or MODULE_PARAM
        user_sub = data.get("user_sub")

        if not (tenant_slug and user_sub):
            return Response({"detail": "tenant et user_sub requis"}, status=400)

        lic = License.objects.filter(tenant=tenant_slug, module=module).order_by("-valid_until").first()
        status_payload = _license_status_payload(lic, tenant_slug, module, user_sub)

        if not status_payload["active"]:
            return Response({"detail": "Licence RH invalide ou expirée"}, status=403)

        if status_payload["user_entitled"]:
            return Response({**status_payload, "user_entitled": True}, status=200)

        if not status_payload["jit_allowed"]:
            return Response({"detail": "Aucun siège disponible"}, status=403)

        SeatAssignment.objects.get_or_create(
            tenant=tenant_slug, module=module, user_sub=user_sub,
            defaults={"active": True, "activated_at": timezone.now()}
        )
        status_payload["user_entitled"] = True
        status_payload["seats_used"] += 1
        return Response(status_payload, status=200)
