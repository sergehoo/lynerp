"""
Fetch d'URL + extraction de texte propre pour LyneAI.

- Vérifie SSRF + allowlist/blocklist + rate-limit avant tout appel HTTP.
- Limite la taille du contenu téléchargé (configurable).
- Préfère ``trafilatura`` pour l'extraction de texte (si installé).
- Fallback : extraction simple via BeautifulSoup ou regex stripper.
- Mise en cache avec TTL pour éviter les requêtes répétées.
"""
from __future__ import annotations

import hashlib
import logging
import re
import time
from typing import Any, Dict, Optional

import requests
from django.conf import settings
from django.core.cache import cache

from ai_assistant.services.web.policy import (
    allowed as policy_allowed,
    clean_url,
    rate_limit_ok,
    ssrf_safe,
)

logger = logging.getLogger(__name__)


class WebFetchError(Exception):
    pass


def _cache_key(url: str) -> str:
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()
    return f"lyneerp:web:fetch:{digest}"


def _ttl() -> int:
    return int(getattr(settings, "WEB_FETCH_CACHE_TTL", 60 * 60 * 6))  # 6h


def _max_bytes() -> int:
    return int(getattr(settings, "WEB_FETCH_MAX_BYTES", 2 * 1024 * 1024))  # 2 Mo


def _timeout() -> int:
    return int(getattr(settings, "WEB_FETCH_TIMEOUT", 15))


# --------------------------------------------------------------------------- #
# Extraction
# --------------------------------------------------------------------------- #
def _extract_text(html: str, url: str) -> Dict[str, str]:
    """
    Extrait titre + texte propre d'une page HTML.
    Priorité : trafilatura → BeautifulSoup → regex strip.
    """
    title = ""
    text = ""

    # 1) trafilatura
    try:
        import trafilatura

        downloaded = trafilatura.extract(
            html,
            url=url,
            include_comments=False,
            include_tables=True,
            no_fallback=False,
            favor_recall=False,
        )
        if downloaded:
            text = downloaded
        meta = trafilatura.extract_metadata(html)
        if meta and getattr(meta, "title", None):
            title = meta.title or ""
    except Exception:  # noqa: BLE001
        pass

    # 2) BeautifulSoup fallback
    if not text:
        try:
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(html, "html.parser")
            if not title and soup.title and soup.title.string:
                title = soup.title.string.strip()[:200]
            for tag in soup(["script", "style", "nav", "header", "footer", "aside", "noscript"]):
                tag.decompose()
            text = soup.get_text(separator="\n", strip=True)
        except Exception:  # noqa: BLE001
            pass

    # 3) regex final fallback
    if not text:
        cleaned = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
        cleaned = re.sub(r"<style[^>]*>.*?</style>", "", cleaned, flags=re.DOTALL | re.IGNORECASE)
        cleaned = re.sub(r"<[^>]+>", " ", cleaned)
        text = re.sub(r"\s+", " ", cleaned).strip()
    if not title:
        m = re.search(r"<title[^>]*>(.*?)</title>", html, re.DOTALL | re.IGNORECASE)
        if m:
            title = re.sub(r"\s+", " ", m.group(1)).strip()[:200]

    return {"title": title, "text": text}


# --------------------------------------------------------------------------- #
# Fetch principal
# --------------------------------------------------------------------------- #
def web_fetch(
    url: str,
    *,
    tenant_id: Optional[str] = None,
    max_chars: int = 8000,
) -> Dict[str, Any]:
    """
    Récupère une URL et extrait son texte. Renvoie ::

        {
            "url": "...",
            "title": "...",
            "text": "...",          # tronqué à max_chars
            "char_count": int,      # taille avant troncature
            "duration_ms": int,
            "cached": bool,
            "content_type": "...",
        }
    """
    url = clean_url((url or "").strip())
    if not url:
        raise WebFetchError("URL vide.")

    # Sécurité : SSRF
    ok, reason = ssrf_safe(url)
    if not ok:
        raise WebFetchError(f"URL refusée (SSRF) : {reason}")

    ok, reason = policy_allowed(url)
    if not ok:
        raise WebFetchError(f"URL refusée (policy) : {reason}")

    ok, reason = rate_limit_ok(tenant_id, bucket="fetch", max_calls=60)
    if not ok:
        raise WebFetchError(reason)

    # Cache
    cache_key = _cache_key(url)
    cached = cache.get(cache_key)
    if cached is not None:
        out = dict(cached)
        out["text"] = out.get("text", "")[:max_chars]
        out["cached"] = True
        return out

    started = time.monotonic()
    headers = {
        "User-Agent": getattr(
            settings, "WEB_SEARCH_USER_AGENT",
            "Mozilla/5.0 (LyneERP-AI/1.0)",
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "fr,en;q=0.7",
    }
    try:
        with requests.get(
            url, headers=headers, timeout=_timeout(),
            stream=True, allow_redirects=True,
        ) as resp:
            resp.raise_for_status()
            content_type = (resp.headers.get("Content-Type") or "").lower()
            if "html" not in content_type and "xml" not in content_type and "text" not in content_type:
                # Sécurité supplémentaire : on refuse les binaires (pdf, images,
                # vidéos…). Pour PDF, l'utilisateur doit passer par OCR.
                if "pdf" in content_type:
                    raise WebFetchError("PDF non supporté par web_fetch — utiliser OCR.")
                raise WebFetchError(f"Content-Type non supporté : {content_type}")

            # Limite de taille
            chunks = []
            total = 0
            for chunk in resp.iter_content(chunk_size=8192, decode_unicode=False):
                if not chunk:
                    continue
                chunks.append(chunk)
                total += len(chunk)
                if total > _max_bytes():
                    raise WebFetchError(f"Contenu trop volumineux ({total} bytes).")
            raw = b"".join(chunks)

            try:
                html = raw.decode(resp.encoding or "utf-8", errors="replace")
            except Exception:  # noqa: BLE001
                html = raw.decode("utf-8", errors="replace")
    except requests.RequestException as exc:
        raise WebFetchError(f"Erreur réseau : {exc}") from exc

    extracted = _extract_text(html, url)
    full_text = extracted["text"] or ""
    payload = {
        "url": url,
        "title": extracted["title"],
        "text": full_text[:max_chars],
        "char_count": len(full_text),
        "duration_ms": int((time.monotonic() - started) * 1000),
        "cached": False,
        "content_type": content_type,
    }
    try:
        cache.set(cache_key, payload, _ttl())
    except Exception:  # noqa: BLE001
        logger.exception("Cache write failed for web fetch")
    return payload
