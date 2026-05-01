"""
URLs API REST module RH (``/api/rh/...``).

Toutes les routes du module sont auto-déclarées par le ``DefaultRouter``
exposé dans ``hr.api.routers``. On rajoute ici les endpoints non-router
(stats globales hors viewset, raccourcis IA).
"""
from __future__ import annotations

from django.urls import include, path

from hr.api.ai_views import (
    AnalyzeResumeView,
    GenerateInterviewQuestionsView,
    SummarizeContractView,
)
from hr.api.routers import urlpatterns as router_urls
from hr.api.views import RecruitmentStatsView

app_name = "hr_api"

urlpatterns = [
    # Statistiques
    path("dashboard/recruitment-stats/", RecruitmentStatsView.as_view(), name="recruitment-stats"),
    # Raccourcis IA RH
    path("ai/analyze-resume/", AnalyzeResumeView.as_view(), name="ai-analyze-resume"),
    path("ai/interview-questions/", GenerateInterviewQuestionsView.as_view(), name="ai-interview-questions"),
    path("ai/summarize-contract/", SummarizeContractView.as_view(), name="ai-summarize-contract"),
    # Routeur DRF principal
    path("", include(router_urls)),
]
