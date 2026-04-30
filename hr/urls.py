"""
URLs UI Web module RH (``/hr/...``).

Les noms d'URL gardent leur forme historique (``hr-dashboard``,
``employee_detail``, ``contract_detail``, etc.) pour ne pas casser les
templates existants. Pas de ``app_name`` : on utilise un espace de noms
global pour ces URLs RH.
"""
from __future__ import annotations

from django.urls import path

from hr.views import (
    AttendanceView,
    EmployeeDeleteView,
    EmployeeDetailView,
    EmployeeManagementView,
    EmployeeUpdateView,
    EmploymentContractDetailView,
    HRDashboardView,
    LeaveManagementView,
    RecruitmentView,
)

# Pas d'app_name : les templates utilisent des noms globaux (hr-dashboard, etc.)

urlpatterns = [
    # Dashboard / sections principales
    path("", HRDashboardView.as_view(), name="hr-dashboard"),
    path("employees/", EmployeeManagementView.as_view(), name="hr-employees"),
    path("recruitment/", RecruitmentView.as_view(), name="hr-recruitment"),
    path("leaves/", LeaveManagementView.as_view(), name="hr-leaves"),
    path("attendance/", AttendanceView.as_view(), name="hr-attendance"),

    # Détail / édition employé (noms historiques en snake_case)
    path("employees/<int:pk>/", EmployeeDetailView.as_view(), name="employee_detail"),
    path("employees/<int:pk>/edit/", EmployeeUpdateView.as_view(), name="employee_update"),
    path("employees/<int:pk>/delete/", EmployeeDeleteView.as_view(), name="employee_delete"),

    # Contrats : nom historique + alias
    path("contracts/<int:pk>/", EmploymentContractDetailView.as_view(), name="contract_detail"),
    # Alias vers la liste contrats : si vous n'avez pas de vue dédiée, on
    # redirige vers le dashboard pour ne pas casser ``{% url 'contracts_list' %}``.
    path("contracts/", HRDashboardView.as_view(), name="contracts_list"),
]
