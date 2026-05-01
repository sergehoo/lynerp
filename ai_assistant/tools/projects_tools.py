"""Outils IA pour le module Projets."""
from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any, Dict

from ai_assistant.services.ollama import get_ollama
from ai_assistant.services.tool_registry import RISK_READ, get_tool_registry

logger = logging.getLogger(__name__)
registry = get_tool_registry()


@registry.tool(
    name="projects.summarize",
    description="Résume l'état d'un projet (avancement, jalons, risques).",
    risk=RISK_READ,
    schema={
        "type": "object",
        "properties": {"project_id": {"type": "string"}},
        "required": ["project_id"],
        "additionalProperties": False,
    },
    module="projects",
)
def summarize_project(*, tenant, user, project_id: str, **_) -> Dict[str, Any]:
    from projects.models import Project

    p = (
        Project.objects.filter(tenant=tenant, id=project_id)
        .prefetch_related("phases", "tasks", "milestones")
        .first()
    )
    if p is None:
        return {"error": "project_not_found"}

    payload = {
        "code": p.code, "name": p.name, "status": p.status,
        "progress": float(p.progress_percent),
        "start": p.start_date.isoformat() if p.start_date else None,
        "end": p.end_date.isoformat() if p.end_date else None,
        "phases_count": p.phases.count(),
        "tasks_count": p.tasks.count(),
        "milestones": [
            {"name": m.name, "target": m.target_date.isoformat() if m.target_date else None,
             "achieved": bool(m.achieved_at)}
            for m in p.milestones.all()
        ],
        "open_tasks_count": p.tasks.exclude(status__in=["DONE", "CANCELLED"]).count(),
        "overdue_tasks_count": p.tasks.filter(
            due_date__lt=date.today(),
        ).exclude(status__in=["DONE", "CANCELLED"]).count(),
    }

    msg = (
        "Résume ce projet en Markdown : avancement, points forts, points "
        "d'attention, risques, recommandations.\n\n"
        f"{payload}"
    )
    result = get_ollama().chat([
        {"role": "system", "content": "Tu es un chef de projet senior."},
        {"role": "user", "content": msg},
    ])
    return {
        "summary_markdown": result.get("content", ""),
        "stats": payload,
        "model": result.get("model"),
    }


@registry.tool(
    name="projects.priority_recommendations",
    description="Recommande quelles tâches prioriser dans les 7 jours.",
    risk=RISK_READ,
    schema={
        "type": "object",
        "properties": {
            "user_id": {"type": "string", "description": "User ciblé (par défaut, l'utilisateur courant)."},
            "horizon_days": {"type": "integer", "minimum": 1, "maximum": 30, "default": 7},
        },
        "additionalProperties": False,
    },
    module="projects",
)
def priority_recommendations(
    *,
    tenant,
    user,
    user_id: str | None = None,
    horizon_days: int = 7,
    **_,
) -> Dict[str, Any]:
    from django.contrib.auth import get_user_model

    from projects.models import Task, TaskStatus

    target_user = user
    if user_id:
        User = get_user_model()
        target_user = User.objects.filter(id=user_id).first() or user

    horizon = date.today() + timedelta(days=horizon_days)
    tasks = list(
        Task.objects.filter(
            tenant=tenant,
            assignees=target_user,
            due_date__lte=horizon,
        ).exclude(status__in=[TaskStatus.DONE, TaskStatus.CANCELLED])
        .select_related("project")
        .order_by("priority", "due_date")[:25]
    )
    if not tasks:
        return {"summary": "Aucune tâche urgente sur la période."}

    payload = [
        {
            "title": t.title, "project": t.project.code,
            "status": t.status, "priority": t.priority,
            "due_date": t.due_date.isoformat() if t.due_date else None,
            "estimated_hours": float(t.estimated_hours or 0),
        }
        for t in tasks
    ]
    msg = (
        f"Priorise ces tâches pour les {horizon_days} prochains jours. "
        "Donne un classement et un plan d'attaque court (Markdown).\n\n"
        f"{payload}"
    )
    result = get_ollama().chat([
        {"role": "system", "content": "Tu es un coach de productivité agile."},
        {"role": "user", "content": msg},
    ])
    return {
        "plan_markdown": result.get("content", ""),
        "tasks": payload,
        "model": result.get("model"),
    }
