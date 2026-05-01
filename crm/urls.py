"""URLs web ``/crm/...``."""
from __future__ import annotations

from django.urls import path

from crm.views import CRMDashboardView, LeadListView, OpportunityListView

app_name = "crm"

urlpatterns = [
    path("", CRMDashboardView.as_view(), name="dashboard"),
    path("leads/", LeadListView.as_view(), name="lead-list"),
    path("opportunities/", OpportunityListView.as_view(), name="opportunity-list"),
]
