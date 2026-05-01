"""Vues web Projets."""
from __future__ import annotations

from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404
from django.views.generic import DetailView, ListView, TemplateView

from projects.models import Project, ProjectStatus, Task, TaskStatus


class ProjectsDashboardView(LoginRequiredMixin, TemplateView):
    template_name = "projects/dashboard.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        tenant = getattr(self.request, "tenant", None)
        if tenant is None:
            return ctx
        ctx["active_projects"] = (
            Project.objects.filter(tenant=tenant, status=ProjectStatus.ACTIVE)
            .order_by("-updated_at")[:20]
        )
        ctx["my_tasks"] = (
            Task.objects.filter(
                tenant=tenant,
                assignees=self.request.user,
            ).exclude(status__in=[TaskStatus.DONE, TaskStatus.CANCELLED])
            .order_by("due_date")[:20]
        )
        return ctx


class ProjectListView(LoginRequiredMixin, ListView):
    template_name = "projects/list.html"
    context_object_name = "projects"
    paginate_by = 20

    def get_queryset(self):
        tenant = getattr(self.request, "tenant", None)
        if tenant is None:
            return Project.objects.none()
        qs = Project.objects.filter(tenant=tenant)
        s = self.request.GET.get("status")
        if s:
            qs = qs.filter(status=s)
        return qs.order_by("-updated_at")


class ProjectDetailView(LoginRequiredMixin, DetailView):
    template_name = "projects/detail.html"
    context_object_name = "project"

    def get_queryset(self):
        tenant = getattr(self.request, "tenant", None)
        if tenant is None:
            return Project.objects.none()
        return (
            Project.objects.filter(tenant=tenant)
            .prefetch_related("phases", "tasks", "milestones", "members__user")
        )

    def get_object(self, queryset=None):
        return get_object_or_404(self.get_queryset(), pk=self.kwargs["pk"])
