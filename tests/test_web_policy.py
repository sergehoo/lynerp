"""
Tests de la couche policy : SSRF, allowlist/blocklist, clean_url.
"""
from __future__ import annotations

import pytest

from ai_assistant.services.web.policy import (
    allowed,
    clean_url,
    rate_limit_ok,
    ssrf_safe,
)


def test_ssrf_blocks_private_ip():
    ok, reason = ssrf_safe("http://192.168.1.10/")
    assert ok is False
    assert "interne" in reason.lower() or "internal" in reason.lower() or reason


def test_ssrf_blocks_loopback_hostname():
    ok, _ = ssrf_safe("http://127.0.0.1/")
    assert ok is False


def test_ssrf_blocks_localhost():
    ok, _ = ssrf_safe("http://localhost/")
    assert ok is False


def test_ssrf_blocks_invalid_scheme():
    ok, reason = ssrf_safe("file:///etc/passwd")
    assert ok is False


def test_ssrf_allows_public_https():
    # On ne fait pas de requête : juste la résolution DNS.
    ok, _ = ssrf_safe("https://example.com/")
    assert ok is True


def test_clean_url_strips_tracking():
    url = "https://example.com/page?utm_source=foo&id=42&fbclid=xxx"
    cleaned = clean_url(url)
    assert "utm_source" not in cleaned
    assert "fbclid" not in cleaned
    assert "id=42" in cleaned


def test_blocklist(settings):
    settings.WEB_BLOCKLIST = ["bad.example"]
    settings.WEB_ALLOWLIST = []
    ok, reason = allowed("https://foo.bad.example/x")
    assert ok is False
    ok2, _ = allowed("https://other.example/x")
    assert ok2 is True


def test_allowlist_restrictive(settings):
    settings.WEB_BLOCKLIST = []
    settings.WEB_ALLOWLIST = ["good.example"]
    ok, _ = allowed("https://good.example/x")
    assert ok is True
    ok2, _ = allowed("https://other.example/x")
    assert ok2 is False


def test_rate_limit_allows_first_calls():
    # Sans cache configuré, ne doit pas planter et laisse passer.
    ok, _ = rate_limit_ok("tenant-uuid-test", bucket="search", max_calls=10)
    assert ok is True
