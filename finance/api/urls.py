"""URLs API REST module Finance (``/api/finance/...``)."""
from __future__ import annotations

from django.urls import include, path

from finance.api.ai_views import (
    AnalyzeBalanceView,
    DetectAnomaliesView,
    SuggestJournalEntryView,
)
from finance.api.routers import router

urlpatterns = [
    # Raccourcis IA Finance
    path("ai/analyze-balance/", AnalyzeBalanceView.as_view(), name="finance-ai-analyze-balance"),
    path("ai/detect-anomalies/", DetectAnomaliesView.as_view(), name="finance-ai-detect-anomalies"),
    path("ai/suggest-journal-entry/", SuggestJournalEntryView.as_view(), name="finance-ai-suggest-journal-entry"),
    # Routeur DRF principal
    path("", include(router.urls)),
]
