"""
Le registre d'outils IA s'auto-charge correctement et expose les outils
attendus avec leurs niveaux de risque.
"""
from __future__ import annotations

import pytest

from ai_assistant.services.tool_registry import (
    RISK_READ,
    RISK_WRITE,
    get_tool_registry,
)


def test_registry_loads_general_tools():
    reg = get_tool_registry()
    assert reg.get("general.who_am_i") is not None
    assert reg.get("general.tenant_info") is not None


def test_registry_loads_hr_tools():
    reg = get_tool_registry()
    tool = reg.get("hr.analyze_resume")
    assert tool is not None
    assert tool.risk == RISK_READ
    assert tool.module == "hr"


def test_registry_loads_finance_tools():
    reg = get_tool_registry()
    tool = reg.get("finance.suggest_journal_entry")
    assert tool is not None
    assert tool.risk == RISK_WRITE  # → passera par AIAction


def test_list_for_module_includes_general():
    reg = get_tool_registry()
    hr_tools = reg.list_for_module("hr")
    names = {t.name for t in hr_tools}
    # General tools doivent être disponibles partout.
    assert "general.who_am_i" in names
    assert "hr.analyze_resume" in names
