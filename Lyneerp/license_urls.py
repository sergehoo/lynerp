"""
URLs API ``/api/license/`` pour la gestion des licences/sièges multi-tenant.
"""
from __future__ import annotations

from django.urls import path

from hr.api.api_auth import (
    LicensePortalView,
    LicenseRefreshView,
    LicenseStatusView as RHLicenseStatusView,
)
from tenants.api_license import (
    LicenseClaimSeatView,
    LicenseStatusView as TenantLicenseStatusView,
)

app_name = "license"

urlpatterns = [
    # Statut "rapide" pour le front RH (réponse simple)
    path("rh/status/", RHLicenseStatusView.as_view(), name="rh-status"),
    path("rh/refresh/", LicenseRefreshView.as_view(), name="rh-refresh"),
    path("rh/portal/", LicensePortalView.as_view(), name="rh-portal"),
    # Statut détaillé multi-tenant + claim de siège
    path("status/", TenantLicenseStatusView.as_view(), name="status"),
    path("claim-seat/", LicenseClaimSeatView.as_view(), name="claim-seat"),
]
