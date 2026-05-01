"""
Construction du contexte injecté dans les prompts IA.

Règle d'or : ne JAMAIS fuir des données sensibles dans le contexte d'un
utilisateur (numéros de sécurité sociale, salaires d'autres employés, etc.).

Le contexte est filtré par tenant ET par permissions du user courant.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def build_user_context(user, tenant) -> Dict[str, Any]:
    """
    Contexte minimal sur l'utilisateur courant, à injecter dans les prompts.
    """
    if user is None or not user.is_authenticated:
        return {"user": None}
    return {
        "user": {
            "id": str(getattr(user, "pk", "")),
            "username": getattr(user, "username", ""),
            "email": getattr(user, "email", ""),
            "full_name": (
                f"{getattr(user, 'first_name', '')} {getattr(user, 'last_name', '')}"
            ).strip(),
            "is_superuser": bool(getattr(user, "is_superuser", False)),
        },
        "tenant": _tenant_summary(tenant),
    }


def _tenant_summary(tenant) -> Optional[Dict[str, Any]]:
    if tenant is None:
        return None
    return {
        "id": str(tenant.id),
        "slug": getattr(tenant, "slug", ""),
        "name": getattr(tenant, "name", ""),
        "currency": getattr(tenant, "currency", ""),
        "timezone": getattr(tenant, "timezone", ""),
    }


def safe_summary(obj: Any, fields: Optional[list[str]] = None) -> Dict[str, Any]:
    """
    Sérialise un objet Django en dict en n'exposant QUE les champs demandés.

    Utile pour fournir à l'IA un contexte minimal sans fuiter les FK
    sensibles, JSON internes, etc.
    """
    if obj is None:
        return {}
    out: Dict[str, Any] = {}
    for f in fields or []:
        try:
            value = getattr(obj, f, None)
        except Exception:  # noqa: BLE001
            continue
        if hasattr(value, "isoformat"):
            value = value.isoformat()
        out[f] = value
    return out


def redact(text: str, patterns: Optional[list[str]] = None) -> str:
    """
    Remplace les motifs sensibles par ``[REDACTED]``. Liste extensible.
    """
    import re

    default_patterns = [
        r"\b\d{13,16}\b",                      # numéros de carte
        r"\b\d{3}-\d{2}-\d{4}\b",              # SSN style US
        r"(?i)password\s*[:=]\s*\S+",
        r"(?i)secret\s*[:=]\s*\S+",
        r"(?i)api[_-]?key\s*[:=]\s*\S+",
        r"(?i)bearer\s+[A-Za-z0-9._-]+",
    ]
    for pat in (patterns or []) + default_patterns:
        text = re.sub(pat, "[REDACTED]", text)
    return text
