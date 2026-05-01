"""
Tests workflows : workflow d'approbation, notifications, audit.
"""
from __future__ import annotations

import pytest

from workflows.models import (
    ApprovalStatus,
    ApprovalStep,
    ApprovalWorkflow,
    AuditEvent,
    Notification,
    NotificationLevel,
)
from workflows.services import (
    approve_step,
    notify,
    reject_step,
    submit_for_approval,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def sample_workflow(tenant_a):
    wf = ApprovalWorkflow.objects.create(
        tenant=tenant_a,
        code="TEST_WF",
        name="Workflow de test",
        target_model="inventory.PurchaseOrder",
    )
    ApprovalStep.objects.create(
        tenant=tenant_a, workflow=wf,
        order=1, name="Manager", role_required="MANAGER",
    )
    ApprovalStep.objects.create(
        tenant=tenant_a, workflow=wf,
        order=2, name="Direction", role_required="ADMIN",
    )
    return wf


def test_submit_creates_request_at_first_step(sample_workflow, tenant_a, user_a):
    req = submit_for_approval(
        tenant=tenant_a, workflow=sample_workflow,
        requested_by=user_a,
        title="Test request",
    )
    assert req.status == ApprovalStatus.IN_PROGRESS
    assert req.current_step is not None
    assert req.current_step.order == 1


def test_approve_advances_to_next_step(sample_workflow, tenant_a, user_a, user_b):
    req = submit_for_approval(
        tenant=tenant_a, workflow=sample_workflow,
        requested_by=user_a, title="Test",
    )
    approve_step(request=req, decided_by=user_b, comment="OK étape 1")
    req.refresh_from_db()
    assert req.status == ApprovalStatus.IN_PROGRESS
    assert req.current_step.order == 2

    approve_step(request=req, decided_by=user_b, comment="OK étape 2")
    req.refresh_from_db()
    assert req.status == ApprovalStatus.APPROVED
    assert req.current_step is None
    assert req.completed_at is not None


def test_reject_terminates_request(sample_workflow, tenant_a, user_a, user_b):
    req = submit_for_approval(
        tenant=tenant_a, workflow=sample_workflow,
        requested_by=user_a, title="Test",
    )
    reject_step(request=req, decided_by=user_b, comment="Non conforme")
    req.refresh_from_db()
    assert req.status == ApprovalStatus.REJECTED
    assert req.completed_at is not None


def test_audit_event_created_on_approve(sample_workflow, tenant_a, user_a, user_b):
    req = submit_for_approval(
        tenant=tenant_a, workflow=sample_workflow,
        requested_by=user_a, title="Test",
    )
    approve_step(request=req, decided_by=user_b)
    assert AuditEvent.objects.filter(
        tenant=tenant_a, event_type="approval.step_approved",
    ).exists()


def test_notify_creates_in_app_notification(tenant_a, user_a):
    n = notify(
        tenant=tenant_a, user=user_a,
        title="Test notif", body="Hello",
        level=NotificationLevel.INFO,
    )
    assert n.read_at is None
    assert Notification.objects.filter(tenant=tenant_a, user=user_a).count() == 1
