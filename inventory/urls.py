"""URLs web Stock ``/inventory/...``."""
from __future__ import annotations

from django.urls import path

from inventory.views import (
    ArticleListView,
    InventoryDashboardView,
    StockAlertListView,
)

app_name = "inventory"

urlpatterns = [
    path("", InventoryDashboardView.as_view(), name="dashboard"),
    path("articles/", ArticleListView.as_view(), name="article-list"),
    path("alerts/", StockAlertListView.as_view(), name="alert-list"),
]
