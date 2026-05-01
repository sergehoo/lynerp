"""
Tests basiques module Projets.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from projects.models import (
    Phase,
    Project,
    ProjectStatus,
    Task,
    TaskStatus,
)

pytestmark = pytest.mark.django_db


def test_project_creation(tenant_a, user_a):
    p = Project.objects.create(
        tenant=tenant_a, code="DEMO", name="Projet démo",
        status=ProjectStatus.ACTIVE, project_manager=user_a,
        start_date=date.today(),
    )
    assert str(p) == "[DEMO] Projet démo"


def test_phase_uniqueness(tenant_a):
    p = Project.objects.create(
        tenant=tenant_a, code="P2", name="Test",
        status=ProjectStatus.DRAFT,
    )
    Phase.objects.create(tenant=tenant_a, project=p, name="Phase 1", order=1)
    with pytest.raises(Exception):
        Phase.objects.create(tenant=tenant_a, project=p, name="Phase 1 bis", order=1)


def test_task_lifecycle(tenant_a, user_a):
    p = Project.objects.create(
        tenant=tenant_a, code="P3", name="Test",
        status=ProjectStatus.ACTIVE,
    )
    t = Task.objects.create(
        tenant=tenant_a, project=p,
        title="Faire X", reporter=user_a,
        due_date=date.today() + timedelta(days=3),
        estimated_hours=Decimal("8"),
    )
    assert t.status == TaskStatus.TODO
    t.status = TaskStatus.DONE
    t.save()
    t.refresh_from_db()
    assert t.status == TaskStatus.DONE
