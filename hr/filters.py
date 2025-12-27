# hr/filters.py
import django_filters
from hr.models import EmploymentContract


class EmploymentContractFilter(django_filters.FilterSet):
    employee = django_filters.NumberFilter(field_name="employee_id")
    contract_type = django_filters.NumberFilter(field_name="contract_type_id")
    status = django_filters.CharFilter(field_name="status")

    # tes champs UI
    start_date__gte = django_filters.DateFilter(field_name="start_date", lookup_expr="gte")
    start_date__lte = django_filters.DateFilter(field_name="start_date", lookup_expr="lte")

    class Meta:
        model = EmploymentContract
        fields = ["employee", "contract_type", "status", "start_date__gte", "start_date__lte"]
