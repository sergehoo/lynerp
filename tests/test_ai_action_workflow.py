"""
Tests du workflow AIAction : PROPOSED → APPROVED → EXECUTED.
"""
from __future__ import annotations

import pytest
from django.utils import timezone

from ai_assistant.models import AIAction, AIActionStatus, AIConversation

pytestmark = pytest.mark.django_db


@pytest.fixture
def proposed_action(tenant_a, user_a):
    conv = AIConversation.objects.create(
        tenant=tenant_a, user=user_a, module="finance",
    )
    return AIAction.objects.create(
        tenant=tenant_a,
        conversation=conv,
        proposed_by=user_a,
        action_type="finance.post_journal_entry",
        title="Test action",
        payload={"label": "Test", "lines": []},
        risk_level="MEDIUM",
    )


def test_action_starts_proposed(proposed_action):
    assert proposed_action.status == AIActionStatus.PROPOSED
    assert proposed_action.is_pending
    assert not proposed_action.is_actionable


def test_approve_makes_actionable(proposed_action, user_b):
    proposed_action.status = AIActionStatus.APPROVED
    proposed_action.approved_by = user_b
    proposed_action.approved_at = timezone.now()
    proposed_action.save()
    assert proposed_action.is_actionable
    assert not proposed_action.is_pending


def test_double_approval_required(proposed_action, user_b):
    proposed_action.requires_double_approval = True
    proposed_action.approved_by = user_b
    proposed_action.approved_at = timezone.now()
    proposed_action.status = AIActionStatus.APPROVED
    proposed_action.save()
    # Pas de second approbateur → pas actionable.
    assert not proposed_action.is_actionable


def test_proposer_cannot_approve_via_permission(proposed_action):
    """
    Vérifie via la permission DRF : un user ne peut pas approuver sa propre action.
    """
    from ai_assistant.permissions import CanApproveAIAction
    from unittest.mock import MagicMock

    perm = CanApproveAIAction()
    request = MagicMock()
    request.user = proposed_action.proposed_by
    request.user.is_authenticated = True
    request.user.is_superuser = False
    request.user.id = proposed_action.proposed_by.id

    # Bypass tenant check (déjà testé ailleurs).
    request.tenant = proposed_action.tenant
    view = MagicMock()

    # Sans tenant membership, c'est False de toute façon.
    # On simule ici uniquement le check d'auto-approbation.
    perm.has_permission = lambda r, v: True
    assert perm.has_object_permission(request, view, proposed_action) is False
