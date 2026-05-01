from __future__ import annotations

from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.generic import CreateView, DetailView, ListView

from ocr.models import DocumentUpload


class DocumentListView(LoginRequiredMixin, ListView):
    template_name = "ocr/list.html"
    context_object_name = "documents"
    paginate_by = 25

    def get_queryset(self):
        tenant = getattr(self.request, "tenant", None)
        if tenant is None:
            return DocumentUpload.objects.none()
        return DocumentUpload.objects.filter(tenant=tenant).order_by("-created_at")


class DocumentDetailView(LoginRequiredMixin, DetailView):
    template_name = "ocr/detail.html"
    context_object_name = "document"

    def get_queryset(self):
        tenant = getattr(self.request, "tenant", None)
        if tenant is None:
            return DocumentUpload.objects.none()
        return DocumentUpload.objects.filter(tenant=tenant).prefetch_related("fields")

    def get_object(self, queryset=None):
        return get_object_or_404(self.get_queryset(), pk=self.kwargs["pk"])
