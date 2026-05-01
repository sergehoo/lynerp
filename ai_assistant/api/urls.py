"""URLs API ``/api/ai/...``."""
from __future__ import annotations

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from ai_assistant.api.views import (
    AIActionViewSet,
    AIConversationViewSet,
    ToolRunView,
)

app_name = "ai_api"

router = DefaultRouter(trailing_slash=True)
router.register(r"conversations", AIConversationViewSet, basename="conversations")
router.register(r"actions", AIActionViewSet, basename="actions")

urlpatterns = [
    path("", include(router.urls)),
    path("tools/<str:name>/run/", ToolRunView.as_view(), name="tool-run"),
]
