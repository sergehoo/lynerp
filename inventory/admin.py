from __future__ import annotations

from django.contrib import admin

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


@admin.register(ArticleCategory)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "tenant", "parent", "is_active")
    list_filter = ("tenant", "is_active")
    search_fields = ("name", "code")


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = ("sku", "name", "tenant", "category", "purchase_price", "sale_price", "min_stock", "is_active")
    list_filter = ("tenant", "is_active", "category")
    search_fields = ("sku", "name", "barcode")


@admin.register(Warehouse)
class WarehouseAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "tenant", "is_active")
    list_filter = ("tenant", "is_active")


@admin.register(Inventory)
class InventoryAdmin(admin.ModelAdmin):
    list_display = ("article", "warehouse", "tenant", "quantity", "reserved_quantity", "last_movement_at")
    list_filter = ("tenant", "warehouse")
    readonly_fields = ("quantity", "reserved_quantity", "last_movement_at")


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ("article", "warehouse", "movement_type", "quantity", "movement_date", "user", "tenant")
    list_filter = ("tenant", "movement_type", "warehouse")
    search_fields = ("article__sku", "reference")
    readonly_fields = ("created_at", "updated_at")


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "tenant", "email", "rating", "is_active")
    list_filter = ("tenant", "is_active")
    search_fields = ("code", "name", "email")


class POLineInline(admin.TabularInline):
    model = PurchaseOrderLine
    extra = 0


@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    list_display = ("order_number", "tenant", "supplier", "status", "order_date", "expected_date")
    list_filter = ("tenant", "status", "supplier")
    search_fields = ("order_number",)
    inlines = [POLineInline]


class GoodsReceiptLineInline(admin.TabularInline):
    model = GoodsReceiptLine
    extra = 0


@admin.register(GoodsReceipt)
class GoodsReceiptAdmin(admin.ModelAdmin):
    list_display = ("receipt_number", "tenant", "purchase_order", "warehouse", "received_at")
    list_filter = ("tenant", "warehouse")
    inlines = [GoodsReceiptLineInline]


@admin.register(StockAlert)
class StockAlertAdmin(admin.ModelAdmin):
    list_display = ("article", "warehouse", "alert_type", "status", "quantity_at_alert", "tenant", "created_at")
    list_filter = ("tenant", "alert_type", "status")
