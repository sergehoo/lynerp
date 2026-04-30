"""
Handlers d'erreur HTTP personnalisés (templates statiques sous ``templates/errors/``).

En cas d'absence du template (déploiement minimal), on retombe sur une réponse
HTML très simple — toujours sans stack trace.
"""
from __future__ import annotations

from django.http import HttpResponse
from django.template import TemplateDoesNotExist
from django.template.loader import render_to_string


def _render(request, template_name: str, status: int, default_text: str) -> HttpResponse:
    try:
        html = render_to_string(template_name, request=request)
    except TemplateDoesNotExist:
        html = (
            "<!doctype html><html lang='fr'><head><meta charset='utf-8'>"
            f"<title>{default_text}</title></head>"
            f"<body style='font-family:system-ui;padding:3rem;text-align:center;'>"
            f"<h1>{default_text}</h1>"
            "<p><a href='/'>Retour à l'accueil</a></p></body></html>"
        )
    return HttpResponse(html, status=status, content_type="text/html; charset=utf-8")


def bad_request(request, exception=None):
    return _render(request, "errors/400.html", 400, "Requête incorrecte (400)")


def permission_denied(request, exception=None):
    return _render(request, "errors/403.html", 403, "Accès refusé (403)")


def page_not_found(request, exception=None):
    return _render(request, "errors/404.html", 404, "Page introuvable (404)")


def server_error(request):
    return _render(request, "errors/500.html", 500, "Erreur serveur (500)")
