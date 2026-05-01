"""
Tests du moteur de paie : déterministe, idempotent, équilibre brut/net.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from payroll.models import (
    EmployeePayrollProfile,
    PayrollPeriod,
    PayrollProfile,
    PayrollProfileItem,
    Payslip,
    PayslipStatus,
)
from payroll.services.engine import PayrollEngine
from payroll.services.seed import seed_ohada_payroll

pytestmark = pytest.mark.django_db


@pytest.fixture
def payroll_setup(tenant_a, user_a):
    """Crée un référentiel paie OHADA + un employé + une période."""
    from hr.models import Employee

    seed_ohada_payroll(tenant_a)
    profile = PayrollProfile.objects.get(tenant=tenant_a, code="OHADA_EMPLOYE")

    emp = Employee.objects.create(
        tenant=tenant_a,
        matricule="E0001",
        first_name="Alice",
        last_name="Tester",
        email="alice@example.com",
        hire_date=date(2024, 1, 1),
    )
    emp_profile = EmployeePayrollProfile.objects.create(
        tenant=tenant_a, employee=emp, profile=profile,
        base_salary=Decimal("500000"),
        currency="XOF",
        valid_from=date(2024, 1, 1),
    )
    period = PayrollPeriod.objects.create(
        tenant=tenant_a, label="2026-04",
        year=2026, month=4,
        date_start=date(2026, 4, 1),
        date_end=date(2026, 4, 30),
    )
    return {"emp": emp, "emp_profile": emp_profile, "period": period}


def test_compute_payslip_balances(payroll_setup, tenant_a):
    slip = Payslip.objects.create(
        tenant=tenant_a,
        period=payroll_setup["period"],
        employee=payroll_setup["emp"],
        employee_profile=payroll_setup["emp_profile"],
    )

    engine = PayrollEngine(period=payroll_setup["period"])
    engine.compute_payslip(slip)
    slip.refresh_from_db()

    # Cohérence : net = brut - retenues
    assert slip.net_amount == (slip.gross_amount - slip.employee_deductions)
    assert slip.gross_amount > 0
    assert slip.status == PayslipStatus.COMPUTED
    assert slip.slip_number.startswith("PAY-2026-04-")


def test_recompute_is_idempotent(payroll_setup, tenant_a):
    slip = Payslip.objects.create(
        tenant=tenant_a,
        period=payroll_setup["period"],
        employee=payroll_setup["emp"],
        employee_profile=payroll_setup["emp_profile"],
    )
    engine = PayrollEngine(period=payroll_setup["period"])
    engine.compute_payslip(slip)
    first_net = slip.net_amount
    first_lines = slip.lines.count()
    # Recalcul → mêmes montants, mêmes nombres de lignes.
    engine.compute_payslip(slip)
    slip.refresh_from_db()
    assert slip.net_amount == first_net
    assert slip.lines.count() == first_lines
