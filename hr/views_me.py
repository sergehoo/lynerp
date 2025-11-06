# hr/views_me.py
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django.utils import timezone
from tenants.models import Tenant, TenantUser, License, SeatAssignment

@api_view(["GET"])
def my_access(request):
    tenant_id = request.session.get("tenant_id") or request.headers.get("X-Tenant-Id")
    resp = {"rh": False, "reason": None}
    if not tenant_id or not request.user.is_authenticated:
        resp["reason"] = "not_authenticated_or_no_tenant"
        return Response(resp)

    try:
        tenant = Tenant.objects.get(id=tenant_id)
    except Tenant.DoesNotExist:
        resp["reason"] = "tenant_not_found"
        return Response(resp)

    if not TenantUser.objects.filter(tenant=tenant, user=request.user, is_active=True).exists():
        resp["reason"] = "membership_inactive"
        return Response(resp)

    today = timezone.now().date()
    lic = License.objects.filter(tenant=tenant, module="rh", active=True, valid_until__gte=today).first()
    if not lic:
        resp["reason"] = "no_valid_license"
        return Response(resp)

    payload = request.auth or {}
    sub = payload.get("sub")
    if not sub:
        resp["reason"] = "no_sub_in_token"
        return Response(resp)

    seat_ok = SeatAssignment.objects.filter(tenant=tenant, module="rh", user_sub=sub, active=True).exists()
    resp["rh"] = bool(seat_ok)
    resp["reason"] = None if seat_ok else "no_active_seat"
    return Response(resp)