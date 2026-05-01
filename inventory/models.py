"""
Modèles du module Stock / Achats.

Architecture :

    ArticleCategory (catégories hiérarchiques)
        ▼
    Article (référence : SKU + prix + seuils)
        ▼
    StockMovement (entrées/sorties/ajustements/transferts) → mise à jour automatique du stock
        ▼
    Inventory (snapshot agrégé par article × entrepôt)

    Supplier ── PurchaseOrder ── PurchaseOrderLine
                       │
                       └── GoodsReceipt ── GoodsReceiptLine

    StockAlert (seuil bas, ruptures)

Tout est multi-tenant strict via ``TenantOwnedModel``.
"""
from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

from Lyneerp.core.models import TenantOwnedModel, UUIDPkModel


# --------------------------------------------------------------------------- #
# Référentiels
# --------------------------------------------------------------------------- #
class ArticleCategory(UUIDPkModel, TenantOwnedModel):
    name = models.CharField(max_length=120)
    code = models.CharField(max_length=40, blank=True)
    parent = models.ForeignKey(
        "self", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="children",
    )
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = "inventory_category"
        verbose_name = "Catégorie article"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "code"],
                condition=~models.Q(code=""),
                name="uniq_inv_category_code_per_tenant",
            ),
        ]

    def __str__(self) -> str:
        return self.name


class StockUnit(models.TextChoices):
    UNIT = "UNIT", "Unité"
    KG = "KG", "Kilogramme"
    LITER = "L", "Litre"
    METER = "M", "Mètre"
    BOX = "BOX", "Carton"
    PALLET = "PALLET", "Palette"


class Article(UUIDPkModel, TenantOwnedModel):
    """Référence article (SKU)."""

    sku = models.CharField(max_length=60, db_index=True)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    category = models.ForeignKey(
        ArticleCategory, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="articles",
    )
    unit = models.CharField(max_length=10, choices=StockUnit.choices, default=StockUnit.UNIT)
    barcode = models.CharField(max_length=64, blank=True, db_index=True)

    # Prix
    purchase_price = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal("0"),
        validators=[MinValueValidator(0)],
    )
    sale_price = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal("0"),
        validators=[MinValueValidator(0)],
    )
    currency = models.CharField(max_length=3, default="XOF")

    # Seuils
    min_stock = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal("0"),
        help_text="Seuil mini : alerte de réapprovisionnement.",
    )
    max_stock = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal("0"),
        help_text="Seuil maxi : éviter le sur-stockage.",
    )
    safety_stock = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal("0"),
        help_text="Stock de sécurité (en plus du seuil mini).",
    )

    # Délai approvisionnement (en jours)
    lead_time_days = models.PositiveIntegerField(default=7)

    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = "inventory_article"
        verbose_name = "Article"
        verbose_name_plural = "Articles"
        ordering = ["sku"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "sku"],
                name="uniq_inv_article_sku_per_tenant",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "is_active"]),
            models.Index(fields=["barcode"]),
        ]

    def __str__(self) -> str:
        return f"{self.sku} — {self.name}"


class Warehouse(UUIDPkModel, TenantOwnedModel):
    code = models.CharField(max_length=40)
    name = models.CharField(max_length=160)
    address = models.TextField(blank=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = "inventory_warehouse"
        verbose_name = "Entrepôt"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "code"],
                name="uniq_inv_warehouse_code_per_tenant",
            ),
        ]

    def __str__(self) -> str:
        return self.name


# --------------------------------------------------------------------------- #
# Stocks et mouvements
# --------------------------------------------------------------------------- #
class Inventory(UUIDPkModel, TenantOwnedModel):
    """
    Snapshot du stock courant pour un (article, entrepôt). Mis à jour
    automatiquement à chaque ``StockMovement.save()`` via signal ou via
    le service ``stock_engine``.
    """

    article = models.ForeignKey(
        Article, on_delete=models.CASCADE, related_name="inventories",
    )
    warehouse = models.ForeignKey(
        Warehouse, on_delete=models.CASCADE, related_name="inventories",
    )
    quantity = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    reserved_quantity = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal("0"),
        help_text="Quantité réservée (commandes en cours).",
    )
    last_movement_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "inventory_inventory"
        verbose_name = "Stock"
        verbose_name_plural = "Stocks"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "article", "warehouse"],
                name="uniq_inv_inventory_per_warehouse",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "article"]),
            models.Index(fields=["tenant", "warehouse"]),
        ]

    @property
    def available_quantity(self) -> Decimal:
        return (self.quantity or Decimal("0")) - (self.reserved_quantity or Decimal("0"))


