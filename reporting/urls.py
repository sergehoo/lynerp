"""URLs ``/reporting/...``."""
from __future__ import annotations

from django.urls import path

from reporting.views import ReportingDashboardView

app_name = "reporting"

urlpatterns = [
    path("", ReportingDashboardView.as_view(), name="dashboard"),
]
