"""
Service de "recherche profonde" (deep research) :
1. Lance une recherche web.
2. Récupère le contenu des N premiers résultats.
3. Demande au LLM Ollama un résumé structuré + citations.

Usage typique : un outil IA ``web.research`` qui combine search + fetch +
synthèse. Garde-fou : limite stricte de N pages, max_chars par page,
timeout global.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from ai_assistant.services.ollama import get_ollama
from ai_assistant.services.web.fetch import WebFetchError, web_fetch
from ai_assistant.services.web.search import WebSearchError, web_search

logger = logging.getLogger(__name__)


# Extensions binaires que web_fetch ne sait pas extraire — on filtre en amont
# pour éviter une perte de 5-15s par URL.
_BINARY_EXTENSIONS = (
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".zip", ".rar", ".7z", ".tar", ".gz", ".bz2",
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".bmp", ".ico",
    ".mp3", ".mp4", ".avi", ".mov", ".webm", ".mkv",
    ".csv", ".tsv",
)


def _is_binary_url(url: str) -> bool:
    """True si l'URL pointe (a priori) vers un binaire non-HTML."""
    if not url:
        return True
    try:
        path = (urlparse(url).path or "").lower()
    except Exception:  # noqa: BLE001
        return True
    return any(path.endswith(ext) for ext in _BINARY_EXTENSIONS)


SYNTHESIS_PROMPT = """Tu es **LyneAI**, assistant ERP de l'organisation {tenant_name}.

L'utilisateur a posé la question suivante :
\"\"\"{question}\"\"\"

Tu disposes d'extraits de pages web récupérés en direct sur Internet :

{snippets}

# Mission
Produis une réponse claire en Markdown, structurée :
- Synthèse en 3-5 phrases.
- Bullets pour les faits clés (avec citation [1], [2], … pointant sur les sources).
- Section "Limites & avertissements" (si information potentiellement obsolète,
  contradictoire, dépendante du pays, etc.).
- Section "Sources" listant les URLs avec titres.

# Règles
1. Cite TOUJOURS les sources [n] dans le texte pour les chiffres / affirmations.
2. Si les sources se contredisent, mentionne-le honnêtement.
3. N'invente JAMAIS de chiffre absent des sources.
4. Si la réponse demande un avis juridique/médical/financier critique, rappelle
   qu'il faut consulter un professionnel certifié.
5. Évite les listes interminables : reste précis et concret.
"""


def deep_research(
    *,
    question: str,
    tenant=None,
    locale: str = "fr-fr",
    pages: int = 3,
    max_chars_per_page: int = 3500,
    provider: Optional[str] = None,
    sync_with_ollama: bool = True,
) -> Dict[str, Any]:
    """
    Pipeline complet :
    1. ``web_search(question)``
    2. Pour les ``pages`` premiers résultats acceptables : ``web_fetch(url)``
    3. Synthèse Ollama avec citations [1], [2], …

    Renvoie ``{question, sources, synthesis_markdown, model, duration_ms}``.
    """
    tenant_id = str(getattr(tenant, "id", "")) if tenant is not None else None
    tenant_name = getattr(tenant, "name", "") if tenant is not None else "votre organisation"

    try:
        sr = web_search(
            question, locale=locale, limit=pages * 3,
            provider=provider, tenant_id=tenant_id,
        )
    except WebSearchError as exc:
        return {"error": f"search_failed: {exc}"}

    candidates: List[Dict[str, Any]] = sr.get("results", []) or []
    if not candidates:
        return {
            "question": question,
            "sources": [],
            "synthesis_markdown": (
                "Je n'ai trouvé **aucun résultat** sur le web pour cette question. "
                "Reformule ou précise l'État-membre / le secteur."
            ),
            "provider": sr.get("provider"),
            "cached": sr.get("cached", False),
        }

    fetched: List[Dict[str, Any]] = []
    for cand in candidates:
        if len(fetched) >= pages:
            break
        url = cand.get("url") or ""
        # Filtre amont : on ne tente même pas de fetcher les binaires.
        if _is_binary_url(url):
            logger.debug("Skip binary URL: %s", url)
            continue
        try:
            page = web_fetch(
                url, tenant_id=tenant_id,
                max_chars=max_chars_per_page,
            )
        except WebFetchError as exc:
            logger.info("Skip page (%s) : %s", url, exc)
            continue
        if not page.get("text"):
            continue
        fetched.append({
            "title": page["title"] or cand.get("title", ""),
            "url": page["url"],
            "snippet": cand.get("snippet", ""),
            "text": page["text"],
        })

    if not fetched:
        return {
            "question": question,
            "sources": candidates[:5],
            "synthesis_markdown": (
                "Aucune page n'a pu être récupérée correctement (timeouts, "
                "erreurs HTTP, blocages bot). Voici les liens trouvés dans la "
                "recherche initiale, à consulter manuellement."
            ),
            "provider": sr.get("provider"),
        }

    # Construit le bloc snippets pour le prompt
    snippets_block = ""
    for idx, page in enumerate(fetched, start=1):
        snippets_block += (
            f"\n[{idx}] **{page['title']}** — <{page['url']}>\n"
            f"{page['text']}\n"
        )

    if not sync_with_ollama:
        return {
            "question": question,
            "sources": [
                {"index": i + 1, "title": p["title"], "url": p["url"], "snippet": p["snippet"]}
                for i, p in enumerate(fetched)
            ],
            "raw_snippets": snippets_block,
            "model": None,
        }

    prompt = SYNTHESIS_PROMPT.format(
        tenant_name=tenant_name,
        question=question,
        snippets=snippets_block[:18000],
    )
    result = get_ollama().chat([
        {"role": "system",
         "content": "Tu es un assistant rigoureux qui cite ses sources."},
        {"role": "user", "content": prompt},
    ])

    return {
        "question": question,
        "sources": [
            {"index": i + 1, "title": p["title"], "url": p["url"], "snippet": p["snippet"]}
            for i, p in enumerate(fetched)
        ],
        "synthesis_markdown": result.get("content", ""),
        "provider": sr.get("provider"),
        "cached": sr.get("cached", False),
        "model": result.get("model"),
        "duration_ms": result.get("duration_ms"),
    }
