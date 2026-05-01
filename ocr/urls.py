"""URLs ``/ocr/...``."""
from __future__ import annotations

from django.urls import path

from ocr.views import DocumentDetailView, DocumentListView

app_name = "ocr"

urlpatterns = [
    path("", DocumentListView.as_view(), name="list"),
    path("<uuid:pk>/", DocumentDetailView.as_view(), name="detail"),
]
