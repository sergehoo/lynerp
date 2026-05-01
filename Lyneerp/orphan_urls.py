"""
URLs orphelines : toutes les pages référencées dans la sidebar mais qui
ne sont pas (encore) couvertes par un module métier.

Stratégie : chaque route orpheline pointe vers ``PlaceholderView`` avec
une clé qui décrit la page (titre, icône, fonctionnalités à venir).

Cela permet :
1. Aucun lien mort dans la sidebar (404 → page propre).
2. Un endroit centralisé pour suivre les "modules à venir".
3. Une migration progressive : remplacer chaque route par sa vraie vue
   au fur et à mesure des développements.
"""
from __future__ import annotations

from django.urls import path
from django.views.generic import RedirectView

from Lyneerp.placeholder import PlaceholderView


app_name = "orphans"

urlpatterns = [
    # =================================================================
    # CORE
    # =================================================================
    path("tasks/", PlaceholderView.as_view(key="core.tasks"), name="tasks"),
    path("documents/", PlaceholderView.as_view(key="core.documents"), name="documents"),
    path("system-audit/", PlaceholderView.as_view(key="core.audit"), name="system-audit"),

    # =================================================================
    # HR
    # =================================================================
    path("hr/performance/", PlaceholderView.as_view(key="hr.performance"), name="hr-performance"),
    path("hr/training/", PlaceholderView.as_view(key="hr.training"), name="hr-training"),

    # =================================================================
    # SALES (CRM)
    # =================================================================
    path("crm/orders/", PlaceholderView.as_view(key="sales.sales_orders"), name="crm-orders"),
    path("crm/support/", PlaceholderView.as_view(key="sales.customer_support"), name="crm-support"),
    # Quotes : on redirige vers Finance qui les gère déjà.
    path(
        "crm/quotes/",
        RedirectView.as_view(url="/finance/quotes/", permanent=False),
        name="crm-quotes",
    ),

    # =================================================================
    # OPS / Stock
    # =================================================================
    path("ops/inventory-counts/", PlaceholderView.as_view(key="ops.inventory_counts"), name="ops-inventory-counts"),
    path("ops/shipments/", PlaceholderView.as_view(key="ops.shipments"), name="ops-shipments"),
    path("ops/tracking/", PlaceholderView.as_view(key="ops.tracking"), name="ops-tracking"),
    path("ops/purchase-orders/", PlaceholderView.as_view(key="ops.purchase_orders"), name="ops-purchase-orders"),

    # =================================================================
    # PROJECTS
    # =================================================================
    path("projects/kanban/", PlaceholderView.as_view(key="projects.kanban"), name="projects-kanban"),
    path("projects/gantt/", PlaceholderView.as_view(key="projects.gantt"), name="projects-gantt"),
    path("projects/costs/", PlaceholderView.as_view(key="projects.project_costs"), name="projects-costs"),

    # =================================================================
    # BI / Reporting
    # =================================================================
    path("bi/reports/", PlaceholderView.as_view(key="bi.reports"), name="bi-reports"),
    path("bi/exports/", PlaceholderView.as_view(key="bi.exports"), name="bi-exports"),
    path("bi/data-quality/", PlaceholderView.as_view(key="bi.data_quality"), name="bi-data-quality"),

    # =================================================================
    # ADMIN
    # =================================================================
    path("manage/tenants/", PlaceholderView.as_view(key="admin.tenants"), name="manage-tenants"),
    path("manage/users-roles/", PlaceholderView.as_view(key="admin.users_roles"), name="manage-users-roles"),
    path("manage/permissions/", PlaceholderView.as_view(key="admin.permissions"), name="manage-permissions"),
    path("manage/license/", PlaceholderView.as_view(key="admin.license"), name="manage-license"),
    path("manage/logs/", PlaceholderView.as_view(key="admin.logs"), name="manage-logs"),
    path("manage/settings/", PlaceholderView.as_view(key="admin.settings"), name="manage-settings"),
]
