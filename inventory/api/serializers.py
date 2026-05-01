from __future__ import annotations

from rest_framework import serializers

from inventory.models import (
    Article,
    ArticleCategory,
    GoodsReceipt,
    GoodsReceiptLine,
    Inventory,
    PurchaseOrder,
    PurchaseOrderLine,
    StockAlert,
    StockMovement,
    Supplier,
    Warehouse,
)


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ArticleCategory
        fields = "__all__"
        read_only_fields = ["id", "tenant", "created_at", "updated_at"]


class ArticleSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)
    total_stock = serializers.SerializerMethodField()

    class Meta:
        model = Article
        fields = [
            "id", "sku", "name", "description",
            "category", "category_name", "unit", "barcode",
            "purchase_price", "sale_price", "currency",
            "min_stock", "max_stock", "safety_stock", "lead_time_days",
            "is_active", "total_stock",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "tenant", "category_name", "total_stock", "created_at", "updated_at"]

    def get_total_stock(self, obj) -> float:
        return float(sum(i.quantity for i in obj.inventories.all()) or 0)


class WarehouseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Warehouse
        fields = "__all__"
        read_only_fields = ["id", "tenant", "created_at", "updated_at"]


class InventorySerializer(serializers.ModelSerializer):
    article_sku = serializers.CharField(source="article.sku", read_only=True)
    article_name = serializers.CharField(source="article.name", read_only=True)
    warehouse_code = serializers.CharField(source="warehouse.code", read_only=True)
    available_quantity = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True,
    )

    class Meta:
        model = Inventory
        fields = [
            "id", "article", "article_sku", "article_name",
            "warehouse", "warehouse_code",
            "quantity", "reserved_quantity", "available_quantity",
            "last_movement_at",
        ]
        read_only_fields = fields


class StockMovementSerializer(serializers.ModelSerializer):
    article_sku = serializers.CharField(source="article.sku", read_only=True)

    class Meta:
        model = StockMovement
        fields = [
            "id", "article", "article_sku",
            "warehouse", "target_warehouse",
            "movement_type", "quantity", "unit_cost",
            "reference", "movement_date", "user", "note",
            "created_at",
        ]
        read_only_fields = ["id", "tenant", "user", "article_sku", "created_at"]


class SupplierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supplier
        fields = "__all__"
        read_only_fields = ["id", "tenant", "created_at", "updated_at"]


class PurchaseOrderLineSerializer(serializers.ModelSerializer):
    article_sku = serializers.CharField(source="article.sku", read_only=True)
    line_total = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True,
    )

    class Meta:
        model = PurchaseOrderLine
        fields = [
            "id", "purchase_order", "article", "article_sku",
            "description", "quantity", "unit_price",
            "received_quantity", "line_total", "sort_order",
        ]
        read_only_fields = ["id", "tenant", "article_sku", "line_total"]


class PurchaseOrderSerializer(serializers.ModelSerializer):
    supplier_name = serializers.CharField(source="supplier.name", read_only=True)
    total_amount = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True,
    )
    lines = PurchaseOrderLineSerializer(many=True, read_only=True)

    class Meta:
        model = PurchaseOrder
        fields = [
            "id", "order_number", "supplier", "supplier_name",
            "warehouse", "order_date", "expected_date",
            "currency", "status", "notes", "total_amount",
            "requested_by", "approved_by", "approved_at",
            "lines", "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "tenant", "supplier_name", "total_amount",
            "approved_by", "approved_at", "created_at", "updated_at",
        ]


class GoodsReceiptLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = GoodsReceiptLine
        fields = "__all__"
        read_only_fields = ["id", "tenant", "created_at", "updated_at"]


class GoodsReceiptSerializer(serializers.ModelSerializer):
    lines = GoodsReceiptLineSerializer(many=True, read_only=True)

    class Meta:
        model = GoodsReceipt
        fields = "__all__"
        read_only_fields = ["id", "tenant", "received_by", "lines", "created_at", "updated_at"]


class StockAlertSerializer(serializers.ModelSerializer):
    article_sku = serializers.CharField(source="article.sku", read_only=True)

    class Meta:
        model = StockAlert
        fields = [
            "id", "article", "article_sku", "warehouse",
            "alert_type", "quantity_at_alert", "status",
            "acknowledged_by", "acknowledged_at", "note",
            "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "tenant", "article_sku", "acknowledged_by", "acknowledged_at",
            "created_at", "updated_at",
        ]
