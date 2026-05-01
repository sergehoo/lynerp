"""
API DRF du module Paie.

Tous les viewsets héritent de ``BaseTenantViewSet`` (multi-tenant strict).
Les actions critiques (calcul, clôture) demandent un rôle élevé.
"""
from __future__ import annotations

import logging
from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ai_assistant.permissions import CanApproveAIAction
from hr.api.views import BaseTenantViewSet
from payroll.api.serializers import (
    EmployeePayrollProfileSerializer,
    PayrollAdjustmentSerializer,
    PayrollItemSerializer,
    PayrollJournalSerializer,
    PayrollPeriodSerializer,
    PayrollProfileItemSerializer,
    PayrollProfileSerializer,
    PayslipDetailSerializer,
    PayslipSerializer,
)
from payroll.models import (
    EmployeePayrollProfile,
    PayrollAdjustment,
    PayrollItem,
    PayrollJournal,
    PayrollPeriod,
    PayrollPeriodStatus,
    PayrollProfile,
    PayrollProfileItem,
    Payslip,
    PayslipStatus,
)
from payroll.services.engine import PayrollEngine

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Référentiels
# --------------------------------------------------------------------------- #
class PayrollItemViewSet(BaseTenantViewSet):
    queryset = PayrollItem.objects.all()
    serializer_class = PayrollItemSerializer
    permission_classes = [IsAuthenticated]
    search_fields = ["code", "name"]


class PayrollProfileViewSet(BaseTenantViewSet):
    queryset = PayrollProfile.objects.all()
    serializer_class = PayrollProfileSerializer
    permission_classes = [IsAuthenticated]


class PayrollProfileItemViewSet(BaseTenantViewSet):
    queryset = PayrollProfileItem.objects.all()
    serializer_class = PayrollProfileItemSerializer
    permission_classes = [IsAuthenticated]


class EmployeePayrollProfileViewSet(BaseTenantViewSet):
    queryset = EmployeePayrollProfile.objects.all()
    serializer_class = EmployeePayrollProfileSerializer
    permission_classes = [IsAuthenticated]


