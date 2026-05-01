"""
Helpers pour journaliser les événements IA (append-only).
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def log_event(
    *,
    tenant,
    event: str,
    actor=None,
    conversation=None,
    target_model: str = "",
    target_id: str = "",
    payload: Optional[Dict[str, Any]] = None,
    request=None,
) -> None:
    """
    Crée une entrée ``AIAuditLog``. Robuste : ne lève pas d'exception
    si la DB est indisponible (on log juste).
    """
    try:
        from ai_assistant.models import AIAuditLog

        ip = ""
        ua = ""
        if request is not None:
            ip = request.META.get("REMOTE_ADDR", "") or ""
            ua = request.META.get("HTTP_USER_AGENT", "") or ""

        AIAuditLog.objects.create(
            tenant=tenant,
            actor=actor if (actor and getattr(actor, "is_authenticated", False)) else None,
            conversation=conversation,
            event=event,
            target_model=target_model,
            target_id=target_id,
            payload=payload or {},
            ip_address=ip or None,
            user_agent=ua,
        )
    except Exception:  # noqa: BLE001
        logger.exception("AIAuditLog write failed for event=%s", event)
