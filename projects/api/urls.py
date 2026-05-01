"""URLs API ``/api/projects/...``."""
from __future__ import annotations

from django.urls import include, path
from rest_framework import serializers, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.routers import DefaultRouter

from hr.api.views import BaseTenantViewSet
from projects.models import (
    Milestone,
    Phase,
    Project,
    ProjectMember,
    Task,
    TimeEntry,
)

app_name = "projects_api"


class ProjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = "__all__"
        read_only_fields = ["id", "tenant", "created_at", "updated_at"]


class PhaseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Phase
        fields = "__all__"
        read_only_fields = ["id", "tenant", "created_at", "updated_at"]


class TaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = Task
        fields = "__all__"
        read_only_fields = ["id", "tenant", "completed_at", "created_at", "updated_at"]


class MilestoneSerializer(serializers.ModelSerializer):
    class Meta:
        model = Milestone
        fields = "__all__"
        read_only_fields = ["id", "tenant", "achieved_at", "created_at", "updated_at"]


class ProjectMemberSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectMember
        fields = "__all__"
        read_only_fields = ["id", "tenant", "created_at", "updated_at"]


class TimeEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = TimeEntry
        fields = "__all__"
        read_only_fields = ["id", "tenant", "created_at", "updated_at"]


class ProjectViewSet(BaseTenantViewSet):
    queryset = Project.objects.all().select_related("project_manager", "customer_account")
    serializer_class = ProjectSerializer
    permission_classes = [IsAuthenticated]
    search_fields = ["code", "name"]


class PhaseViewSet(BaseTenantViewSet):
    queryset = Phase.objects.all()
    serializer_class = PhaseSerializer
    permission_classes = [IsAuthenticated]


class TaskViewSet(BaseTenantViewSet):
    queryset = Task.objects.all().select_related("project", "phase", "parent", "reporter").prefetch_related("assignees")
    serializer_class = TaskSerializer
    permission_classes = [IsAuthenticated]
    search_fields = ["title", "description"]


class MilestoneViewSet(BaseTenantViewSet):
    queryset = Milestone.objects.all()
    serializer_class = MilestoneSerializer
    permission_classes = [IsAuthenticated]


class ProjectMemberViewSet(BaseTenantViewSet):
    queryset = ProjectMember.objects.all().select_related("project", "user")
    serializer_class = ProjectMemberSerializer
    permission_classes = [IsAuthenticated]


class TimeEntryViewSet(BaseTenantViewSet):
    queryset = TimeEntry.objects.all().select_related("user", "project", "task")
    serializer_class = TimeEntrySerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


router = DefaultRouter(trailing_slash=True)
router.register(r"projects", ProjectViewSet, basename="proj-projects")
router.register(r"phases", PhaseViewSet, basename="proj-phases")
router.register(r"tasks", TaskViewSet, basename="proj-tasks")
router.register(r"milestones", MilestoneViewSet, basename="proj-milestones")
router.register(r"members", ProjectMemberViewSet, basename="proj-members")
router.register(r"time-entries", TimeEntryViewSet, basename="proj-time-entries")

urlpatterns = [path("", include(router.urls))]
