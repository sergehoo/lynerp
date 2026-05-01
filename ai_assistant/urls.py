"""URLs web ``/ai/...``."""
from __future__ import annotations

from django.urls import path

from ai_assistant.views import (
    AIActionDetailView,
    AIActionListView,
    AIPanelView,
)

app_name = "ai"

urlpatterns = [
    path("", AIPanelView.as_view(), name="panel"),
    path("actions/", AIActionListView.as_view(), name="action-list"),
    path("actions/<uuid:pk>/", AIActionDetailView.as_view(), name="action-detail"),
]
