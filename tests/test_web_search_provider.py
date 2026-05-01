"""
Tests du dispatcher de provider de recherche web.
On mocke ``requests`` pour ne pas dépendre du réseau.
"""
from __future__ import annotations

from unittest.mock import patch, MagicMock

import pytest

from ai_assistant.services.web.search import (
    PROVIDERS,
    WebSearchError,
    web_search,
)


def test_unknown_provider_raises(settings):
    settings.WEB_SEARCH_PROVIDER = "xxx"
    with pytest.raises(WebSearchError):
        web_search("test")


def test_ddg_html_parsing(settings):
    """Vérifie que le scraping DuckDuckGo HTML extrait au moins un résultat."""
    settings.WEB_SEARCH_PROVIDER = "ddg"
    settings.WEB_BLOCKLIST = []
    settings.WEB_ALLOWLIST = []

    fake_html = """
    <a class="result__a" href="https://example.com/page">Titre exemple</a>
    <a class="result__snippet">Voici un extrait pertinent.</a>
    <a class="result__a" href="https://other.test/foo">Autre</a>
    <a class="result__snippet">Description alternative.</a>
    """
    fake_resp = MagicMock(status_code=200, text=fake_html)
    fake_resp.raise_for_status = MagicMock()

    with patch("ai_assistant.services.web.search.requests.post", return_value=fake_resp):
        out = web_search("test", limit=5)
    assert out["provider"] == "ddg"
    assert len(out["results"]) >= 1
    assert out["results"][0]["title"]


def test_brave_provider_requires_key(settings):
    settings.WEB_SEARCH_PROVIDER = "brave"
    settings.BRAVE_API_KEY = ""
    with pytest.raises(WebSearchError):
        web_search("test")


def test_searx_requires_url(settings):
    settings.WEB_SEARCH_PROVIDER = "searx"
    settings.SEARX_URL = ""
    with pytest.raises(WebSearchError):
        web_search("test")


def test_results_filtered_by_blocklist(settings):
    settings.WEB_SEARCH_PROVIDER = "ddg"
    settings.WEB_ALLOWLIST = []
    settings.WEB_BLOCKLIST = ["other.test"]

    fake_html = """
    <a class="result__a" href="https://example.com/page">Bon</a>
    <a class="result__snippet">A</a>
    <a class="result__a" href="https://other.test/foo">Bloqué</a>
    <a class="result__snippet">B</a>
    """
    fake_resp = MagicMock(status_code=200, text=fake_html)
    fake_resp.raise_for_status = MagicMock()

    with patch("ai_assistant.services.web.search.requests.post", return_value=fake_resp):
        out = web_search("test")

    urls = [r["url"] for r in out["results"]]
    assert all("other.test" not in u for u in urls)
