# hr/auth_utils.py
from typing import Optional
from django.utils import timezone
from tenants.models import Tenant, License, SeatAssignment

def ensure_seat_for_user(tenant: Tenant, module: str, user_sub: str, user_email: str) -> Optional[SeatAssignment]:
    """
    Attribue automatiquement un siège si:
    - une licence active existe pour ce module
    - il reste des sièges disponibles
    Ne crée rien si déjà attribué.
    """
    if not (tenant and module and user_sub):
        return None

    # Déjà attribué ?
    existing = SeatAssignment.objects.filter(
        tenant=tenant, module=module, user_sub=user_sub, active=True
    ).select_related("license").first()
    if existing:
        return existing

    # Licence active (la plus “récente”)
    today = timezone.now().date()
    lic = (License.objects
           .filter(tenant=tenant, module=module, active=True, valid_until__gte=today)
           .order_by("-valid_until")
           .first())
    if not lic:
        return None

    # Capacité
    used = SeatAssignment.objects.filter(tenant=tenant, module=module, active=True).count()
    if used >= lic.seats:
        return None

    # Crée l’attribution liée à la licence
    return SeatAssignment.objects.create(
        tenant=tenant,
        license=lic,
        module=module,
        user_sub=user_sub,
        user_email=user_email or "",
        active=True,
        activated_at=timezone.now(),
    )