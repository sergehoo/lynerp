"""
URLs API REST module RH (``/api/rh/...``).

Toutes les routes du module sont auto-déclarées par le ``DefaultRouter``
exposé dans ``hr.api.routers``. On rajoute ici les endpoints non-router
(stats globales hors viewset).
"""
from __future__ import annotations

from django.urls import include, path

from hr.api.routers import urlpatterns as router_urls
from hr.api.views import RecruitmentStatsView

app_name = "hr_api"

urlpatterns = [
    path("dashboard/recruitment-stats/", RecruitmentStatsView.as_view(), name="recruitment-stats"),
    path("", include(router_urls)),
]
