"""
Handler d'exception DRF unifié pour LYNEERP.

Avantages :
- format d'erreur stable (clé ``detail`` + ``code``)
- log des erreurs serveur
- pas de stack trace exposée en prod
"""
from __future__ import annotations

import logging
import uuid

from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.http import Http404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

logger = logging.getLogger(__name__)


def lyneerp_exception_handler(exc, context):
    response = drf_exception_handler(exc, context)
    request = context.get("request")
    user = getattr(request, "user", None)
    tenant = getattr(request, "tenant", None)

    # 1) Cas 404 / PermissionDenied non gérés par DRF
    if response is None:
        if isinstance(exc, Http404):
            return Response(
                {"detail": "Ressource introuvable.", "code": "not_found"},
                status=status.HTTP_404_NOT_FOUND,
            )
        if isinstance(exc, DjangoPermissionDenied):
            return Response(
                {"detail": str(exc) or "Accès refusé.", "code": "permission_denied"},
                status=status.HTTP_403_FORBIDDEN,
            )
        # Erreur serveur inattendue
        error_id = str(uuid.uuid4())
        logger.exception(
            "Unhandled exception (id=%s) user=%s tenant=%s",
            error_id,
            getattr(user, "id", None),
            getattr(tenant, "id", None),
        )
        return Response(
            {
                "detail": "Erreur serveur. Le support a été notifié.",
                "code": "server_error",
                "error_id": error_id,
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    # 2) Réponse DRF standard, on harmonise les clés.
    data = response.data
    if isinstance(data, dict) and "detail" in data:
        normalized = {
            "detail": str(data.get("detail")),
            "code": data.get("code") or _code_from_status(response.status_code),
        }
        # Conserver les éventuelles erreurs de champ
        for key, value in data.items():
            if key not in {"detail", "code"}:
                normalized.setdefault("errors", {})[key] = value
        response.data = normalized
    elif isinstance(data, dict):
        response.data = {
            "detail": "Validation échouée.",
            "code": "validation_error",
            "errors": data,
        }
    elif isinstance(data, list):
        response.data = {
            "detail": "Validation échouée.",
            "code": "validation_error",
            "errors": data,
        }

    return response


def _code_from_status(status_code: int) -> str:
    return {
        400: "bad_request",
        401: "not_authenticated",
        403: "permission_denied",
        404: "not_found",
        405: "method_not_allowed",
        409: "conflict",
        415: "unsupported_media_type",
        422: "unprocessable_entity",
        429: "throttled",
    }.get(status_code, "error")
