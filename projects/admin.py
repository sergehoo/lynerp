from __future__ import annotations

from django.contrib import admin

from projects.models import (
    Milestone,
    Phase,
    Project,
    ProjectMember,
    Task,
    TimeEntry,
)


class PhaseInline(admin.TabularInline):
    model = Phase
    extra = 0


class MilestoneInline(admin.TabularInline):
    model = Milestone
    extra = 0


class ProjectMemberInline(admin.TabularInline):
    model = ProjectMember
    extra = 0


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "tenant", "status", "project_manager", "start_date", "end_date", "progress_percent")
    list_filter = ("tenant", "status")
    search_fields = ("code", "name", "description")
    inlines = [PhaseInline, MilestoneInline, ProjectMemberInline]


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ("title", "tenant", "project", "phase", "status", "priority", "due_date")
    list_filter = ("tenant", "status", "priority", "project")
    search_fields = ("title", "description")


@admin.register(Milestone)
class MilestoneAdmin(admin.ModelAdmin):
    list_display = ("name", "tenant", "project", "target_date", "achieved_at")
    list_filter = ("tenant", "project")


@admin.register(TimeEntry)
class TimeEntryAdmin(admin.ModelAdmin):
    list_display = ("user", "tenant", "project", "task", "work_date", "hours", "is_billable")
    list_filter = ("tenant", "is_billable", "project")
    date_hierarchy = "work_date"
