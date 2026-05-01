from __future__ import annotations

from django.apps import AppConfig


class OCRConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "ocr"
    verbose_name = "OCR Documents"