class MovementType(models.TextChoices):
    IN = "IN", "Entrée"
    OUT = "OUT", "Sortie"
    ADJUST = "ADJUST", "Ajustement (inventaire)"
    TRANSFER = "TRANSFER", "Transfert"


class StockMovement(UUIDPkModel, TenantOwnedModel):
    """Un mouvement de stock (atomique, source de vérité du stock)."""

    article = models.ForeignKey(
        Article, on_delete=models.PROTECT, related_name="movements",
    )
    warehouse = models.ForeignKey(
        Warehouse, on_delete=models.PROTECT, related_name="movements",
    )
    target_warehouse = models.ForeignKey(
        Warehouse, null=True, blank=True,
        on_delete=models.PROTECT, related_name="incoming_transfers",
        help_text="Pour TRANSFER : entrepôt de destination.",
    )
    movement_type = models.CharField(max_length=10, choices=MovementType.choices, db_index=True)
    quantity = models.DecimalField(
        max_digits=14, decimal_places=2,
        validators=[MinValueValidator(0)],
    )
    unit_cost = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal("0"),
        help_text="Coût unitaire pour valorisation.",
    )

    # Liens optionnels
    reference = models.CharField(max_length=120, blank=True)
    source_model = models.CharField(max_length=64, blank=True)
    source_object_id = models.CharField(max_length=64, blank=True)
    movement_date = models.DateTimeField()
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="stock_movements",
    )
    note = models.TextField(blank=True)

    class Meta:
        db_table = "inventory_movement"
        verbose_name = "Mouvement de stock"
        ordering = ["-movement_date"]
        indexes = [
            models.Index(fields=["tenant", "article", "-movement_date"]),
            models.Index(fields=["tenant", "movement_type"]),
            models.Index(fields=["tenant", "warehouse"]),
        ]


# --------------------------------------------------------------------------- #
# Fournisseurs et achats
# --------------------------------------------------------------------------- #
class Supplier(UUIDPkModel, TenantOwnedModel):
    code = models.CharField(max_length=40)
    name = models.CharField(max_length=200)
    contact_name = models.CharField(max_length=160, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=40, blank=True)
    address = models.TextField(blank=True)
    payment_terms_days = models.PositiveIntegerField(default=30)
    is_active = models.BooleanField(default=True, db_index=True)
    rating = models.DecimalField(
        max_digits=3, decimal_places=1, default=Decimal("0"),
        help_text="Note interne fournisseur (0-5).",
    )

    class Meta:
        db_table = "inventory_supplier"
        verbose_name = "Fournisseur"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "code"],
                name="uniq_inv_supplier_code_per_tenant",
            ),
        ]

    def __str__(self) -> str:
        return self.name


class PurchaseOrderStatus(models.TextChoices):
    DRAFT = "DRAFT", "Brouillon"
    SUBMITTED = "SUBMITTED", "Soumis"
    APPROVED = "APPROVED", "Approuvé"
    CONFIRMED = "CONFIRMED", "Confirmé fournisseur"
    PARTIAL = "PARTIAL", "Réception partielle"
    RECEIVED = "RECEIVED", "Reçu"
    CANCELLED = "CANCELLED", "Annulé"


