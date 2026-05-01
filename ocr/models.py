"""
Modèles OCR : DocumentUpload + ExtractedField.

Le pipeline d'extraction est volontairement simple ici : un service
extrait le texte (PDF / image / docx) puis l'IA structure les champs.
On stocke les résultats dans ``ExtractedField`` (clé/valeur) pour permettre
à l'humain de corriger avant import comptable.
"""
from __future__ import annotations

from django.conf import settings
from django.db import models

from Lyneerp.core.models import TenantOwnedModel, UUIDPkModel
from hr.storage import TenantPath


class DocumentKind(models.TextChoices):
    INVOICE = "INVOICE", "Facture fournisseur"
    RECEIPT = "RECEIPT", "Reçu / ticket"
    CONTRACT = "CONTRACT", "Contrat"
    OTHER = "OTHER", "Autre"


class DocumentStatus(models.TextChoices):
    UPLOADED = "UPLOADED", "Importé"
    PROCESSING = "PROCESSING", "Analyse en cours"
    EXTRACTED = "EXTRACTED", "Champs extraits"
    VALIDATED = "VALIDATED", "Validé"
    POSTED = "POSTED", "Comptabilisé"
    FAILED = "FAILED", "Échec"


class DocumentUpload(UUIDPkModel, TenantOwnedModel):
    file = models.FileField(upload_to=TenantPath("ocr/uploads"))
    kind = models.CharField(
        max_length=12, choices=DocumentKind.choices,
        default=DocumentKind.INVOICE,
    )
    status = models.CharField(
        max_length=12, choices=DocumentStatus.choices,
        default=DocumentStatus.UPLOADED, db_index=True,
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="ocr_uploads",
    )
    raw_text = models.TextField(blank=True)
    note = models.TextField(blank=True)
    error_message = models.TextField(blank=True)

    class Meta:
        db_table = "ocr_document"
        verbose_name = "Document OCR"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "status", "-created_at"]),
        ]


class ExtractedField(UUIDPkModel, TenantOwnedModel):
    """Champ structuré extrait d'un document OCR (clé / valeur / confiance)."""

    document = models.ForeignKey(
        DocumentUpload, on_delete=models.CASCADE, related_name="fields",
    )
    key = models.CharField(max_length=80, db_index=True)
    value = models.TextField()
    confidence = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    is_validated = models.BooleanField(default=False)

    class Meta:
        db_table = "ocr_field"
        constraints = [
            models.UniqueConstraint(
                fields=["document", "key"], name="uniq_ocr_field_per_doc",
            ),
        ]
        ordering = ["key"]
