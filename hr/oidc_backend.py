"""
Backend OIDC custom pour Keycloak — LYNEERP.

Au-delà du mapping basique d'attributs (email, nom, prénom), ce backend
**provisionne le rattachement tenant** dès la première connexion :

1. Lit le claim ``settings.KEYCLOAK_TENANT_CLAIM`` (défaut : ``"tenant"``)
   du token Keycloak. Ce claim doit contenir le **slug** du tenant
   (par convention configurée côté Keycloak via un mapper "User attribute").
2. Si le tenant existe → crée/active la membership ``TenantUser``.
3. Si le tenant n'existe pas et que ``settings.KEYCLOAK_AUTO_CREATE_TENANT``
   est True → crée le tenant à la volée (utile en dev). Sinon, log et
   laisse le user sans tenant (il verra la page « no tenant »).
4. Mappe les rôles Keycloak (claim ``realm_access.roles``) vers le rôle
   ``TenantUser.role`` (OWNER/ADMIN/MANAGER/MEMBER/VIEWER) selon
   ``settings.KEYCLOAK_ROLE_MAPPING``.

Toutes les valeurs sont prudentes : si un claim manque, on ne plante pas.
On loggue un warning et on continue pour ne pas bloquer le SSO.
"""
from __future__ import annotations

import logging
from typing import Iterable, Optional

from django.conf import settings
from django.utils.text import slugify
from mozilla_django_oidc.auth import OIDCAuthenticationBackend

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Réglages par défaut (peuvent être surchargés dans settings)
# --------------------------------------------------------------------------- #
DEFAULT_TENANT_CLAIM = "tenant"
DEFAULT_AUTO_CREATE_TENANT = False
DEFAULT_ROLE_MAPPING = {
    # Keycloak realm role → TenantUser.role
    "lyneerp-owner": "OWNER",
    "lyneerp-admin": "ADMIN",
    "lyneerp-manager": "MANAGER",
    "lyneerp-member": "MEMBER",
    "lyneerp-viewer": "VIEWER",
}


def _setting(name, default):
    return getattr(settings, name, default)


def _extract_tenant_slug(claims: dict) -> Optional[str]:
    """
    Cherche le slug du tenant dans plusieurs emplacements possibles
    pour s'adapter à différentes configurations Keycloak :

      - claim direct ``settings.KEYCLOAK_TENANT_CLAIM`` (default ``tenant``)
      - claim ``tenant_slug`` ou ``tenant_id``
      - sous-élément ``organization`` / ``org_slug`` (mapper d'attribut)
    """
    claim_name = _setting("KEYCLOAK_TENANT_CLAIM", DEFAULT_TENANT_CLAIM)
    candidates = [
        claims.get(claim_name),
        claims.get("tenant"),
        claims.get("tenant_slug"),
        claims.get("tenant_id"),
        claims.get("organization"),
        claims.get("org_slug"),
    ]
    for value in candidates:
        if value:
            slug = str(value).strip().lower()
            return slugify(slug) or None
    return None


def _extract_realm_roles(claims: dict) -> Iterable[str]:
    """
    Extrait la liste des rôles Keycloak depuis plusieurs claims possibles :

      - ``realm_access.roles`` (rôles realm)
      - ``resource_access.<client>.roles`` (rôles client)
      - ``roles`` à plat (mapper custom)
    """
    out = set()

    realm = claims.get("realm_access") or {}
    for r in realm.get("roles") or []:
        out.add(str(r).strip().lower())

    res = claims.get("resource_access") or {}
    if isinstance(res, dict):
        for _client, payload in res.items():
            for r in (payload or {}).get("roles") or []:
                out.add(str(r).strip().lower())

    flat = claims.get("roles")
    if isinstance(flat, list):
        for r in flat:
            out.add(str(r).strip().lower())

    return out


