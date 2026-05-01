"""
Signaux qui auto-créent des notifications + audit events lors d'événements
métier clés.

- ``Payslip.status -> APPROVED`` → notif employé "bulletin disponible".
- ``StockAlert`` créée → notif aux managers du tenant.
- ``AIAction.status -> EXECUTED`` → audit event + notif initiateur.

Tous les imports d'apps sont protégés (ImportError → no-op) pour permettre
au projet de tourner même si certaines apps sont désactivées.
"""
from __future__ import annotations

import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from workflows.models import (
    AuditEvent,
    Notification,
    NotificationLevel,
)

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Paie
# --------------------------------------------------------------------------- #
def _hook_payroll_signals():
    try:
        from payroll.models import Payslip, PayslipStatus
    except Exception:  # noqa: BLE001
        return

    @receiver(post_save, sender=Payslip)
    def on_payslip_saved(sender, instance: Payslip, created, update_fields=None, **kwargs):
        if instance.status != PayslipStatus.APPROVED:
            return
        # Notif salarié si user_account lié
        user = getattr(instance.employee, "user_account", None)
        if user is None:
            return
        try:
            Notification.objects.create(
                tenant=instance.tenant,
                user=user,
                title=f"Bulletin {instance.slip_number} disponible",
                body=(
                    f"Votre bulletin de paie {instance.period.label} a été validé. "
                    f"Net à payer : {instance.net_amount} {instance.currency}."
                ),
                level=NotificationLevel.INFO,
                url=f"/payroll/payslips/{instance.id}/",
            )
        except Exception:  # noqa: BLE001
            logger.exception("Failed to create payslip notification")


# --------------------------------------------------------------------------- #
# Stock — alertes
# --------------------------------------------------------------------------- #
def _hook_inventory_signals():
    try:
        from inventory.models import StockAlert, StockAlertType
        from tenants.models import TenantUser
    except Exception:  # noqa: BLE001
        return

    @receiver(post_save, sender=StockAlert)
    def on_stock_alert(sender, instance: StockAlert, created, **kwargs):
        if not created:
            return
        # Notif aux managers du tenant
        managers = TenantUser.objects.filter(
            tenant=instance.tenant,
            is_active=True,
            role__in=["OWNER", "ADMIN", "MANAGER"],
        ).select_related("user")[:20]
        level = (
            NotificationLevel.ERROR
            if instance.alert_type == StockAlertType.OUT_OF_STOCK
            else NotificationLevel.WARNING
        )
        for m in managers:
            try:
                Notification.objects.create(
                    tenant=instance.tenant,
                    user=m.user,
                    title=f"Alerte stock : {instance.get_alert_type_display()}",
                    body=(
                        f"{instance.article.sku} — {instance.article.name} | "
                        f"Quantité : {instance.quantity_at_alert}"
                    ),
                    level=level,
                    url=f"/inventory/alerts/",
                )
            except Exception:  # noqa: BLE001
                logger.exception("Failed to create stock alert notification")

        try:
            AuditEvent.objects.create(
                tenant=instance.tenant,
                event_type=f"inventory.alert.{instance.alert_type.lower()}",
                severity="HIGH" if instance.alert_type == StockAlertType.OUT_OF_STOCK else "MEDIUM",
                target_model="inventory.StockAlert",
                target_id=str(instance.id),
                description=f"Alerte stock {instance.alert_type} sur {instance.article.sku}",
                metadata={
                    "article": instance.article.sku,
                    "warehouse": getattr(instance.warehouse, "code", None),
                    "quantity": float(instance.quantity_at_alert),
                },
            )
        except Exception:  # noqa: BLE001
            logger.exception("Failed to create audit event for stock alert")


# --------------------------------------------------------------------------- #
# IA — actions exécutées
# --------------------------------------------------------------------------- #
def _hook_ai_signals():
    try:
        from ai_assistant.models import AIAction, AIActionStatus
    except Exception:  # noqa: BLE001
        return

    @receiver(post_save, sender=AIAction)
    def on_ai_action(sender, instance: AIAction, created, **kwargs):
        if instance.status not in {AIActionStatus.EXECUTED, AIActionStatus.FAILED}:
            return
        if instance.proposed_by is None:
            return
        ok = instance.status == AIActionStatus.EXECUTED
        try:
            Notification.objects.create(
                tenant=instance.tenant,
                user=instance.proposed_by,
                title=f"Action IA {'exécutée' if ok else 'échouée'} : {instance.title}",
                body=(
                    "L'action que vous aviez proposée a été exécutée."
                    if ok else
                    f"L'exécution a échoué : {instance.error_message[:200]}"
                ),
                level=NotificationLevel.SUCCESS if ok else NotificationLevel.ERROR,
                url=f"/ai/actions/{instance.id}/",
            )
        except Exception:  # noqa: BLE001
            logger.exception("Failed to create AI action notification")


# Branchements (appelés depuis WorkflowsConfig.ready())
def connect_signals() -> None:
    _hook_payroll_signals()
    _hook_inventory_signals()
    _hook_ai_signals()
