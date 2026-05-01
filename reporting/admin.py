from __future__ import annotations

from django.contrib import admin

from reporting.models import Dashboard, KPISnapshot, Widget


@admin.register(Dashboard)
class DashboardAdmin(admin.ModelAdmin):
    list_display = ("name", "tenant", "is_default", "is_public", "owner")


@admin.register(Widget)
class WidgetAdmin(admin.ModelAdmin):
    list_display = ("title", "tenant", "dashboard", "type", "kpi_code")


@admin.register(KPISnapshot)
class KPISnapshotAdmin(admin.ModelAdmin):
    list_display = ("kpi_code", "tenant", "value", "captured_at")
    list_filter = ("tenant", "kpi_code")
    date_hierarchy = "captured_at"