def _resolve_role(claims: dict) -> str:
    """
    Renvoie le rôle TenantUser à appliquer au user. Par défaut MEMBER.
    Si le user est superuser Django, on donne OWNER (utile en dev).
    """
    mapping = _setting("KEYCLOAK_ROLE_MAPPING", DEFAULT_ROLE_MAPPING)
    roles = _extract_realm_roles(claims)
    # On prend le rôle le plus permissif présent.
    priority = ["OWNER", "ADMIN", "MANAGER", "MEMBER", "VIEWER"]
    found = []
    for role in roles:
        target = mapping.get(role)
        if target:
            found.append(target)
    for tier in priority:
        if tier in found:
            return tier
    return "MEMBER"


# --------------------------------------------------------------------------- #
# Backend
# --------------------------------------------------------------------------- #
class KeycloakOIDCBackend(OIDCAuthenticationBackend):
    """Backend OIDC custom pour Keycloak : pas d'appel /userinfo + tenant auto."""

    # ---- Claims → utilisateur Django ---- #
    def get_userinfo(self, access_token, id_token, payload):
        # Ne plus appeler /userinfo : on se base sur l'ID Token.
        return payload

    def get_username(self, claims):
        return (
            claims.get("preferred_username")
            or claims.get("email")
            or claims.get("sub")
        )

    def create_user(self, claims):
        user = super().create_user(claims)
        user.email = claims.get("email", "") or user.email
        user.first_name = claims.get("given_name", "")
        user.last_name = claims.get("family_name", "")
        user.save()
        self._provision_tenant_membership(user, claims)
        return user

    def update_user(self, user, claims):
        user.email = claims.get("email", "") or user.email
        user.first_name = claims.get("given_name", "")
        user.last_name = claims.get("family_name", "")
        user.save()
        self._provision_tenant_membership(user, claims)
        return user

    # ---- Provisioning tenant ---- #
    def _provision_tenant_membership(self, user, claims: dict) -> None:
        """
        Idempotent : crée le tenant si autorisé, puis crée/active la
        membership TenantUser. N'écrase pas un rôle déjà élevé (pour
        éviter qu'un changement Keycloak rétrograde un OWNER en MEMBER).
        """
        slug = _extract_tenant_slug(claims)
        if not slug:
            logger.info(
                "OIDC: no tenant claim for user=%s — laissé sans tenant.",
                user.email or user.username,
            )
            return

        # Import tardif pour éviter le cycle d'import au démarrage Django.
        from tenants.models import Tenant, TenantUser
        from tenants.services.licensing import grant_license

        tenant = Tenant.objects.filter(slug=slug).first()
        if tenant is None:
            if not _setting("KEYCLOAK_AUTO_CREATE_TENANT", DEFAULT_AUTO_CREATE_TENANT):
                logger.warning(
                    "OIDC: tenant slug='%s' inconnu et auto-création désactivée. "
                    "User=%s.", slug, user.email or user.username,
                )
                return
            tenant = Tenant.objects.create(
                slug=slug,
                name=claims.get("organization_name") or slug.title(),
                contact_email=user.email or "",
                is_active=True,
            )
            # En auto-création (dev), on octroie une licence ALL/ENTERPRISE.
            try:
                grant_license(
                    tenant, module="all", plan="ENTERPRISE",
                    seats=25, valid_for_days=365,
                )
            except Exception:  # noqa: BLE001
                logger.exception("Échec attribution licence par défaut.")
            logger.info("OIDC: tenant créé en auto pour slug='%s'.", slug)

        target_role = _resolve_role(claims)
        membership, created = TenantUser.objects.get_or_create(
            tenant=tenant, user=user,
            defaults={"role": target_role, "is_active": True},
        )

        if not created:
            # On ne rétrograde JAMAIS automatiquement. On peut promouvoir.
            priority = {"OWNER": 5, "ADMIN": 4, "MANAGER": 3, "MEMBER": 2, "VIEWER": 1}
            if priority.get(target_role, 0) > priority.get(membership.role, 0):
                membership.role = target_role
            if not membership.is_active:
                membership.is_active = True
            membership.save(update_fields=["role", "is_active"])

        logger.info(
            "OIDC: membership %s tenant=%s user=%s role=%s",
            "created" if created else "updated",
            tenant.slug, user.email or user.username, membership.role,
        )
