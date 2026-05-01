"""Services workflows : créer une demande, approuver/rejeter une étape."""
from __future__ import annotations

import logging
from typing import Any

from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.utils import timezone

from workflows.models import (
    ApprovalDecision,
    ApprovalRequest,
    ApprovalStatus,
    ApprovalStep,
    ApprovalWorkflow,
    AuditEvent,
    Notification,
    NotificationLevel,
)

logger = logging.getLogger(__name__)


def submit_for_approval(
    *,
    tenant,
    workflow: ApprovalWorkflow,
    requested_by,
    title: str,
    summary: str = "",
    target_obj: Any | None = None,
    payload: dict | None = None,
) -> ApprovalRequest:
    first_step = workflow.steps.order_by("order").first()
    req_kwargs = {
        "tenant": tenant,
        "workflow": workflow,
        "requested_by": requested_by,
        "title": title,
        "summary": summary,
        "payload": payload or {},
        "current_step": first_step,
        "status": ApprovalStatus.IN_PROGRESS if first_step else ApprovalStatus.PENDING,
    }
    if target_obj is not None:
        req_kwargs["content_type"] = ContentType.objects.get_for_model(type(target_obj))
        req_kwargs["object_id"] = str(target_obj.pk)
    return ApprovalRequest.objects.create(**req_kwargs)


@transaction.atomic
def approve_step(*, request: ApprovalRequest, decided_by, comment: str = "") -> ApprovalRequest:
    if request.status not in {ApprovalStatus.IN_PROGRESS, ApprovalStatus.PENDING}:
        raise ValueError("Demande déjà finalisée.")
    if not request.current_step:
        raise ValueError("Aucune étape courante.")

    ApprovalDecision.objects.create(
        tenant=request.tenant,
        request=request,
        step=request.current_step,
        decided_by=decided_by,
        decision="APPROVE",
        comment=comment,
    )

    next_step = (
        ApprovalStep.objects
        .filter(workflow=request.workflow, order__gt=request.current_step.order)
        .order_by("order")
        .first()
    )
    if next_step is None:
        request.status = ApprovalStatus.APPROVED
        request.current_step = None
        request.completed_at = timezone.now()
    else:
        request.current_step = next_step
    request.save()

    AuditEvent.objects.create(
        tenant=request.tenant,
        actor=decided_by,
        event_type="approval.step_approved",
        severity="MEDIUM",
        target_model="workflows.ApprovalRequest",
        target_id=str(request.id),
        description=f"Étape approuvée : {comment[:200]}",
    )
    return request


@transaction.atomic
def reject_step(*, request: ApprovalRequest, decided_by, comment: str = "") -> ApprovalRequest:
    if request.status not in {ApprovalStatus.IN_PROGRESS, ApprovalStatus.PENDING}:
        raise ValueError("Demande déjà finalisée.")
    ApprovalDecision.objects.create(
        tenant=request.tenant,
        request=request,
        step=request.current_step,
        decided_by=decided_by,
        decision="REJECT",
        comment=comment,
    )
    request.status = ApprovalStatus.REJECTED
    request.current_step = None
    request.completed_at = timezone.now()
    request.save()

    AuditEvent.objects.create(
        tenant=request.tenant,
        actor=decided_by,
        event_type="approval.rejected",
        severity="MEDIUM",
        target_model="workflows.ApprovalRequest",
        target_id=str(request.id),
        description=comment[:500],
    )
    return request


def notify(
    *,
    tenant,
    user,
    title: str,
    body: str = "",
    level: str = NotificationLevel.INFO,
    url: str = "",
    target_obj: Any | None = None,
) -> Notification:
    kwargs = {
        "tenant": tenant, "user": user,
        "title": title, "body": body,
        "level": level, "url": url,
    }
    if target_obj is not None:
        kwargs["content_type"] = ContentType.objects.get_for_model(type(target_obj))
        kwargs["object_id"] = str(target_obj.pk)
    return Notification.objects.create(**kwargs)
