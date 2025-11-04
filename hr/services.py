# hr/services.py
from __future__ import annotations
import io
from typing import Any, Dict, List, Iterable
import pandas as pd
from django.utils import timezone

from .models import Employee

class EmployeeExportService:
    """
    Exporte les employés d’un tenant au format CSV ou XLSX.
    - fields: liste des champs à inclure (ex: ["matricule","first_name","last_name","email","hire_date","contract_type"])
    - filters: dict de filtres Django (ex: {"is_active": True, "department__name": "RH"})
    """
    DEFAULT_FIELDS = [
        "matricule", "first_name", "last_name", "email",
        "hire_date", "contract_type", "is_active",
    ]

    def export_employees(
        self,
        tenant_id: str,
        export_format: str,
        fields: List[str] | None = None,
        filters: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        fields = fields or self.DEFAULT_FIELDS
        filters = filters or {}

        qs = Employee.objects.filter(tenant_id=tenant_id)
        if filters:
            qs = qs.filter(**filters)

        # Sélectionne uniquement les champs demandés (si existants)
        # On mappe proprement pour éviter les attributs FK non gérés
        rows: List[Dict[str, Any]] = []
        for e in qs.select_related("department", "position").iterator():
            row = {}
            for f in fields:
                row[f] = self._resolve_field(e, f)
            rows.append(row)

        df = pd.DataFrame(rows, columns=fields)

        now = timezone.now().strftime("%Y%m%d_%H%M%S")
        if export_format.lower() == "xlsx":
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
                df.to_excel(writer, index=False, sheet_name="employees")
            content = output.getvalue()
            filename = f"employees_{tenant_id}_{now}.xlsx"
            content_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        else:
            # CSV par défaut
            content = df.to_csv(index=False).encode("utf-8")
            filename = f"employees_{tenant_id}_{now}.csv"
            content_type = "text/csv; charset=utf-8"

        return {
            "success": True,
            "content": content,
            "filename": filename,
            "content_type": content_type,
        }

    # -------- internals

    def _resolve_field(self, e: Employee, field: str):
        """
        Résout un champ simple ou quelques alias utiles.
        Ajoute ici d’autres mappings si besoin.
        """
        # alias fréquents
        if field == "department":
            return getattr(getattr(e, "department", None), "name", None)
        if field == "position":
            return getattr(getattr(e, "position", None), "title", None)
        if field == "full_name":
            return f"{e.first_name} {e.last_name}".strip()

        # champs directs
        if hasattr(e, field):
            val = getattr(e, field)
            # Conversion basique de dates pour CSV
            if hasattr(val, "isoformat"):
                return val.isoformat()
            return val

        # fallback : None si champ inconnu
        return None