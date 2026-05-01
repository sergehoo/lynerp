"""URLs web ``/projects/...``."""
from __future__ import annotations

from django.urls import path

from projects.views import (
    ProjectDetailView,
    ProjectListView,
    ProjectsDashboardView,
)

app_name = "projects"

urlpatterns = [
    path("", ProjectsDashboardView.as_view(), name="dashboard"),
    path("list/", ProjectListView.as_view(), name="list"),
    path("<uuid:pk>/", ProjectDetailView.as_view(), name="detail"),
]
