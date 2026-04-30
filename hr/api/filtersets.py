"""
FilterSets ``django-filter`` pour les viewsets RH.

À brancher sur les viewsets via ``filterset_class = ...`` (et déclarer
``DjangoFilterBackend`` dans ``DEFAULT_FILTER_BACKENDS`` — déjà fait dans
``Lyneerp/settings/base.py``).
"""
from __future__ import annotations

import django_filters

from hr.models import (
    Attendance,
    Employee,
    EmploymentContract,
    JobApplication,
    LeaveRequest,
    Recruitment,
)


class EmployeeFilterSet(django_filters.FilterSet):
    department = django_filters.NumberFilter(field_name="department_id")
    position = django_filters.NumberFilter(field_name="position_id")
    contract_type = django_filters.CharFilter(field_name="contract_type")
    is_active = django_filters.BooleanFilter(field_name="is_active")
    hire_date_from = django_filters.DateFilter(field_name="hire_date", lookup_expr="gte")
    hire_date_to = django_filters.DateFilter(field_name="hire_date", lookup_expr="lte")

    class Meta:
        model = Employee
        fields = [
            "department", "position", "contract_type",
            "is_active", "hire_date_from", "hire_date_to",
        ]


class LeaveRequestFilterSet(django_filters.FilterSet):
    status = django_filters.CharFilter(field_name="status")
    employee = django_filters.NumberFilter(field_name="employee_id")
    leave_type = django_filters.NumberFilter(field_name="leave_type_id")
    start_date_from = django_filters.DateFilter(field_name="start_date", lookup_expr="gte")
    start_date_to = django_filters.DateFilter(field_name="start_date", lookup_expr="lte")

    class Meta:
        model = LeaveRequest
        fields = [
            "status", "employee", "leave_type",
            "start_date_from", "start_date_to",
        ]


class AttendanceFilterSet(django_filters.FilterSet):
    employee = django_filters.NumberFilter(field_name="employee_id")
    status = django_filters.CharFilter(field_name="status")
    date_from = django_filters.DateFilter(field_name="date", lookup_expr="gte")
    date_to = django_filters.DateFilter(field_name="date", lookup_expr="lte")

    class Meta:
        model = Attendance
        fields = ["employee", "status", "date_from", "date_to"]


class RecruitmentFilterSet(django_filters.FilterSet):
    status = django_filters.CharFilter(field_name="status")
    department = django_filters.NumberFilter(field_name="department_id")
    position = django_filters.NumberFilter(field_name="position_id")
    publication_date_from = django_filters.DateFilter(
        field_name="publication_date", lookup_expr="gte"
    )
    publication_date_to = django_filters.DateFilter(
        field_name="publication_date", lookup_expr="lte"
    )

    class Meta:
        model = Recruitment
        fields = [
            "status", "department", "position",
            "publication_date_from", "publication_date_to",
        ]


class JobApplicationFilterSet(django_filters.FilterSet):
    status = django_filters.CharFilter(field_name="status")
    recruitment = django_filters.UUIDFilter(field_name="recruitment_id")
    ai_score_min = django_filters.NumberFilter(field_name="ai_score", lookup_expr="gte")
    ai_score_max = django_filters.NumberFilter(field_name="ai_score", lookup_expr="lte")
    applied_from = django_filters.DateTimeFilter(field_name="applied_at", lookup_expr="gte")
    applied_to = django_filters.DateTimeFilter(field_name="applied_at", lookup_expr="lte")

    class Meta:
        model = JobApplication
        fields = [
            "status", "recruitment",
            "ai_score_min", "ai_score_max",
            "applied_from", "applied_to",
        ]


class EmploymentContractFilterSet(django_filters.FilterSet):
    employee = django_filters.NumberFilter(field_name="employee_id")
    contract_type = django_filters.NumberFilter(field_name="contract_type_id")
    status = django_filters.CharFilter(field_name="status")
    start_date_from = django_filters.DateFilter(field_name="start_date", lookup_expr="gte")
    start_date_to = django_filters.DateFilter(field_name="start_date", lookup_expr="lte")
    end_date_from = django_filters.DateFilter(field_name="end_date", lookup_expr="gte")
    end_date_to = django_filters.DateFilter(field_name="end_date", lookup_expr="lte")

    class Meta:
        model = EmploymentContract
        fields = [
            "employee", "contract_type", "status",
            "start_date_from", "start_date_to",
            "end_date_from", "end_date_to",
        ]
