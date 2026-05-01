"""
Tests pour ``ai_assistant.services.web.fetch.web_fetch``.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from ai_assistant.services.web.fetch import WebFetchError, web_fetch


def _fake_response(html: str, content_type: str = "text/html"):
    resp = MagicMock()
    resp.headers = {"Content-Type": content_type}
    resp.encoding = "utf-8"
    resp.iter_content = lambda chunk_size, decode_unicode=False: iter([html.encode()])
    resp.raise_for_status = MagicMock()
    resp.__enter__ = lambda self: resp
    resp.__exit__ = lambda self, *args: False
    return resp


def test_fetch_extracts_title_and_text(settings):
    settings.WEB_BLOCKLIST = []
    settings.WEB_ALLOWLIST = []

    html = "<html><head><title>Mon titre</title></head><body><p>Hello world</p></body></html>"
    with patch("ai_assistant.services.web.fetch.ssrf_safe", return_value=(True, "")), \
         patch("ai_assistant.services.web.fetch.requests.get", return_value=_fake_response(html)):
        out = web_fetch("https://example.com/page", max_chars=2000)
    assert "Mon titre" in (out["title"] or "")
    assert "Hello" in out["text"]
    assert out["cached"] is False


def test_fetch_refuses_pdf(settings):
    settings.WEB_BLOCKLIST = []
    settings.WEB_ALLOWLIST = []

    with patch("ai_assistant.services.web.fetch.ssrf_safe", return_value=(True, "")), \
         patch("ai_assistant.services.web.fetch.requests.get",
               return_value=_fake_response("%PDF-1.4...", content_type="application/pdf")):
        with pytest.raises(WebFetchError):
            web_fetch("https://example.com/file.pdf")


def test_fetch_refuses_internal_ssrf(settings):
    with pytest.raises(WebFetchError):
        web_fetch("http://192.168.1.10/admin")


def test_fetch_refuses_blocked_domain(settings):
    settings.WEB_ALLOWLIST = []
    settings.WEB_BLOCKLIST = ["bad.example"]
    with patch("ai_assistant.services.web.fetch.ssrf_safe", return_value=(True, "")):
        with pytest.raises(WebFetchError):
            web_fetch("https://bad.example/x")
