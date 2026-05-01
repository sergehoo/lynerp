from __future__ import annotations

from django.contrib import admin

from ocr.models import DocumentUpload, ExtractedField


@admin.register(DocumentUpload)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ("id", "tenant", "kind", "status", "uploaded_by", "created_at")
    list_filter = ("tenant", "kind", "status")


@admin.register(ExtractedField)
class FieldAdmin(admin.ModelAdmin):
    list_display = ("key", "tenant", "document", "value", "confidence", "is_validated")
    list_filter = ("tenant", "key", "is_validated")
