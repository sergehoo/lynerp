"""
Context processors LYNEERP.

- ``current_tenant`` : expose ``request.tenant`` dans tous les templates
  (slug, id, instance).
- Expose aussi ``DEBUG`` (bascule CDN/build local) et les compteurs des
  badges sidebar (notifications non lues, actions IA en attente, demandes
  d'approbation en cours).

Tous les compteurs sont calculés best-effort : si une app n'est pas
disponible (tests, fresh install), on retombe sur 0 sans casser le rendu.
"""
from __future__ import annotations

from django.conf import settings


def current_tenant(request):
    tenant = getattr(request, "tenant", None)
    user = getattr(request, "user", None)

    unread_notifications = 0
    pending_ai_actions = 0
    pending_approvals = 0
    if tenant is not None and user is not None and getattr(user, "is_authenticated", False):
        try:
            from workflows.models import Notification

            unread_notifications = Notification.objects.filter(
                tenant=tenant, user=user, read_at__isnull=True,
            ).count()
        except Exception:  # noqa: BLE001
            pass
        try:
            from ai_assistant.models import AIAction, AIActionStatus

            pending_ai_actions = AIAction.objects.filter(
                tenant=tenant, status=AIActionStatus.PROPOSED,
            ).count()
        except Exception:  # noqa: BLE001
            pass
        try:
            from workflows.models import ApprovalRequest, ApprovalStatus

            pending_approvals = ApprovalRequest.objects.filter(
                tenant=tenant,
                status__in=[ApprovalStatus.PENDING, ApprovalStatus.IN_PROGRESS],
            ).count()
        except Exception:  # noqa: BLE001
            pass

    return {
        "current_tenant": tenant,
        "current_tenant_slug": getattr(tenant, "slug", None) if tenant else None,
        "current_tenant_id": str(getattr(tenant, "id", "")) if tenant else "",
        "DEBUG": bool(getattr(settings, "DEBUG", False)),
        # Compteurs sidebar
        "lyneerp_unread_notifications": unread_notifications,
        "lyneerp_pending_ai_actions": pending_ai_actions,
        "lyneerp_pending_approvals": pending_approvals,
    }
