"""
URL configuration LYNEERP.

Hiérarchie :

- ``/admin/``       → Django admin
- ``/healthz``      → endpoint de healthcheck (pas d'auth, pas de DB)
- ``/api/schema/``  → schéma OpenAPI (drf-spectacular)
- ``/api/docs/``    → Swagger UI
- ``/api/rh/``      → API REST RH
- ``/api/finance/`` → API REST Finance
- ``/api/license/`` → API licences (multi-tenant)
- ``/api/auth/``    → API auth (whoami, exchange, etc.)
- ``/oidc/``        → URLs mozilla-django-oidc (Authorization Code Flow)
- ``/login/``       → Page de connexion (form + lien SSO Keycloak)
- ``/logout/``      → Déconnexion (purge session locale + Keycloak si applicable)
- ``/finance/``     → UI Finance (web)
- ``/hr/``          → UI RH (web) — préfixe explicite, plus de pollution racine
- ``/``             → redirige vers le dashboard adapté au rôle utilisateur
"""
from __future__ import annotations

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)


# --------------------------------------------------------------------------- #
# Endpoints utilitaires
# --------------------------------------------------------------------------- #
def healthz(_request):
    """
    Healthcheck léger, sans accès DB. Renvoie toujours 200.
    """
    return JsonResponse({"status": "ok", "service": "lyneerp"})


def root_dispatch(request):
    """
    Route ``/`` :
    - utilisateur authentifié → dashboard RH
    - sinon → page de connexion
    """
    if request.user.is_authenticated:
        return redirect("hr-dashboard")
    return redirect(settings.LOGIN_URL)


# --------------------------------------------------------------------------- #
# URL patterns
# --------------------------------------------------------------------------- #
urlpatterns = [
    # Admin & Health
    path("admin/", admin.site.urls),
    path("healthz", healthz, name="healthz"),
    # API documentation
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="api-docs",
    ),
    path(
        "api/redoc/",
        SpectacularRedocView.as_view(url_name="schema"),
        name="api-redoc",
    ),
    # API REST par module
    path("api/rh/", include(("hr.api.urls", "hr_api"), namespace="hr_api")),
    path(
        "api/finance/",
        include(("finance.api.urls", "finance_api"), namespace="finance_api"),
    ),
    path(
        "api/auth/",
        include(("Lyneerp.auth_urls", "auth"), namespace="auth"),
    ),
    path(
        "api/license/",
        include(("Lyneerp.license_urls", "license"), namespace="license"),
    ),
    # OIDC / Keycloak (Authorization Code Flow géré par mozilla-django-oidc)
    path("oidc/", include("mozilla_django_oidc.urls")),
    # Login / Logout (formulaire + redirections SSO)
    path(
        "login/",
        auth_views.LoginView.as_view(template_name="registration/login.html"),
        name="login",
    ),
    path(
        "logout/",
        auth_views.LogoutView.as_view(next_page="/login/"),
        name="logout",
    ),
    # UI Web par module
    path(
        "finance/",
        include(("finance.urls", "finance"), namespace="finance"),
    ),
    # Les URLs RH conservent les noms historiques (sans namespace) pour
    # rester compatibles avec les ~50 templates existants qui font
    # `{% url 'hr-dashboard' %}`, `{% url 'employee_detail' pk=... %}`, etc.
    path("hr/", include("hr.urls")),
    # Module IA — UI web et API
    path("ai/", include(("ai_assistant.urls", "ai"), namespace="ai")),
    path("api/ai/", include(("ai_assistant.api.urls", "ai_api"), namespace="ai_api")),

    # Module Paie
    path("payroll/", include(("payroll.urls", "payroll"), namespace="payroll")),
    path("api/payroll/", include(("payroll.api.urls", "payroll_api"), namespace="payroll_api")),

    # Module Stock / Logistique
    path("inventory/", include(("inventory.urls", "inventory"), namespace="inventory")),
    path("api/inventory/", include(("inventory.api.urls", "inventory_api"), namespace="inventory_api")),

    # Workflows / notifications / audit
    path("workflows/", include(("workflows.urls", "workflows"), namespace="workflows")),
    path("api/workflows/", include(("workflows.api.urls", "workflows_api"), namespace="workflows_api")),

    # CRM
    path("crm/", include(("crm.urls", "crm"), namespace="crm")),
    path("api/crm/", include(("crm.api.urls", "crm_api"), namespace="crm_api")),

    # Projets
    path("projects/", include(("projects.urls", "projects"), namespace="projects")),
    path("api/projects/", include(("projects.api.urls", "projects_api"), namespace="projects_api")),

    # Reporting / BI
    path("reporting/", include(("reporting.urls", "reporting"), namespace="reporting")),

    # OCR factures
    path("ocr/", include(("ocr.urls", "ocr"), namespace="ocr")),
    path("api/ocr/", include(("ocr.api.urls", "ocr_api"), namespace="ocr_api")),

    # Orphelins : pages référencées par la sidebar mais sans module dédié.
    # Chaque route renvoie une page Placeholder propre (titre + roadmap).
    path("", include(("Lyneerp.orphan_urls", "orphans"), namespace="orphans")),

    # Racine
    path("", root_dispatch, name="root"),
]

# --------------------------------------------------------------------------- #
# Médias statiques (uniquement en dev)
# --------------------------------------------------------------------------- #
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# --------------------------------------------------------------------------- #
# Handlers d'erreur personnalisés (templates 4xx/5xx fournis dans templates/)
# --------------------------------------------------------------------------- #
handler400 = "Lyneerp.views_errors.bad_request"
handler403 = "Lyneerp.views_errors.permission_denied"
handler404 = "Lyneerp.views_errors.page_not_found"
handler500 = "Lyneerp.views_errors.server_error"
