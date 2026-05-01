"""URLs API ``/api/inventory/...``."""
from __future__ import annotations

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from inventory.api.views import (
    ArticleViewSet,
    CategoryViewSet,
    GoodsReceiptViewSet,
    InventoryViewSet,
    PurchaseOrderLineViewSet,
    PurchaseOrderViewSet,
    StockAlertViewSet,
    StockMovementViewSet,
    SupplierViewSet,
    WarehouseViewSet,
)

app_name = "inventory_api"

router = DefaultRouter(trailing_slash=True)
router.register(r"categories", CategoryViewSet, basename="inv-categories")
router.register(r"articles", ArticleViewSet, basename="inv-articles")
router.register(r"warehouses", WarehouseViewSet, basename="inv-warehouses")
router.register(r"inventories", InventoryViewSet, basename="inv-inventories")
router.register(r"movements", StockMovementViewSet, basename="inv-movements")
router.register(r"suppliers", SupplierViewSet, basename="inv-suppliers")
router.register(r"purchase-orders", PurchaseOrderViewSet, basename="inv-pos")
router.register(r"purchase-order-lines", PurchaseOrderLineViewSet, basename="inv-po-lines")
router.register(r"goods-receipts", GoodsReceiptViewSet, basename="inv-receipts")
router.register(r"alerts", StockAlertViewSet, basename="inv-alerts")

from inventory.api.ai_views import (
    AnalyzeSuppliersView,
    ForecastStockoutsView,
    RecommendReorderView,
)

urlpatterns = [
    # Raccourcis IA stock
    path("ai/forecast-stockouts/", ForecastStockoutsView.as_view(), name="ai-forecast-stockouts"),
    path("ai/recommend-reorder/", RecommendReorderView.as_view(), name="ai-recommend-reorder"),
    path("ai/analyze-suppliers/", AnalyzeSuppliersView.as_view(), name="ai-analyze-suppliers"),
    # Routeur DRF
    path("", include(router.urls)),
]
