"""
Moteur de recherche web pluggable pour LyneAI.

Providers disponibles :
- ``ddg``    : DuckDuckGo HTML (gratuit, scraping respectueux, par défaut).
- ``brave``  : API Brave Search (clé requise, ``BRAVE_API_KEY``).
- ``searx``  : SearxNG auto-hébergé (URL ``SEARX_URL``).

Chaque provider renvoie une liste normalisée :
    [{"title": "...", "url": "...", "snippet": "...", "source": "ddg"}]

Le service ajoute automatiquement :
- la mise en cache (Redis ou LocMem) avec TTL configurable
- le filtrage SSRF / allowlist sur les URLs renvoyées
- l'audit (modèle WebSearchCache)
- le rate-limit par tenant
"""
from __future__ import annotations

import hashlib
import logging
import re
import time
import urllib.parse
from typing import Any, Dict, List, Optional

import requests
from django.conf import settings
from django.core.cache import cache

from ai_assistant.services.web.policy import (
    allowed as policy_allowed,
    clean_url,
    rate_limit_ok,
)

logger = logging.getLogger(__name__)


class WebSearchError(Exception):
    """Erreur côté provider de recherche."""


# --------------------------------------------------------------------------- #
# Cache helpers
# --------------------------------------------------------------------------- #
def _cache_key(provider: str, query: str, locale: str) -> str:
    digest = hashlib.sha1(
        f"{provider}|{query}|{locale}".encode("utf-8")
    ).hexdigest()
    return f"lyneerp:web:search:{provider}:{digest}"


def _ttl() -> int:
    return int(getattr(settings, "WEB_SEARCH_CACHE_TTL", 60 * 30))


# --------------------------------------------------------------------------- #
# Provider : DuckDuckGo HTML
# --------------------------------------------------------------------------- #
_DDG_RESULT_RE = re.compile(
    r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
    re.DOTALL,
)
_DDG_SNIPPET_RE = re.compile(
    r'<a[^>]+class="result__snippet"[^>]*>(.*?)</a>',
    re.DOTALL,
)


def _ddg_search(query: str, locale: str = "fr-fr", limit: int = 8) -> List[Dict[str, str]]:
    url = "https://html.duckduckgo.com/html/"
    params = {"q": query, "kl": locale}
    headers = {
        "User-Agent": getattr(
            settings, "WEB_SEARCH_USER_AGENT",
            "Mozilla/5.0 (LyneERP-AI/1.0) AppleWebKit/537.36",
        ),
        "Accept": "text/html",
    }
    timeout = int(getattr(settings, "WEB_SEARCH_TIMEOUT", 12))
    resp = requests.post(url, data=params, headers=headers, timeout=timeout)
    resp.raise_for_status()
    html = resp.text

    results = []
    titles_iter = _DDG_RESULT_RE.finditer(html)
    snippets_iter = _DDG_SNIPPET_RE.finditer(html)
    for title_m, snip_m in zip(titles_iter, snippets_iter):
        href = title_m.group(1)
        # DuckDuckGo wrappe l'URL via /l/?uddg=...
        if href.startswith("/l/?") or href.startswith("//duckduckgo.com/l/"):
            try:
                qs = urllib.parse.urlparse(href).query
                target = urllib.parse.parse_qs(qs).get("uddg", [""])[0]
                href = urllib.parse.unquote(target) or href
            except Exception:  # noqa: BLE001
                pass
        if href.startswith("//"):
            href = "https:" + href
        title = re.sub(r"<.*?>", "", title_m.group(2)).strip()
        snippet = re.sub(r"<.*?>", "", snip_m.group(1)).strip()
        if not href or not title:
            continue
        results.append({
            "title": title,
            "url": clean_url(href),
            "snippet": snippet,
            "source": "ddg",
        })
        if len(results) >= limit:
            break
    return results


# --------------------------------------------------------------------------- #
# Provider : Brave Search API
# --------------------------------------------------------------------------- #
def _brave_search(query: str, locale: str = "fr-fr", limit: int = 8) -> List[Dict[str, str]]:
    api_key = getattr(settings, "BRAVE_API_KEY", "")
    if not api_key:
        raise WebSearchError("BRAVE_API_KEY manquant.")
    url = "https://api.search.brave.com/res/v1/web/search"
    headers = {
        "Accept": "application/json",
        "X-Subscription-Token": api_key,
        "User-Agent": "LyneERP-AI/1.0",
    }
    params = {"q": query, "count": min(limit, 20), "country": (locale.split("-")[-1] or "fr")}
    resp = requests.get(url, headers=headers, params=params, timeout=12)
    resp.raise_for_status()
    data = resp.json()
    results = []
    for item in (data.get("web", {}) or {}).get("results", []) or []:
        results.append({
            "title": item.get("title") or "",
            "url": clean_url(item.get("url") or ""),
            "snippet": item.get("description") or "",
            "source": "brave",
        })
        if len(results) >= limit:
            break
    return results


# --------------------------------------------------------------------------- #
# Provider : SearxNG (auto-hébergé)
# --------------------------------------------------------------------------- #
def _searx_search(query: str, locale: str = "fr-fr", limit: int = 8) -> List[Dict[str, str]]:
    base = getattr(settings, "SEARX_URL", "")
    if not base:
        raise WebSearchError("SEARX_URL manquant.")
    base = base.rstrip("/")
    resp = requests.get(
        f"{base}/search",
        params={"q": query, "format": "json", "language": locale},
        headers={"User-Agent": "LyneERP-AI/1.0"},
        timeout=12,
    )
    resp.raise_for_status()
    data = resp.json()
    results = []
    for item in (data.get("results") or [])[:limit]:
        results.append({
            "title": item.get("title") or "",
            "url": clean_url(item.get("url") or ""),
            "snippet": item.get("content") or "",
            "source": "searx",
        })
    return results


# --------------------------------------------------------------------------- #
# Dispatcher
# --------------------------------------------------------------------------- #
PROVIDERS = {
    "ddg": _ddg_search,
    "brave": _brave_search,
    "searx": _searx_search,
}


def web_search(
    query: str,
    *,
    locale: str = "fr-fr",
    limit: int = 8,
    provider: Optional[str] = None,
    tenant_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Lance une recherche web. Renvoie ``{"results": [...], "provider": "...",
    "duration_ms": int, "cached": bool}``.
    """
    provider = (provider or getattr(settings, "WEB_SEARCH_PROVIDER", "ddg")).lower()
    if provider not in PROVIDERS:
        raise WebSearchError(f"Provider inconnu : {provider}")

    # Rate limit
    ok, reason = rate_limit_ok(tenant_id, bucket="search")
    if not ok:
        raise WebSearchError(reason)

    cache_key = _cache_key(provider, query, locale)
    cached = cache.get(cache_key)
    if cached is not None:
        return {**cached, "cached": True}

    started = time.monotonic()
    fn = PROVIDERS[provider]
    try:
        raw = fn(query=query, locale=locale, limit=limit)
    except requests.RequestException as exc:
        raise WebSearchError(f"Provider {provider} injoignable : {exc}") from exc

    # Filtrage allowlist/blocklist
    filtered = []
    for r in raw:
        ok2, _ = policy_allowed(r["url"])
        if not ok2:
            continue
        filtered.append(r)

    payload = {
        "query": query,
        "provider": provider,
        "locale": locale,
        "results": filtered,
        "duration_ms": int((time.monotonic() - started) * 1000),
        "cached": False,
    }
    try:
        cache.set(cache_key, payload, _ttl())
    except Exception:  # noqa: BLE001
        logger.exception("Cache write failed for web search")
    return payload
