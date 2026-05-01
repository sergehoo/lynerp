from __future__ import annotations

from django.contrib import admin

from crm.models import (
    Account,
    Activity,
    Contact,
    Lead,
    Opportunity,
    Pipeline,
    Stage,
)


class ContactInline(admin.TabularInline):
    model = Contact
    extra = 0


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ("name", "tenant", "type", "industry", "owner", "is_active", "created_at")
    list_filter = ("tenant", "type", "industry", "is_active")
    search_fields = ("name", "legal_name", "email", "phone")
    inlines = [ContactInline]


@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ("first_name", "last_name", "tenant", "account", "email", "is_primary")
    list_filter = ("tenant", "is_primary", "do_not_contact")
    search_fields = ("first_name", "last_name", "email")


class StageInline(admin.TabularInline):
    model = Stage
    extra = 0


@admin.register(Pipeline)
class PipelineAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "tenant", "is_default", "is_active")
    list_filter = ("tenant", "is_default", "is_active")
    inlines = [StageInline]


@admin.register(Opportunity)
class OpportunityAdmin(admin.ModelAdmin):
    list_display = ("name", "tenant", "account", "stage", "status", "amount", "win_probability", "expected_close_date", "owner")
    list_filter = ("tenant", "status", "stage", "pipeline")
    search_fields = ("name", "account__name")


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = ("first_name", "last_name", "company", "tenant", "status", "ai_score", "owner", "created_at")
    list_filter = ("tenant", "status", "industry")
    search_fields = ("first_name", "last_name", "company", "email")


@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
    list_display = ("subject", "tenant", "type", "status", "scheduled_at", "assigned_to")
    list_filter = ("tenant", "type", "status")
    search_fields = ("subject", "description")