# --------------------------------------------------------------------------- #
# Périodes
# --------------------------------------------------------------------------- #
class PayrollPeriodViewSet(BaseTenantViewSet):
    queryset = PayrollPeriod.objects.all()
    serializer_class = PayrollPeriodSerializer
    permission_classes = [IsAuthenticated]

    @action(
        detail=True, methods=["post"],
        url_path="compute", permission_classes=[IsAuthenticated, CanApproveAIAction],
    )
    def compute(self, request, pk=None):
        """Recalcule tous les bulletins de la période."""
        period: PayrollPeriod = self.get_object()
        if period.status == PayrollPeriodStatus.CLOSED:
            return Response(
                {"detail": "Période clôturée.", "code": "period_closed"},
                status=status.HTTP_409_CONFLICT,
            )
        engine = PayrollEngine(period=period)
        try:
            slips = engine.compute_period()
        except Exception as exc:  # noqa: BLE001
            logger.exception("Compute period failed")
            return Response(
                {"detail": str(exc), "code": "compute_failed"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        period.status = PayrollPeriodStatus.LOCKED
        period.save(update_fields=["status", "updated_at"])
        return Response({
            "period": PayrollPeriodSerializer(period).data,
            "computed": len(slips),
        })

    @action(
        detail=True, methods=["post"], url_path="close",
        permission_classes=[IsAuthenticated, CanApproveAIAction],
    )
    def close(self, request, pk=None):
        """Clôture la période (verrouille définitivement les bulletins)."""
        period: PayrollPeriod = self.get_object()
        if period.status == PayrollPeriodStatus.CLOSED:
            return Response(
                {"detail": "Déjà clôturée.", "code": "already_closed"},
                status=status.HTTP_409_CONFLICT,
            )
        # Tous les bulletins doivent être COMPUTED ou APPROVED.
        bad = period.payslips.exclude(
            status__in=[PayslipStatus.COMPUTED, PayslipStatus.APPROVED, PayslipStatus.PAID, PayslipStatus.CANCELLED]
        ).count()
        if bad:
            return Response(
                {"detail": f"{bad} bulletins en brouillon ; calculer avant clôture.", "code": "drafts_remaining"},
                status=status.HTTP_409_CONFLICT,
            )

        with transaction.atomic():
            # Génère le journal de paie.
            agg = period.payslips.aggregate(
                gross=__import__("django.db.models", fromlist=["Sum"]).Sum("gross_amount"),
                ded=__import__("django.db.models", fromlist=["Sum"]).Sum("employee_deductions"),
                emp=__import__("django.db.models", fromlist=["Sum"]).Sum("employer_charges"),
                tax=__import__("django.db.models", fromlist=["Sum"]).Sum("income_tax"),
                net=__import__("django.db.models", fromlist=["Sum"]).Sum("net_amount"),
            )
            PayrollJournal.objects.update_or_create(
                tenant=period.tenant, period=period,
                defaults={
                    "total_gross": agg["gross"] or 0,
                    "total_employee_deductions": agg["ded"] or 0,
                    "total_employer_charges": agg["emp"] or 0,
                    "total_income_tax": agg["tax"] or 0,
                    "total_net": agg["net"] or 0,
                    "is_posted": False,
                },
            )
            period.status = PayrollPeriodStatus.CLOSED
            period.save(update_fields=["status", "updated_at"])

        return Response(PayrollPeriodSerializer(period).data)


# --------------------------------------------------------------------------- #
# Bulletins
# --------------------------------------------------------------------------- #
class PayslipViewSet(BaseTenantViewSet):
    queryset = Payslip.objects.all().select_related(
        "employee", "period", "employee_profile"
    )
    permission_classes = [IsAuthenticated]
    search_fields = ["slip_number", "employee__email", "employee__first_name", "employee__last_name"]
    ordering_fields = ["created_at", "period__year", "period__month", "net_amount"]

    def get_serializer_class(self):
        if self.action == "retrieve":
            return PayslipDetailSerializer
        return PayslipSerializer

    @action(
        detail=True, methods=["post"], url_path="compute",
        permission_classes=[IsAuthenticated, CanApproveAIAction],
    )
    def compute(self, request, pk=None):
        slip: Payslip = self.get_object()
        try:
            engine = PayrollEngine(period=slip.period)
            engine.compute_payslip(slip)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Compute payslip failed")
            return Response(
                {"detail": str(exc), "code": "compute_failed"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        return Response(PayslipDetailSerializer(slip).data)

    @action(
        detail=True, methods=["post"], url_path="approve",
        permission_classes=[IsAuthenticated, CanApproveAIAction],
    )
    def approve(self, request, pk=None):
        slip: Payslip = self.get_object()
        if slip.status != PayslipStatus.COMPUTED:
            return Response(
                {"detail": "Le bulletin doit être calculé.", "code": "must_be_computed"},
                status=status.HTTP_409_CONFLICT,
            )
        slip.status = PayslipStatus.APPROVED
        slip.approved_by = request.user
        slip.approved_at = timezone.now()
        slip.save(update_fields=["status", "approved_by", "approved_at", "updated_at"])
        return Response(PayslipSerializer(slip).data)

    @action(
        detail=True, methods=["post"], url_path="mark-paid",
        permission_classes=[IsAuthenticated, CanApproveAIAction],
    )
    def mark_paid(self, request, pk=None):
        slip: Payslip = self.get_object()
        if slip.status != PayslipStatus.APPROVED:
            return Response(
                {"detail": "Le bulletin doit être approuvé.", "code": "must_be_approved"},
                status=status.HTTP_409_CONFLICT,
            )
        slip.status = PayslipStatus.PAID
        slip.save(update_fields=["status", "updated_at"])
        return Response(PayslipSerializer(slip).data)


class PayrollAdjustmentViewSet(BaseTenantViewSet):
    queryset = PayrollAdjustment.objects.all()
    serializer_class = PayrollAdjustmentSerializer
    permission_classes = [IsAuthenticated]


class PayrollJournalViewSet(BaseTenantViewSet):
    queryset = PayrollJournal.objects.all()
    serializer_class = PayrollJournalSerializer
    permission_classes = [IsAuthenticated]
