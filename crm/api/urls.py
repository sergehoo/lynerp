"""URLs API ``/api/crm/...``."""
from __future__ import annotations

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from crm.api.views import (
    AccountViewSet,
    ActivityViewSet,
    ContactViewSet,
    LeadViewSet,
    OpportunityViewSet,
    PipelineViewSet,
    StageViewSet,
)

app_name = "crm_api"

router = DefaultRouter(trailing_slash=True)
router.register(r"accounts", AccountViewSet, basename="crm-accounts")
router.register(r"contacts", ContactViewSet, basename="crm-contacts")
router.register(r"pipelines", PipelineViewSet, basename="crm-pipelines")
router.register(r"stages", StageViewSet, basename="crm-stages")
router.register(r"opportunities", OpportunityViewSet, basename="crm-opps")
router.register(r"leads", LeadViewSet, basename="crm-leads")
router.register(r"activities", ActivityViewSet, basename="crm-activities")

urlpatterns = [path("", include(router.urls))]
