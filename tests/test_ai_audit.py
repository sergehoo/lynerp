"""
Audit IA : les événements sensibles sont bien tracés.
"""
from __future__ import annotations

import pytest

from ai_assistant.models import AIAuditEvent, AIAuditLog
from ai_assistant.services.audit import log_event

pytestmark = pytest.mark.django_db


def test_log_event_persists(tenant_a, user_a):
    log_event(
        tenant=tenant_a,
        actor=user_a,
        event=AIAuditEvent.PROMPT_SENT,
        target_model="ai_assistant.AIMessage",
        target_id="abc-123",
        payload={"length": 42},
    )
    log = AIAuditLog.objects.filter(tenant=tenant_a).first()
    assert log is not None
    assert log.event == AIAuditEvent.PROMPT_SENT
    assert log.payload["length"] == 42


def test_log_event_robust_to_db_error(tenant_a, monkeypatch):
    """log_event ne lève JAMAIS d'exception, même si la DB est en panne."""
    from ai_assistant import services

    def boom(*args, **kwargs):
        raise RuntimeError("DB down")

    monkeypatch.setattr(AIAuditLog.objects, "create", boom)
    # Ne doit pas lever
    log_event(
        tenant=tenant_a, event=AIAuditEvent.PROMPT_SENT,
        payload={},
    )
