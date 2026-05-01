"""
Retrieval simple full-text sur les articles OHADA.

Pas de Postgres FTS pour rester portable. Score = nombre de termes
matchés (mots-clés + titre + résumé), pondéré par champ.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

from django.db.models import Q

logger = logging.getLogger(__name__)


_STOPWORDS = {
    "le", "la", "les", "un", "une", "des", "de", "du", "et", "ou", "à", "au",
    "aux", "que", "qui", "ce", "ces", "cette", "pour", "par", "sur", "dans",
    "avec", "est", "sont", "en", "se", "sa", "son", "ses", "il", "elle", "ils",
    "the", "a", "an", "of", "and", "or", "for", "to", "in", "on", "with",
}


def _tokens(text: str) -> List[str]:
    if not text:
        return []
    raw = re.findall(r"[a-zA-Zà-ÿÀ-Ÿ0-9_]+", text.lower())
    return [w for w in raw if w not in _STOPWORDS and len(w) >= 3]


def search_ohada(
    query: str,
    *,
    actes: Optional[List[str]] = None,
    modules: Optional[List[str]] = None,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """
    Recherche d'articles OHADA pertinents.

    >>> search_ohada("CNPS cotisations salariales")
    [{"reference": "SYSCOHADA-CNPS", ...}, ...]
    """
    from ai_assistant.models import OHADAArticle

    qs = OHADAArticle.objects.filter(is_active=True)
    if actes:
        qs = qs.filter(acte__in=actes)
    if modules:
        # Match si AU MOINS un des modules demandés est dans related_modules.
        # Approximé en SQL pur via icontains (JSON-portable).
        cond = Q()
        for m in modules:
            cond |= Q(related_modules__icontains=f'"{m}"')
        qs = qs.filter(cond)

    tokens = _tokens(query)
    if not tokens:
        return []

    # Heuristique : on tire ~50 candidats par OR sur tokens, puis on score
    cond = Q()
    for tok in tokens[:8]:
        cond |= (
            Q(title__icontains=tok)
            | Q(summary__icontains=tok)
            | Q(keywords__icontains=tok)
            | Q(reference__icontains=tok)
        )
    candidates = list(qs.filter(cond).distinct()[:80])

    scored = []
    for art in candidates:
        score = _score(art, tokens)
        if score <= 0:
            continue
        scored.append((score, art))

    scored.sort(key=lambda x: x[0], reverse=True)
    out = []
    for _score_val, art in scored[:limit]:
        out.append({
            "reference": art.reference,
            "acte": art.acte,
            "acte_display": art.get_acte_display(),
            "title": art.title,
            "summary": art.summary,
            "keywords": art.keywords or [],
            "related_modules": art.related_modules or [],
            "version": art.version,
        })
    return out


def _score(article, tokens: List[str]) -> int:
    """
    Pondération :
        +5 par token dans la référence
        +3 par token dans les keywords (exact)
        +2 par token dans le titre
        +1 par token dans le résumé
    """
    score = 0
    title = (article.title or "").lower()
    summary = (article.summary or "").lower()
    reference = (article.reference or "").lower()
    kw = [str(k).lower() for k in (article.keywords or [])]

    for tok in tokens:
        if tok in reference:
            score += 5
        if tok in kw:
            score += 3
        if tok in title:
            score += 2
        if tok in summary:
            score += 1
    return score


def get_article(reference: str) -> Optional[Dict[str, Any]]:
    from ai_assistant.models import OHADAArticle

    art = OHADAArticle.objects.filter(reference=reference, is_active=True).first()
    if art is None:
        return None
    return {
        "reference": art.reference,
        "acte": art.acte,
        "acte_display": art.get_acte_display(),
        "title": art.title,
        "summary": art.summary,
        "keywords": art.keywords or [],
        "related_modules": art.related_modules or [],
        "related_references": art.related_references or [],
        "version": art.version,
        "livre": art.livre,
        "titre": art.titre,
        "chapitre": art.chapitre,
        "section": art.section,
    }


def list_actes() -> List[Dict[str, str]]:
    from ai_assistant.models import OHADAActe

    return [{"code": code, "label": label} for code, label in OHADAActe.choices]


def article_count() -> int:
    from ai_assistant.models import OHADAArticle

    return OHADAArticle.objects.filter(is_active=True).count()
