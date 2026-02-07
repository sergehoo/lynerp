# core_finance/models_base.py
from __future__ import annotations

import uuid
from decimal import Decimal
from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

from tenants.models import Tenant


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class TenantOwnedModel(TimeStampedModel):
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name="%(app_label)s_%(class)ss",
        related_query_name="%(app_label)s_%(class)s",
        db_index=True,
    )

    class Meta:
        abstract = True
        indexes = [models.Index(fields=["tenant"])]


class UUIDPkModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


class SoftDeleteModel(models.Model):
    is_deleted = models.BooleanField(default=False, db_index=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        abstract = True

    def soft_delete(self):
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save(update_fields=["is_deleted", "deleted_at"])


class Currency(models.TextChoices):
    XOF = "XOF", "Franc CFA (XOF)"
    XAF = "XAF", "Franc CFA (XAF)"
    EUR = "EUR", "Euro"
    USD = "USD", "Dollar US"
    GBP = "GBP", "Livre Sterling"


class MoneyFieldMixin(models.Model):
    """
    Stockage "money-like" standard : Decimal(14,2). 14 digits = suffisant pour ERP.
    """
    class Meta:
        abstract = True

    @staticmethod
    def quantize_2(amount: Decimal) -> Decimal:
        return (amount or Decimal("0")).quantize(Decimal("0.01"))