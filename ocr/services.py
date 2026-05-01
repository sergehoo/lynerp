"""
Service d'extraction OCR.

Pipeline :
1. Lire le fichier (PDF/image/docx) → extraire le texte brut.
2. Demander au LLM Ollama de structurer en JSON les champs invoice
   (numéro, date, fournisseur, total HT/TTC, lignes…).
3. Stocker les ExtractedField + raw_text.
4. Marquer le document EXTRACTED.

Pour les images, le pipeline simple lit uniquement les PDF/text en MVP.
Une intégration Tesseract (pytesseract) ou un service externe peut être
ajoutée pour les images / scans.
"""
from __future__ import annotations

import io
import logging
from decimal import Decimal
from typing import Any, Dict

from ai_assistant.services.ollama import get_ollama
from ocr.models import DocumentStatus, DocumentUpload, ExtractedField

logger = logging.getLogger(__name__)


INVOICE_EXTRACTION_PROMPT = """Tu es un comptable expert. Tu reçois le texte brut d'une facture fournisseur.
Extrait les informations en JSON strict, structure :

{
  "supplier_name": "...",
  "supplier_tax_id": "...",
  "invoice_number": "...",
  "invoice_date": "YYYY-MM-DD",
  "due_date": "YYYY-MM-DD",
  "currency": "XOF",
  "lines": [
    {"description": "...", "quantity": 1, "unit_price": 0, "tax_rate": 0, "total": 0}
  ],
  "subtotal": 0,
  "tax_total": 0,
  "total": 0,
  "payment_terms": "..."
}

Ne renvoie QUE le JSON, sans préambule ni backticks. Si une donnée est
absente, mets "" ou 0. Devises possibles : XOF, XAF, EUR, USD.

Texte brut :
---
{text}
---
"""


def extract_text(document: DocumentUpload) -> str:
    """Lit le contenu brut du fichier (PDF/docx/txt)."""
    name = (document.file.name or "").lower()
    document.file.open("rb")
    try:
        data = document.file.read()
    finally:
        try:
            document.file.close()
        except Exception:  # noqa: BLE001
            pass

    if name.endswith(".pdf"):
        try:
            import pdfplumber

            with pdfplumber.open(io.BytesIO(data)) as pdf:
                return "\n".join((p.extract_text() or "") for p in pdf.pages)
        except Exception:  # noqa: BLE001
            logger.exception("PDF extraction failed")
            return ""
    if name.endswith(".docx"):
        try:
            from docx import Document

            doc = Document(io.BytesIO(data))
            return "\n".join(p.text for p in doc.paragraphs)
        except Exception:  # noqa: BLE001
            logger.exception("DOCX extraction failed")
            return ""
    if name.endswith(".txt"):
        try:
            return data.decode("utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            return ""
    # Image / autre : intégration Tesseract à brancher ici.
    return ""


def process_document(document: DocumentUpload) -> Dict[str, Any]:
    """Pipeline complet : extraction texte → LLM → fields."""
    document.status = DocumentStatus.PROCESSING
    document.save(update_fields=["status", "updated_at"])

    raw = extract_text(document)
    if not raw:
        document.status = DocumentStatus.FAILED
        document.error_message = "Texte non extractible (PDF scanné ?)."
        document.save(update_fields=["status", "error_message", "updated_at"])
        return {"error": "no_text"}

    document.raw_text = raw[:50000]

    prompt = INVOICE_EXTRACTION_PROMPT.replace("{text}", raw[:8000])
    result = get_ollama().chat_json([
        {"role": "system", "content": "Tu es un comptable méticuleux."},
        {"role": "user", "content": prompt},
    ])
    data = result.get("data") or {}

    if not isinstance(data, dict) or data.get("_parse_error"):
        document.status = DocumentStatus.FAILED
        document.error_message = "Extraction IA non valide."
        document.save(update_fields=["status", "error_message", "raw_text", "updated_at"])
        return {"error": "extraction_failed"}

    # Persiste les champs.
    ExtractedField.objects.filter(document=document).delete()
    flat = _flatten(data)
    for key, value in flat.items():
        ExtractedField.objects.create(
            tenant=document.tenant,
            document=document,
            key=key,
            value=str(value)[:5000],
            confidence=Decimal("0.85"),  # estimation forfaitaire
        )

    document.status = DocumentStatus.EXTRACTED
    document.save(update_fields=["status", "raw_text", "updated_at"])
    return {"data": data, "fields_count": len(flat)}


def _flatten(data: Dict[str, Any], prefix: str = "") -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for k, v in data.items():
        key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            out.update(_flatten(v, prefix=key))
        elif isinstance(v, list):
            out[key] = str(v)[:5000]
        else:
            out[key] = v
    return out
