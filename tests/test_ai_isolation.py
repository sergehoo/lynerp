"""
Tests garde-fou : le module IA respecte l'isolation multi-tenant.
"""
from __future__ import annotations

import pytest

from ai_assistant.models import AIConversation, AIMessage, AIMessageRole

pytestmark = pytest.mark.django_db


def test_conversation_isolated_per_tenant(tenant_a, tenant_b, user_a):
    """Un user ne voit que les conversations de SON tenant."""
    conv_a = AIConversation.objects.create(
        tenant=tenant_a, user=user_a, module="general", title="A1",
    )
    AIConversation.objects.create(
        tenant=tenant_b, user=user_a, module="general", title="B1",
    )

    visible = AIConversation.objects.filter(tenant=tenant_a, user=user_a)
    assert list(visible) == [conv_a]


def test_message_count(tenant_a, user_a):
    conv = AIConversation.objects.create(
        tenant=tenant_a, user=user_a, module="hr",
    )
    for i in range(3):
        AIMessage.objects.create(
            tenant=tenant_a, conversation=conv,
            role=AIMessageRole.USER, content=f"q{i}",
        )
    assert conv.message_count == 3
