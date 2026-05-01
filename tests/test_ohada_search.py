"""
Tests du retrieval OHADA.
"""
from __future__ import annotations

import pytest

from ai_assistant.models import OHADAArticle
from ai_assistant.ohada.knowledge import OHADA_KNOWLEDGE
from ai_assistant.ohada.retrieval import (
    article_count,
    get_article,
    list_actes,
    search_ohada,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def ohada_seed(db):
    """Charge le référentiel OHADA via le seed (rapide en SQLite mémoire)."""
    for spec in OHADA_KNOWLEDGE:
        OHADAArticle.objects.update_or_create(
            reference=spec["reference"],
            defaults={
                "acte": spec["acte"],
                "livre": spec.get("livre", ""),
                "title": spec["title"],
                "summary": spec["summary"],
                "article_number": spec.get("article_number", ""),
                "keywords": spec.get("keywords", []),
                "related_modules": spec.get("related_modules", []),
                "related_references": spec.get("related_references", []),
                "is_active": True,
            },
        )


def test_seed_loaded(ohada_seed):
    assert article_count() >= 30


def test_list_actes_contains_main():
    codes = {a["code"] for a in list_actes()}
    assert {"DCG", "AUSCGIE", "SURETES", "SYSCOHADA", "PROCED_COLL"}.issubset(codes)


def test_search_finds_cnps(ohada_seed):
    res = search_ohada("CNPS cotisations sociales")
    assert len(res) > 0
    refs = {r["reference"] for r in res}
    assert any("CNPS" in r or "SYSCOHADA" in r for r in refs)


def test_search_finds_super_privilege_salaires(ohada_seed):
    res = search_ohada("super privilège salaires liquidation")
    assert len(res) > 0
    refs = {r["reference"] for r in res}
    # Doit retourner l'article PROCED_COLL sur les privilèges en liquidation.
    assert any("PROCED_COLL" in r for r in refs)


def test_search_filter_by_module(ohada_seed):
    res = search_ohada("contrat", modules=["payroll"])
    # Limité aux articles avec module payroll dans related_modules.
    for r in res:
        assert "payroll" in r["related_modules"]


def test_get_article_by_reference(ohada_seed):
    art = get_article("AUSCGIE-Art.4-9")
    assert art is not None
    assert "société commerciale" in art["title"].lower()


def test_get_article_unknown(ohada_seed):
    assert get_article("ZZZ-Art.999") is None
