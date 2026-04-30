"""
URLs API ``/api/auth/`` regroupant les endpoints d'authentification non-OIDC :

- ``whoami/``                 → infos utilisateur courant + tenant
- ``exchange/``               → créer une session locale à partir d'un Bearer
- ``keycloak/login/``         → login direct (Direct Access Grants) — réservé aux flows particuliers
"""
from __future__ import annotations

from django.urls import path

from hr.api.api_auth import WhoAmIView
from hr.views_auth import ExchangeTokenView
from tenants.auth_views import keycloak_direct_login

app_name = "auth"

urlpatterns = [
    path("whoami/", WhoAmIView.as_view(), name="whoami"),
    path("exchange/", ExchangeTokenView.as_view(), name="exchange"),
    path("keycloak/login/", keycloak_direct_login, name="keycloak-direct-login"),
]
