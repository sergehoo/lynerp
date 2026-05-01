from __future__ import annotations

from rest_framework import serializers

from payroll.models import (
    EmployeePayrollProfile,
    PayrollAdjustment,
    PayrollItem,
    PayrollJournal,
    PayrollPeriod,
    PayrollProfile,
    PayrollProfileItem,
    Payslip,
    PayslipLine,
)


class PayrollItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = PayrollItem
        fields = "__all__"
        read_only_fields = ["id", "tenant", "created_at", "updated_at"]


class PayrollProfileItemSerializer(serializers.ModelSerializer):
    item_code = serializers.CharField(source="item.code", read_only=True)
    item_name = serializers.CharField(source="item.name", read_only=True)
    item_kind = serializers.CharField(source="item.kind", read_only=True)

    class Meta:
        model = PayrollProfileItem
        fields = [
            "id", "profile", "item", "item_code", "item_name", "item_kind",
            "sort_order", "rate_override", "amount_override", "is_optional",
        ]
        read_only_fields = ["id"]


class PayrollProfileSerializer(serializers.ModelSerializer):
    profile_items = PayrollProfileItemSerializer(many=True, read_only=True)

    class Meta:
        model = PayrollProfile
        fields = [
            "id", "code", "name", "description", "is_active",
            "profile_items", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "tenant", "created_at", "updated_at"]


class EmployeePayrollProfileSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source="employee.full_name", read_only=True)
    profile_code = serializers.CharField(source="profile.code", read_only=True)

    class Meta:
        model = EmployeePayrollProfile
        fields = [
            "id", "employee", "employee_name", "profile", "profile_code",
            "base_salary", "currency", "variables",
            "valid_from", "valid_to", "is_active",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "tenant", "created_at", "updated_at"]


class PayrollPeriodSerializer(serializers.ModelSerializer):
    payslips_count = serializers.SerializerMethodField()

    class Meta:
        model = PayrollPeriod
        fields = [
            "id", "label", "year", "month",
            "date_start", "date_end", "pay_date",
            "status", "notes", "payslips_count",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "tenant", "created_at", "updated_at", "payslips_count"]

    def get_payslips_count(self, obj):
        return obj.payslips.count()


class PayslipLineSerializer(serializers.ModelSerializer):
    item_code = serializers.CharField(source="item.code", read_only=True)

    class Meta:
        model = PayslipLine
        fields = [
            "id", "item", "item_code", "label", "kind",
            "base_amount", "rate", "amount",
            "sort_order", "metadata",
        ]
        read_only_fields = fields


class PayrollAdjustmentSerializer(serializers.ModelSerializer):
    item_code = serializers.CharField(source="item.code", read_only=True)
    total_amount = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True,
    )

    class Meta:
        model = PayrollAdjustment
        fields = [
            "id", "payslip", "item", "item_code", "label",
            "quantity", "unit_amount", "total_amount", "note",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "tenant", "total_amount", "created_at", "updated_at"]


class PayslipSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source="employee.full_name", read_only=True)
    period_label = serializers.CharField(source="period.label", read_only=True)

    class Meta:
        model = Payslip
        fields = [
            "id", "slip_number", "period", "period_label",
            "employee", "employee_name", "employee_profile",
            "gross_amount", "employee_deductions", "employer_charges",
            "taxable_base", "social_base", "income_tax", "net_amount",
            "currency", "status", "computed_at",
            "approved_by", "approved_at", "pdf_url",
            "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "tenant", "slip_number",
            "gross_amount", "employee_deductions", "employer_charges",
            "taxable_base", "social_base", "income_tax", "net_amount",
            "computed_at", "approved_by", "approved_at",
            "created_at", "updated_at",
        ]


class PayslipDetailSerializer(PayslipSerializer):
    lines = PayslipLineSerializer(many=True, read_only=True)
    adjustments = PayrollAdjustmentSerializer(many=True, read_only=True)

    class Meta(PayslipSerializer.Meta):
        fields = PayslipSerializer.Meta.fields + ["lines", "adjustments"]


class PayrollJournalSerializer(serializers.ModelSerializer):
    period_label = serializers.CharField(source="period.label", read_only=True)

    class Meta:
        model = PayrollJournal
        fields = [
            "id", "period", "period_label",
            "total_gross", "total_employee_deductions", "total_employer_charges",
            "total_income_tax", "total_net",
            "is_posted", "posted_at", "journal_entry_id",
            "created_at", "updated_at",
        ]
        read_only_fields = fields
