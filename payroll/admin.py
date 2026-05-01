from __future__ import annotations

from django.contrib import admin

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


@admin.register(PayrollItem)
class PayrollItemAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "tenant", "kind", "calculation", "rate", "fixed_amount", "is_active")
    list_filter = ("tenant", "kind", "calculation", "is_active")
    search_fields = ("code", "name")


class PayrollProfileItemInline(admin.TabularInline):
    model = PayrollProfileItem
    extra = 0
    fields = ("item", "sort_order", "rate_override", "amount_override", "is_optional")
    autocomplete_fields = ("item",)


@admin.register(PayrollProfile)
class PayrollProfileAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "tenant", "is_active")
    list_filter = ("tenant", "is_active")
    inlines = [PayrollProfileItemInline]


@admin.register(EmployeePayrollProfile)
class EmployeePayrollProfileAdmin(admin.ModelAdmin):
    list_display = ("employee", "tenant", "profile", "base_salary", "currency", "valid_from", "valid_to", "is_active")
    list_filter = ("tenant", "is_active", "profile")
    search_fields = ("employee__first_name", "employee__last_name", "employee__email")
    autocomplete_fields = ("employee",)


@admin.register(PayrollPeriod)
class PayrollPeriodAdmin(admin.ModelAdmin):
    list_display = ("label", "tenant", "year", "month", "date_start", "date_end", "status")
    list_filter = ("tenant", "status", "year")
    search_fields = ("label",)


class PayslipLineInline(admin.TabularInline):
    model = PayslipLine
    extra = 0
    can_delete = False
    readonly_fields = ("item", "label", "kind", "base_amount", "rate", "amount", "sort_order")


class PayrollAdjustmentInline(admin.TabularInline):
    model = PayrollAdjustment
    extra = 0
    fields = ("item", "label", "quantity", "unit_amount", "note")
    autocomplete_fields = ("item",)


@admin.register(Payslip)
class PayslipAdmin(admin.ModelAdmin):
    list_display = (
        "slip_number", "tenant", "employee", "period",
        "gross_amount", "employee_deductions", "net_amount", "status",
    )
    list_filter = ("tenant", "status", "period")
    search_fields = ("slip_number", "employee__last_name", "employee__email")
    inlines = [PayslipLineInline, PayrollAdjustmentInline]
    readonly_fields = (
        "slip_number", "gross_amount", "employee_deductions", "employer_charges",
        "taxable_base", "social_base", "income_tax", "net_amount", "computed_at",
        "approved_by", "approved_at",
    )


@admin.register(PayrollJournal)
class PayrollJournalAdmin(admin.ModelAdmin):
    list_display = (
        "period", "tenant",
        "total_gross", "total_employee_deductions",
        "total_employer_charges", "total_net", "is_posted",
    )
    list_filter = ("tenant", "is_posted")
