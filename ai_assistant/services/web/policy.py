"""
Politique de sécurité pour les appels web depuis LyneAI.

- ``ssrf_safe(url)``    : interdit tout host privé/loopback/IP-link-local.
- ``allowed(url)``      : applique allowlist / blocklist domaines.
- ``rate_limit_ok(...)``: rate-limit par tenant via cache.
"""
from __future__ import annotations

import ipaddress
import logging
import re
import socket
from typing import Iterable, Optional, Tuple
from urllib.parse import urlparse

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# SSRF safety
# --------------------------------------------------------------------------- #
_PRIVATE_NETS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]


def ssrf_safe(url: str) -> Tuple[bool, str]:
    """
    Vérifie qu'une URL ne pointe pas vers une zone réseau interne.
    Renvoie ``(ok, raison)``.
    """
    try:
        parsed = urlparse(url)
    except Exception as exc:  # noqa: BLE001
        return False, f"URL invalide : {exc}"

    if parsed.scheme not in {"http", "https"}:
        return False, f"Schéma interdit : {parsed.scheme}"
    if not parsed.hostname:
        return False, "Hostname manquant."

    host = parsed.hostname
    # Interdit explicite localhost
    if host.lower() in {"localhost", "0", "broadcasthost"}:
        return False, "Hôte local interdit."

    # Si le hostname est déjà une IP, on teste directement.
    try:
        ip = ipaddress.ip_address(host)
        for net in _PRIVATE_NETS:
            if ip in net:
                return False, f"IP interne interdite ({ip})"
        return True, ""
    except ValueError:
        pass  # ce n'est pas une IP, on tente la résolution DNS

    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:
        return False, f"DNS résolution échouée : {exc}"

    for info in infos:
        addr = info[4][0]
        try:
            ip = ipaddress.ip_address(addr)
        except ValueError:
            continue
        for net in _PRIVATE_NETS:
            if ip in net:
                return False, f"DNS résolu vers IP interne ({ip})"
    return True, ""


# --------------------------------------------------------------------------- #
# Allow / block list de domaines
# --------------------------------------------------------------------------- #
def _domain(url: str) -> str:
    try:
        return (urlparse(url).hostname or "").lower()
    except Exception:  # noqa: BLE001
        return ""


def allowed(url: str) -> Tuple[bool, str]:
    """
    Vérifie l'URL contre les allowlist/blocklist (variables d'env ou settings).

    - ``WEB_ALLOWLIST`` : si défini, seules les URL d'un domaine listé passent.
    - ``WEB_BLOCKLIST`` : domaines explicitement interdits.

    Format : liste séparée par virgule (ou Python list dans settings).
    Match par suffixe : ``example.com`` couvre aussi ``foo.example.com``.
    """
    domain = _domain(url)
    if not domain:
        return False, "Domaine introuvable."

    allowlist = _normalize(getattr(settings, "WEB_ALLOWLIST", []) or [])
    blocklist = _normalize(getattr(settings, "WEB_BLOCKLIST", []) or [])

    for pattern in blocklist:
        if domain == pattern or domain.endswith("." + pattern):
            return False, f"Domaine bloqué ({domain})."

    if allowlist:
        for pattern in allowlist:
            if domain == pattern or domain.endswith("." + pattern):
                return True, ""
        return False, f"Domaine non listé en allowlist ({domain})."

    return True, ""


def _normalize(value) -> list[str]:
    if isinstance(value, str):
        items = [v.strip().lower() for v in value.split(",") if v.strip()]
    else:
        items = [str(v).strip().lower() for v in (value or []) if str(v).strip()]
    return items


# --------------------------------------------------------------------------- #
# Rate-limit par tenant
# --------------------------------------------------------------------------- #
def rate_limit_ok(
    tenant_id: str | None,
    *,
    bucket: str = "web_search",
    window_seconds: int = 60,
    max_calls: int = 30,
) -> Tuple[bool, str]:
    """
    Token bucket simplifié sur Redis : N appels max par fenêtre glissante.
    """
    if tenant_id is None:
        return True, ""
    key = f"lyneerp:web:rl:{bucket}:{tenant_id}:{int(__import__('time').time()) // window_seconds}"
    try:
        current = cache.get(key) or 0
        if current >= max_calls:
            return False, f"Rate limit dépassé ({max_calls}/{window_seconds}s)."
        cache.set(key, current + 1, window_seconds + 5)
    except Exception:  # noqa: BLE001
        # Si le cache est down, on laisse passer (best-effort) mais on log.
        logger.exception("Rate limit cache failure")
    return True, ""


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
TRACKING_PARAMS = re.compile(
    r"^(utm_|fbclid|gclid|mc_|ref|igshid|yclid|dclid|trk)",
    re.IGNORECASE,
)


def clean_url(url: str) -> str:
    """Supprime les paramètres de tracking d'une URL."""
    from urllib.parse import urlencode, urlparse, urlunparse, parse_qsl

    try:
        p = urlparse(url)
        params = [(k, v) for (k, v) in parse_qsl(p.query, keep_blank_values=True)
                  if not TRACKING_PARAMS.match(k)]
        return urlunparse(p._replace(query=urlencode(params)))
    except Exception:  # noqa: BLE001
        return url
