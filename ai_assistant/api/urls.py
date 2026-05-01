"""URLs API ``/api/ai/...``."""
from __future__ import annotations

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from ai_assistant.api.views import (
    AIActionViewSet,
    AIConversationViewSet,
    ToolRunView,
)
from ai_assistant.api.web_views import (
    WebFetchView,
    WebResearchView,
    WebSearchView,
)

app_name = "ai_api"

router = DefaultRouter(trailing_slash=True)
router.register(r"conversations", AIConversationViewSet, basename="conversations")
router.register(r"actions", AIActionViewSet, basename="actions")

urlpatterns = [
    # Web research raccourcis
    path("web/search/", WebSearchView.as_view(), name="web-search"),
    path("web/fetch/", WebFetchView.as_view(), name="web-fetch"),
    path("web/research/", WebResearchView.as_view(), name="web-research"),
    # Tool generic runner
    path("tools/<str:name>/run/", ToolRunView.as_view(), name="tool-run"),
    # CRUD conversations & actions
    path("", include(router.urls)),
]
