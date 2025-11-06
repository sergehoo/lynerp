# hr/auth_utils.py
from django.utils import timezone
from tenants.models import Tenant, License, SeatAssignment

def ensure_seat_for_user(tenant: Tenant, module: str, sub: str, email: str) -> bool:
    """Tente d’auto-attribuer un siège libre si possible. Retourne True si OK."""
    if SeatAssignment.objects.filter(tenant=tenant, module=module, user_sub=sub, active=True).exists():
        return True

    # Licence valide ?
    today = timezone.now().date()
    try:
        lic = License.objects.get(tenant=tenant, module=module, active=True, valid_until__gte=today)
    except License.DoesNotExist:
        return False

    # Sièges dispos ?
    if lic.available_seats <= 0:
        return False

    SeatAssignment.objects.create(
        tenant=tenant,
        license=lic,
        module=module,
        user_sub=sub,
        user_email=email,
        active=True,
        activated_at=timezone.now()
    )
    return True