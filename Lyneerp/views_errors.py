"""
Handlers d'erreur HTTP personnalisés.

Conçus pour être **robustes** : on ne doit JAMAIS lever une exception depuis
un handler d'erreur (sinon Django retombe sur un 500 minimal et boucle).
On utilise donc :

- un fallback HTML inline si le template ne se charge pas ;
- un try/except global ;
- aucun ``{% static %}`` ne devrait apparaître dans les templates ``errors/*``
  pour éviter qu'un manifest WhiteNoise cassé fasse boucler le rendu.
"""
from __future__ import annotations

import logging

from django.http import HttpResponse
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)


_FALLBACK_HTML = """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<title>{title}</title>
<style>
  body{{margin:0;font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
       background:#f9fafb;color:#111827;display:flex;align-items:center;
       justify-content:center;min-height:100vh}}
  .c{{max-width:420px;padding:3rem 2rem;text-align:center;background:#fff;
       border:1px solid #e5e7eb;border-radius:1rem}}
  .x{{font-size:4rem;font-weight:800;color:{color};margin:0}}
  a{{display:inline-block;margin-top:1.5rem;padding:.7rem 1.2rem;background:#4f46e5;
     color:#fff;text-decoration:none;border-radius:.6rem;font-weight:600}}
</style>
</head>
<body>
  <main class="c">
    <p class="x">{code}</p>
    <h1 style="font-size:1.3rem;margin:.5rem 0 0">{title}</h1>
    <p style="color:#6b7280">{message}</p>
    <a href="/">Retour à l'accueil</a>
  </main>
</body>
</html>"""


def _render(
    request,
    template_name: str,
    status: int,
    title: str,
    message: str = "",
    color: str = "#4f46e5",
) -> HttpResponse:
    """
    Rendu sûr : essaie le template, sinon renvoie un fallback HTML inline.
    """
    try:
        html = render_to_string(template_name, request=request)
    except Exception:  # noqa: BLE001
        # On NE veut PAS faire planter le handler d'erreur.
        logger.exception("Failed to render error template %s", template_name)
        html = _FALLBACK_HTML.format(
            code=status, title=title, message=message, color=color,
        )
    return HttpResponse(html, status=status, content_type="text/html; charset=utf-8")


def bad_request(request, exception=None):
    return _render(
        request, "errors/400.html", 400,
        title="Requête incorrecte",
        message="La requête envoyée au serveur n'a pas pu être interprétée.",
        color="#f97316",
    )


def permission_denied(request, exception=None):
    return _render(
        request, "errors/403.html", 403,
        title="Accès refusé",
        message="Vous n'avez pas les permissions nécessaires pour accéder à cette ressource.",
        color="#ef4444",
    )


def page_not_found(request, exception=None):
    return _render(
        request, "errors/404.html", 404,
        title="Page introuvable",
        message="La page que vous cherchez n'existe pas ou a été déplacée.",
        color="#4f46e5",
    )


def server_error(request):
    return _render(
        request, "errors/500.html", 500,
        title="Erreur serveur",
        message="Une erreur inattendue est survenue. Notre équipe a été notifiée.",
        color="#e11d48",
    )
