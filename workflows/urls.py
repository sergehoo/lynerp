"""URLs web ``/workflows/...``."""
from __future__ import annotations

from django.urls import path

from workflows.views import (
    ApprovalActionView,
    ApprovalRequestDetailView,
    ApprovalRequestListView,
    AuditFeedView,
    NotificationInboxView,
    NotificationMarkReadView,
)

app_name = "workflows"

urlpatterns = [
    path("requests/", ApprovalRequestListView.as_view(), name="request-list"),
    path("requests/<uuid:pk>/", ApprovalRequestDetailView.as_view(), name="request-detail"),
    path("requests/<uuid:pk>/decide/", ApprovalActionView.as_view(), name="request-decide"),
    path("notifications/", NotificationInboxView.as_view(), name="notifications"),
    path("notifications/<uuid:pk>/read/", NotificationMarkReadView.as_view(), name="notification-read"),
    path("audit/", AuditFeedView.as_view(), name="audit"),
]
