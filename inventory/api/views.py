"""API DRF du module Stock."""
from __future__ import annotations

import logging

from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ai_assistant.permissions import CanApproveAIAction
from hr.api.views import BaseTenantViewSet
from inventory.api.serializers import (
    ArticleSerializer,
    CategorySerializer,
    GoodsReceiptSerializer,
    InventorySerializer,
    PurchaseOrderLineSerializer,
    PurchaseOrderSerializer,
    StockAlertSerializer,
    StockMovementSerializer,
    SupplierSerializer,
    WarehouseSerializer,
)
from inventory.models import (
    Article,
    ArticleCategory,
    GoodsReceipt,
    Inventory,
    PurchaseOrder,
    PurchaseOrderLine,
    PurchaseOrderStatus,
    StockAlert,
    StockAlertStatus,
    StockMovement,
    Supplier,
    Warehouse,
)

logger = logging.getLogger(__name__)


class CategoryViewSet(BaseTenantViewSet):
    queryset = ArticleCategory.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [IsAuthenticated]


class ArticleViewSet(BaseTenantViewSet):
    queryset = Article.objects.all().select_related("category")
    serializer_class = ArticleSerializer
    permission_classes = [IsAuthenticated]
    search_fields = ["sku", "name", "barcode"]
    ordering_fields = ["sku", "name", "purchase_price"]


class WarehouseViewSet(BaseTenantViewSet):
    queryset = Warehouse.objects.all()
    serializer_class = WarehouseSerializer
    permission_classes = [IsAuthenticated]


class InventoryViewSet(BaseTenantViewSet):
    queryset = Inventory.objects.all().select_related("article", "warehouse")
    serializer_class = InventorySerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "head", "options"]  # lecture seule


class StockMovementViewSet(BaseTenantViewSet):
    queryset = StockMovement.objects.all().select_related("article", "warehouse")
    serializer_class = StockMovementSerializer
    permission_classes = [IsAuthenticated]
    ordering_fields = ["-movement_date"]
    http_method_names = ["get", "post", "head", "options"]  # pas d'édition

    def perform_create(self, serializer):
        serializer.save(user=self.request.user, movement_date=timezone.now())


class SupplierViewSet(BaseTenantViewSet):
    queryset = Supplier.objects.all()
    serializer_class = SupplierSerializer
    permission_classes = [IsAuthenticated]
    search_fields = ["code", "name", "email"]


class PurchaseOrderViewSet(BaseTenantViewSet):
    queryset = PurchaseOrder.objects.all().select_related("supplier", "warehouse").prefetch_related("lines")
    serializer_class = PurchaseOrderSerializer
    permission_classes = [IsAuthenticated]
    search_fields = ["order_number", "supplier__name"]

    @action(
        detail=True, methods=["post"], url_path="submit",
        permission_classes=[IsAuthenticated],
    )
    def submit(self, request, pk=None):
        po: PurchaseOrder = self.get_object()
        if po.status != PurchaseOrderStatus.DRAFT:
            return Response(
                {"detail": "Bon de commande déjà soumis.", "code": "invalid_status"},
                status=status.HTTP_409_CONFLICT,
            )
        po.status = PurchaseOrderStatus.SUBMITTED
        po.save(update_fields=["status", "updated_at"])
        return Response(PurchaseOrderSerializer(po).data)

    @action(
        detail=True, methods=["post"], url_path="approve",
        permission_classes=[IsAuthenticated, CanApproveAIAction],
    )
    def approve(self, request, pk=None):
        po: PurchaseOrder = self.get_object()
        if po.status != PurchaseOrderStatus.SUBMITTED:
            return Response(
                {"detail": "Doit être soumis avant approbation.", "code": "invalid_status"},
                status=status.HTTP_409_CONFLICT,
            )
        po.status = PurchaseOrderStatus.APPROVED
        po.approved_by = request.user
        po.approved_at = timezone.now()
        po.save(update_fields=["status", "approved_by", "approved_at", "updated_at"])
        return Response(PurchaseOrderSerializer(po).data)


class PurchaseOrderLineViewSet(BaseTenantViewSet):
    queryset = PurchaseOrderLine.objects.all()
    serializer_class = PurchaseOrderLineSerializer
    permission_classes = [IsAuthenticated]


class GoodsReceiptViewSet(BaseTenantViewSet):
    queryset = GoodsReceipt.objects.all().select_related("warehouse").prefetch_related("lines")
    serializer_class = GoodsReceiptSerializer
    permission_classes = [IsAuthenticated]


class StockAlertViewSet(BaseTenantViewSet):
    queryset = StockAlert.objects.all().select_related("article", "warehouse")
    serializer_class = StockAlertSerializer
    permission_classes = [IsAuthenticated]

    @action(detail=True, methods=["post"], url_path="acknowledge")
    def acknowledge(self, request, pk=None):
        alert: StockAlert = self.get_object()
        alert.status = StockAlertStatus.ACKNOWLEDGED
        alert.acknowledged_by = request.user
        alert.acknowledged_at = timezone.now()
        alert.save(update_fields=["status", "acknowledged_by", "acknowledged_at", "updated_at"])
        return Response(StockAlertSerializer(alert).data)

    @action(detail=True, methods=["post"], url_path="resolve")
    def resolve(self, request, pk=None):
        alert: StockAlert = self.get_object()
        alert.status = StockAlertStatus.RESOLVED
        alert.save(update_fields=["status", "updated_at"])
        return Response(StockAlertSerializer(alert).data)