class PurchaseOrder(UUIDPkModel, TenantOwnedModel):
    order_number = models.CharField(max_length=40, db_index=True)
    supplier = models.ForeignKey(
        Supplier, on_delete=models.PROTECT, related_name="purchase_orders",
    )
    warehouse = models.ForeignKey(
        Warehouse, on_delete=models.PROTECT, related_name="purchase_orders",
        help_text="Entrepôt de réception.",
    )
    order_date = models.DateField()
    expected_date = models.DateField(null=True, blank=True)
    currency = models.CharField(max_length=3, default="XOF")
    status = models.CharField(
        max_length=10, choices=PurchaseOrderStatus.choices,
        default=PurchaseOrderStatus.DRAFT, db_index=True,
    )
    notes = models.TextField(blank=True)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="purchase_orders_requested",
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="purchase_orders_approved",
    )
    approved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "inventory_purchase_order"
        verbose_name = "Bon de commande"
        verbose_name_plural = "Bons de commande"
        ordering = ["-order_date"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "order_number"],
                name="uniq_inv_po_number_per_tenant",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "status", "-order_date"]),
        ]

    @property
    def total_amount(self) -> Decimal:
        return sum(
            ((line.quantity or Decimal("0")) * (line.unit_price or Decimal("0")))
            for line in self.lines.all()
        ) or Decimal("0")


class PurchaseOrderLine(UUIDPkModel, TenantOwnedModel):
    purchase_order = models.ForeignKey(
        PurchaseOrder, on_delete=models.CASCADE, related_name="lines",
    )
    article = models.ForeignKey(Article, on_delete=models.PROTECT)
    description = models.CharField(max_length=200, blank=True)
    quantity = models.DecimalField(max_digits=14, decimal_places=2)
    unit_price = models.DecimalField(max_digits=14, decimal_places=2)
    received_quantity = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    sort_order = models.PositiveIntegerField(default=100)

    class Meta:
        db_table = "inventory_po_line"
        ordering = ["sort_order"]

    @property
    def line_total(self) -> Decimal:
        return (self.quantity or Decimal("0")) * (self.unit_price or Decimal("0"))


class GoodsReceipt(UUIDPkModel, TenantOwnedModel):
    receipt_number = models.CharField(max_length=40, db_index=True)
    purchase_order = models.ForeignKey(
        PurchaseOrder, null=True, blank=True,
        on_delete=models.PROTECT, related_name="receipts",
    )
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="receipts")
    received_at = models.DateTimeField()
    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="goods_receipts",
    )
    note = models.TextField(blank=True)

    class Meta:
        db_table = "inventory_goods_receipt"
        verbose_name = "Bon de réception"
        ordering = ["-received_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "receipt_number"],
                name="uniq_inv_receipt_number_per_tenant",
            ),
        ]


class GoodsReceiptLine(UUIDPkModel, TenantOwnedModel):
    receipt = models.ForeignKey(GoodsReceipt, on_delete=models.CASCADE, related_name="lines")
    article = models.ForeignKey(Article, on_delete=models.PROTECT)
    quantity = models.DecimalField(max_digits=14, decimal_places=2)
    unit_cost = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    purchase_order_line = models.ForeignKey(
        PurchaseOrderLine, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="receipt_lines",
    )

    class Meta:
        db_table = "inventory_goods_receipt_line"


# --------------------------------------------------------------------------- #
# Alertes
# --------------------------------------------------------------------------- #
class StockAlertType(models.TextChoices):
    LOW_STOCK = "LOW_STOCK", "Stock bas"
    OUT_OF_STOCK = "OUT_OF_STOCK", "Rupture"
    OVERSTOCK = "OVERSTOCK", "Sur-stock"


class StockAlertStatus(models.TextChoices):
    OPEN = "OPEN", "Ouverte"
    ACKNOWLEDGED = "ACK", "Reconnue"
    RESOLVED = "RESOLVED", "Résolue"


class StockAlert(UUIDPkModel, TenantOwnedModel):
    article = models.ForeignKey(
        Article, on_delete=models.CASCADE, related_name="alerts",
    )
    warehouse = models.ForeignKey(
        Warehouse, null=True, blank=True,
        on_delete=models.CASCADE, related_name="alerts",
    )
    alert_type = models.CharField(max_length=14, choices=StockAlertType.choices, db_index=True)
    quantity_at_alert = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    status = models.CharField(
        max_length=10, choices=StockAlertStatus.choices,
        default=StockAlertStatus.OPEN, db_index=True,
    )
    acknowledged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="stock_alerts_acknowledged",
    )
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    note = models.TextField(blank=True)

    class Meta:
        db_table = "inventory_stock_alert"
        verbose_name = "Alerte stock"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "alert_type", "status"]),
        ]
