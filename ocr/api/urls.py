"""URLs API OCR."""
from __future__ import annotations

from django.urls import include, path
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.routers import DefaultRouter

from hr.api.views import BaseTenantViewSet
from ocr.models import DocumentUpload, ExtractedField
from ocr.services import process_document

app_name = "ocr_api"


class FieldSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExtractedField
        fields = "__all__"
        read_only_fields = ["id", "tenant", "created_at", "updated_at"]


class DocumentSerializer(serializers.ModelSerializer):
    fields = FieldSerializer(many=True, read_only=True)

    class Meta:
        model = DocumentUpload
        fields = "__all__"
        read_only_fields = [
            "id", "tenant", "uploaded_by", "raw_text", "status",
            "error_message", "fields", "created_at", "updated_at",
        ]


class DocumentViewSet(BaseTenantViewSet):
    queryset = DocumentUpload.objects.all().prefetch_related("fields")
    serializer_class = DocumentSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(uploaded_by=self.request.user)

    @action(detail=True, methods=["post"], url_path="process")
    def process(self, request, pk=None):
        doc = self.get_object()
        result = process_document(doc)
        return Response({"document": DocumentSerializer(doc).data, "result": result})


router = DefaultRouter(trailing_slash=True)
router.register(r"documents", DocumentViewSet, basename="ocr-documents")

urlpatterns = [path("", include(router.urls))]
