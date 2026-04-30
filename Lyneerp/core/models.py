"""
Modèles abstraits partagés par toutes les apps LYNEERP.

Ces classes garantissent :

- une PK UUID pour les modèles métier ;
- horodatage created_at / updated_at automatique ;
- une isolation multi-tenant systématique via ``TenantOwnedModel`` ;
- la possibilité d'utiliser un manager qui filtre automatiquement
  par tenant courant si on lui passe un objet request.
"""
from __future__ import annotations

import uuid
from typing import Optional

from django.db import models


class UUIDPkModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class SoftDeleteQuerySet(models.QuerySet):
    def alive(self):
        return self.filter(is_deleted=False)

    def dead(self):
        return self.filter(is_deleted=True)

    def soft_delete(self):
        from django.utils import timezone

        return self.update(is_deleted=True, deleted_at=timezone.now())


class SoftDeleteModel(models.Model):
    is_deleted = models.BooleanField(default=False, db_index=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    objects = SoftDeleteQuerySet.as_manager()

    class Meta:
        abstract = True

    def soft_delete(self):
        from django.utils import timezone

        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save(update_fields=["is_deleted", "deleted_at"])


class TenantManager(models.Manager):
    """
    Manager qui sait filtrer automatiquement par tenant.

    Usage côté vue :

        Employee.objects.for_request(self.request)

    ou directement :

        Employee.objects.for_tenant(tenant)
    """

    def for_tenant(self, tenant) -> models.QuerySet:
        if tenant is None:
            return self.none()
        return self.filter(tenant=tenant)

    def for_request(self, request) -> models.QuerySet:
        from Lyneerp.core.tenant import resolve_tenant_from_request

        tenant = resolve_tenant_from_request(request)
        return self.for_tenant(tenant)


class TenantOwnedModel(TimeStampedModel):
    """
    Tout modèle métier multi-tenant doit hériter de cette classe.

    - ``tenant`` est non-nullable (pas de fuite par défaut).
    - ``related_name`` est calculé automatiquement par app et par modèle.
    - Index DB sur tenant et sur (tenant, created_at).
    """

    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="%(app_label)s_%(class)ss",
        related_query_name="%(app_label)s_%(class)s",
        db_index=True,
    )

    objects = TenantManager()

    class Meta:
        abstract = True
        indexes = [
            models.Index(fields=["tenant"]),
            models.Index(fields=["tenant", "created_at"]),
        ]
