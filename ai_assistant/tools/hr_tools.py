"""
Outils IA pour le module RH.

Les outils ``read`` s'exécutent immédiatement. Les outils ``write`` (création
d'employé, validation de contrat, etc.) doivent passer par ``AIAction`` —
ils ne sont pas exposés ici tant que le workflow d'approbation n'est pas
mature.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List

from django.utils import timezone

from ai_assistant.services.ollama import get_ollama
from ai_assistant.services.prompt_registry import get_prompt_registry
from ai_assistant.services.tool_registry import (
    RISK_READ,
    get_tool_registry,
)

logger = logging.getLogger(__name__)
registry = get_tool_registry()


# --------------------------------------------------------------------------- #
# Lecture
# --------------------------------------------------------------------------- #
@registry.tool(
    name="hr.list_open_recruitments",
    description="Liste les recrutements actifs (status OPEN/IN_REVIEW/INTERVIEW/OFFER).",
    risk=RISK_READ,
    schema={
        "type": "object",
        "properties": {
            "limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 10},
        },
        "additionalProperties": False,
    },
    module="hr",
)
def list_open_recruitments(*, tenant, user, limit: int = 10, **_) -> Dict[str, Any]:
    from hr.models import Recruitment

    qs = Recruitment.objects.filter(
        tenant=tenant,
        status__in=["OPEN", "IN_REVIEW", "INTERVIEW", "OFFER"],
    ).select_related("department", "position").order_by("-publication_date")[:limit]

    return {
        "count": qs.count() if hasattr(qs, "count") else len(qs),
        "recruitments": [
            {
                "id": str(r.id),
                "title": r.title,
                "status": r.status,
                "department": getattr(r.department, "name", None),
                "position": getattr(r.position, "title", None),
                "publication_date": r.publication_date.isoformat()
                if r.publication_date else None,
            }
            for r in qs
        ],
    }


@registry.tool(
    name="hr.candidate_summary",
    description="Renvoie un résumé synthétique d'une candidature (sans données médicales).",
    risk=RISK_READ,
    schema={
        "type": "object",
        "properties": {
            "application_id": {"type": "string"},
        },
        "required": ["application_id"],
        "additionalProperties": False,
    },
    module="hr",
)
def candidate_summary(*, tenant, user, application_id: str, **_) -> Dict[str, Any]:
    from hr.models import JobApplication

    app = (
        JobApplication.objects
        .filter(tenant_id__in=[str(tenant.id), tenant.slug], id=application_id)
        .select_related("recruitment")
        .first()
    )
    if app is None:
        return {"error": "not_found"}
    return {
        "id": str(app.id),
        "name": f"{app.first_name} {app.last_name}".strip(),
        "email": app.email,
        "status": app.status,
        "ai_score": app.ai_score,
        "applied_at": app.applied_at.isoformat() if app.applied_at else None,
        "recruitment": getattr(app.recruitment, "title", None),
    }


# --------------------------------------------------------------------------- #
# Analyse de CV (read-only sur la DB, mais appelle Ollama)
# --------------------------------------------------------------------------- #
@registry.tool(
    name="hr.analyze_resume",
    description=(
        "Analyse un CV et renvoie un JSON structuré : compétences, "
        "expériences, score de fit, points forts, points d'attention."
    ),
    risk=RISK_READ,
    schema={
        "type": "object",
        "properties": {
            "application_id": {"type": "string"},
            "resume_text": {"type": "string"},
        },
        "additionalProperties": False,
    },
    module="hr",
)
def analyze_resume(
    *,
    tenant,
    user,
    application_id: str | None = None,
    resume_text: str | None = None,
    **_,
) -> Dict[str, Any]:
    from hr.models import JobApplication

    text = resume_text or ""
    job_title = ""
    job_description = ""
    required_skills: List[str] = []

    if application_id:
        app = JobApplication.objects.filter(
            tenant_id__in=[str(tenant.id), tenant.slug],
            id=application_id,
        ).select_related("recruitment").first()
        if app is None:
            return {"error": "application_not_found"}

        if not text and app.cv:
            try:
                text = _extract_text_from_file(app.cv)
            except Exception:  # noqa: BLE001
                logger.exception("Failed to extract CV text")

        if app.recruitment:
            job_title = app.recruitment.title
            job_description = (
                getattr(app.recruitment, "job_description", "") or ""
            )[:4000]
            try:
                required_skills = list(
                    app.recruitment.requirements.get("skills", [])
                ) if isinstance(app.recruitment.requirements, dict) else []
            except Exception:  # noqa: BLE001
                required_skills = []

    if not text:
        return {"error": "no_resume_text"}

    prompt = get_prompt_registry().render(
        "hr.cv_analysis",
        context={
            "job_title": job_title or "Non précisé",
            "job_description": job_description or "Non précisé",
            "required_skills": ", ".join(required_skills) or "Non précisé",
            "resume_text": text[:8000],
        },
        tenant=tenant,
    )
    if not prompt:
        return {"error": "prompt_missing"}

    result = get_ollama().chat_json([
        {"role": "system", "content": "Tu es un analyste RH expert."},
        {"role": "user", "content": prompt},
    ])
    data = result.get("data") or {}

    # Persiste un AIProcessingResult si possible.
    if application_id and isinstance(data, dict) and not data.get("_parse_error"):
        _persist_ai_processing(application_id, tenant, data)

    return {
        "model": result.get("model"),
        "duration_ms": result.get("duration_ms"),
        "data": data,
    }


@registry.tool(
    name="hr.generate_interview_questions",
    description="Génère 8-12 questions d'entretien pour un poste donné.",
    risk=RISK_READ,
    schema={
        "type": "object",
        "properties": {
            "recruitment_id": {"type": "string"},
            "candidate_summary": {"type": "string"},
        },
        "required": ["recruitment_id"],
        "additionalProperties": False,
    },
    module="hr",
)
def generate_interview_questions(
    *,
    tenant,
    user,
    recruitment_id: str,
    candidate_summary: str = "",
    **_,
) -> Dict[str, Any]:
    from hr.models import Recruitment

    rec = Recruitment.objects.filter(
        tenant=tenant, id=recruitment_id,
    ).first()
    if rec is None:
        return {"error": "recruitment_not_found"}

    prompt = get_prompt_registry().render(
        "hr.interview_questions",
        context={
            "job_title": rec.title,
            "job_description": (rec.job_description or "")[:3000],
            "candidate_summary": candidate_summary or "Profil junior à confirmer.",
        },
        tenant=tenant,
    )
    result = get_ollama().chat_json([
        {"role": "system", "content": "Tu es un recruteur senior."},
        {"role": "user", "content": prompt},
    ])
    return {
        "data": result.get("data") or {},
        "model": result.get("model"),
        "duration_ms": result.get("duration_ms"),
    }


@registry.tool(
    name="hr.summarize_contract",
    description="Résume un contrat de travail (clauses clés, points d'attention).",
    risk=RISK_READ,
    schema={
        "type": "object",
        "properties": {
            "contract_id": {"type": "string"},
            "contract_text": {"type": "string"},
        },
        "additionalProperties": False,
    },
    module="hr",
)
def summarize_contract(
    *,
    tenant,
    user,
    contract_id: str | None = None,
    contract_text: str | None = None,
    **_,
) -> Dict[str, Any]:
    from hr.models import EmploymentContract

    text = contract_text or ""
    if contract_id and not text:
        c = EmploymentContract.objects.filter(
            tenant_id__in=[str(tenant.id), tenant.slug],
            id=contract_id,
        ).first()
        if c is None:
            return {"error": "contract_not_found"}
        if c.contract_document:
            try:
                text = _extract_text_from_file(c.contract_document)
            except Exception:  # noqa: BLE001
                logger.exception("Failed to extract contract text")

    if not text:
        return {"error": "no_contract_text"}

    prompt = get_prompt_registry().render(
        "hr.contract_summary",
        context={"contract_text": text[:12000]},
        tenant=tenant,
    )
    result = get_ollama().chat([
        {"role": "system", "content": "Tu es un juriste en droit du travail."},
        {"role": "user", "content": prompt},
    ])
    return {
        "summary_markdown": result.get("content", ""),
        "model": result.get("model"),
        "duration_ms": result.get("duration_ms"),
    }


# --------------------------------------------------------------------------- #
# Helpers internes
# --------------------------------------------------------------------------- #
def _extract_text_from_file(file_field) -> str:
    """
    Extrait le texte d'un FieldFile : PDF (pdfplumber) ou docx (python-docx).
    Renvoie une chaîne vide si format non supporté.
    """
    name = getattr(file_field, "name", "") or ""
    lower = name.lower()
    file_field.open("rb")
    try:
        data = file_field.read()
    finally:
        try:
            file_field.close()
        except Exception:  # noqa: BLE001
            pass

    if lower.endswith(".pdf"):
        try:
            import io
            import pdfplumber

            with pdfplumber.open(io.BytesIO(data)) as pdf:
                return "\n".join(
                    (page.extract_text() or "") for page in pdf.pages
                )
        except Exception:  # noqa: BLE001
            return ""

    if lower.endswith(".docx"):
        try:
            import io
            from docx import Document

            doc = Document(io.BytesIO(data))
            return "\n".join(p.text for p in doc.paragraphs)
        except Exception:  # noqa: BLE001
            return ""

    if lower.endswith(".txt"):
        try:
            return data.decode("utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            return ""

    return ""


def _persist_ai_processing(application_id: str, tenant, data: Dict[str, Any]) -> None:
    try:
        from hr.models import AIProcessingResult, JobApplication

        app = JobApplication.objects.filter(id=application_id).first()
        if not app:
            return

        extracted = data.get("extracted_data", {}) or {}
        ai_score = data.get("fit_score") or 0
        feedback = data.get("summary") or ""

        AIProcessingResult.objects.update_or_create(
            job_application=app,
            defaults={
                "tenant_id": str(tenant.id),
                "status": "COMPLETED",
                "extracted_skills": extracted.get("skills", []) or [],
                "extracted_experience": extracted.get("experience", []) or [],
                "extracted_education": extracted.get("education", []) or [],
                "extracted_languages": extracted.get("languages", []) or [],
                "skills_match_score": ai_score,
                "experience_match_score": ai_score,
                "overall_match_score": ai_score,
                "missing_skills": data.get("concerns", []) or [],
                "strong_skills": data.get("strengths", []) or [],
                "processed_at": timezone.now(),
                "ai_model_version": "ollama/qwen2.5",
            },
        )

        # Met à jour le score sur la candidature.
        app.ai_score = ai_score
        app.ai_feedback = feedback
        app.save(update_fields=["ai_score", "ai_feedback", "updated_at"])
    except Exception:  # noqa: BLE001
        logger.exception("Failed to persist AI processing result")
