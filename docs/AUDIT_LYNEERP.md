# Audit technique LYNEERP — Rapport complet

**Périmètre auditer** : Django 4.2.25 / DRF / PostgreSQL / Keycloak (mozilla-django-oidc) / Celery / Redis / MinIO / WhiteNoise / WeasyPrint
**Modules** : `Lyneerp/` (config), `tenants/` (multi-tenant + licences), `hr/` (Ressources Humaines), `finance/` (comptabilité, facturation, trésorerie)
**Volumétrie** : ~14 800 lignes Python, 66 fichiers .py, 57 templates HTML, 4 apps installées
**Date d'audit** : 2026-04-30

---

## Légende des gravités

| Code | Gravité | Action attendue |
|------|---------|----------------|
| 🔴 **BLOQUANT** | Faille de sécurité, fuite de données tenant, app cassée en prod | Corriger immédiatement |
| 🟠 **HAUT** | Bug majeur, dette critique, sécurité dégradée | Corriger avant mise en prod |
| 🟡 **MOYEN** | Bug fonctionnel, mauvaise pratique notable | Planifier sous 1-2 sprints |
| 🟢 **BAS** | Amélioration, lisibilité, optimisation | À faire opportunément |

---

## 1. Architecture du projet — vue d'ensemble

### 1.1 🔴 BLOQUANT — Double source de settings

Le projet contient **simultanément** :

- `Lyneerp/settings.py` (124 lignes, settings « par défaut » `startproject`)
- `Lyneerp/settings/` (package avec `__init__.py`, `base.py`, `dev.py`, `prod.py`)

`manage.py` pointe sur `Lyneerp.settings`. Python résout vers le **package** (qui prime sur le module) — donc `settings.py` n'est jamais lu, mais sa simple présence trompe les outils (IDE, déploiement, lecteurs humains) et peut piéger une CI. **À supprimer.**

### 1.2 🟠 HAUT — `INSTALLED_APPS` invalide

`Lyneerp/settings/base.py` enregistre `'redis'` comme app Django alors que `redis` est juste une lib Python. Au premier `manage.py check`, Django lèvera `ImportError` ou `ModuleNotFoundError` lors d'un autoload. À **retirer**.

Manquent par ailleurs :

- `django.contrib.messages` est OK mais le contexte processor `messages` est OK aussi.
- Pas d'enregistrement de `mozilla_django_oidc` dans la config de prod alors que les URLs `oidc/` sont incluses dans `Lyneerp/urls.py`.
- Pas d'`AUTH_USER_MODEL` (donc `auth.User` standard, mais le code parle parfois de `user.employee`/`user.is_external_hr` qui n'existent pas par défaut → confusion).

### 1.3 🟠 HAUT — Configuration prod incohérente / dangereuse

`Lyneerp/settings/prod.py`, lignes 5 et suivantes :

```python
DEBUG = True              # ❌ DEBUG en prod
SECURE_SSL_REDIRECT = True
```

- `DEBUG = True` en prod : fuite des stack-traces et configuration secrète.
- `SECRET_KEY` héritée de `base.py` avec fallback `"dev"` → utilisée en prod si l'env n'est pas chargé.
- `ALLOWED_HOSTS` par défaut : `.lyneerp.com,rh.lyneerp.com,localhost,127.0.0.1` (trop permissif et incohérent avec les CSRF_TRUSTED_ORIGINS qui pointent sur `lynerp.com` — typo !).
- `CSRF_TRUSTED_ORIGINS` mélange http/https et **cible le mauvais domaine** (`lynerp.com` au lieu de `lyneerp.com`).
- Aucune des directives `SECURE_HSTS_SECONDS`, `SECURE_HSTS_INCLUDE_SUBDOMAINS`, `SECURE_HSTS_PRELOAD`, `SECURE_REFERRER_POLICY`, `SECURE_BROWSER_XSS_FILTER`, `SECURE_CONTENT_TYPE_NOSNIFF`, `X_FRAME_OPTIONS` n'est posée.
- `SESSION_ENGINE = "django.contrib.sessions.backends.cache"` mais aucun fallback si Redis tombe → 500 immédiat sur toutes les vues.
- `OIDC_RP_CLIENT_SECRET = None` ré-écrit en dur (ligne 117) → impossible d'utiliser un client confidentiel.
- ~110 lignes commentées en dessous : **code mort** à supprimer.

### 1.4 🟡 MOYEN — `ROOT_URLCONF` peu cohérent

`Lyneerp/urls.py` mélange dans la racine `/` :

- Les URLs HR templates (`/`, `/employees/`, `/recruitment/`, `/leaves/`, `/attendance/`, `/employees/<pk>/...`)
- Les URLs auth (`/login/`, `/logout/`, `/auth/exchange/`, `/auth/keycloak/login`)
- L'API RH sous `/api/rh/`
- L'API finance et les vues finance sous `/finance/api/...`
- Le schema/docs DRF
- Les URLs `oidc/`

Conséquence : il n'y a aucune barrière logique entre frontend et API, le module HR « monopolise » la racine, et un changement d'URL HR casse potentiellement tout. Recommandation : déplacer les templates HR sous `/hr/` et garder la racine pour un dashboard global ou rediriger `/` vers `/hr/dashboard/` en fonction du rôle.

### 1.5 🟠 HAUT — Conflit de noms : `LicenseStatusView` ×2

Deux classes différentes portent le même nom et sont importées dans `Lyneerp/urls.py` :

- `hr.api.api_auth.LicenseStatusView` (renvoie status fixe « active »)
- `tenants.api_license.LicenseStatusView` (vraie logique licence/sièges)

Le routage utilise les deux pour des paths différents, mais la collision dans l'import-list est piégeuse et masque l'intention. Renommer en `RHLicenseStatusView` / `TenantLicenseStatusView`.

### 1.6 🟢 BAS — Fichier `Lyneerp/tenant_filters.py`

Ce fichier (16 lignes) définit `TenantScopedQuerysetMixin` qui filtre sur `tenant_id=<slug>`. Il n'est référencé nulle part. Soit on l'utilise comme mixin commun aux apps, soit on le supprime (recommandé : le **fusionner** dans `tenants/utils.py` avec une logique multi-types FK / UUID / slug correcte).

---

## 2. Multi-tenant (`tenants/`)

### 2.1 🔴 BLOQUANT — Quatre middlewares concurrents dans le même fichier

`tenants/middleware.py` définit **simultanément** :

1. `RequestTenantMiddleware`
2. `TenantResolutionMiddleware` ← seul activé dans `settings/base.py`
3. `TenantSessionMiddleware`
4. `TenantMiddleware` (basé sur `MiddlewareMixin`)

Plus une classe vide `CurrentTenant`. Les comportements diffèrent (gestion 403 sur API, header injection, fallback DEFAULT_TENANT…). À **consolider en un seul middleware**, le reste à supprimer.

### 2.2 🔴 BLOQUANT — Fuite tenant via `License` et `SeatAssignment`

Dans `tenants/api_license.py` et `tenants/admin.py` :

```python
SeatAssignment.objects.filter(tenant=tenant_slug, ...)
License.objects.filter(tenant=tenant_slug, ...)
```

Or `License.tenant` et `SeatAssignment.tenant` sont des **`ForeignKey(Tenant)`** (UUID). Filtrer un FK avec un slug renvoie toujours 0 résultat **mais** peut aussi lever une `ValueError` selon les versions de Django/PostgreSQL → endpoint inutilisable et faux statuts de licence. À reprendre : `filter(tenant__slug=tenant_slug)` ou résoudre `tenant` en amont.

### 2.3 🟠 HAUT — Middleware tenant placé avant CSRF

Dans `MIDDLEWARE`, l'ordre est :
`Security → WhiteNoise → Sessions → TenantResolutionMiddleware → Common → CSRF → Auth → ...`

Le middleware tenant peut bloquer une requête par `JsonResponse(..., 403)` **avant** que le CSRF ait validé (problème mineur), surtout cela court-circuite les pages d'erreur Django propres. Recommandation : placer après `CommonMiddleware` mais **avant** `Auth` (pour permettre à des permissions de lire `request.tenant`).

### 2.4 🟠 HAUT — `Tenant.logo_url` mal nommé

```python
logo_url = models.ImageField(upload_to="tenant/logos", max_length=255, blank=True)
```

C'est un `ImageField` (donc l'attribut renvoie un `FieldFile`), mais le nom suggère une chaîne. Tous les accès `tenant.logo_url or ""` (cf. `finance/utils.py`, templates PDF) sont buggés — un `FieldFile` vide est falsy, OK, mais si renseigné on récupère un `FieldFile`, pas une URL. Renommer en `logo` et utiliser `logo.url`. Idem pour `stamp_url` et `signature_url` (CharField, à renommer si on veut héberger sur S3 → ImageField).

### 2.5 🟠 HAUT — `TenantModelBackend` ne sécurise rien

`tenants/auth_backends.py` : la vérif tenant est laissée en `# TODO`. Un user créé sur le tenant A peut donc se connecter via le formulaire en spécifiant le tenant B. **Faille d'isolation directe.**

### 2.6 🟡 MOYEN — Pas de modèle abstrait `TenantOwnedModel` partagé

`finance/models_base.py` définit un `TenantOwnedModel` propre. `hr/models.py` a réinventé sa propre logique avec un FK `tenant` parfois nullable, parfois pas, parfois `db_column='tenant_id'`, parfois non. Aucune cohérence. Recommandation : promouvoir `TenantOwnedModel` au niveau projet (ex. `Lyneerp/core/models.py`) et l'utiliser partout, avec un manager `TenantManager` qui implémente automatiquement l'isolation.

### 2.7 🟡 MOYEN — Regex sous-domaine codée en dur sur `lyneerp.com`

`TENANT_SUBDOMAIN_REGEX = r"^(?P<tenant>[a-z0-9-]+)\.(?:rh\.)?lyneerp\.com$"`. Pour le dev local et pour des domaines blanche-marque, il faut paramétrer via env.

### 2.8 🟡 MOYEN — Modèle `Tenant` mélange identité, branding, fiscalité, paiement

40+ champs dans une seule table. À terme, scinder en `Tenant` + `TenantBranding` + `TenantBilling` (déjà partiellement présent via `TenantBilling` mais redondant).

---

## 3. Authentification Keycloak / OIDC

### 3.1 🔴 BLOQUANT — Login Keycloak côté navigateur expose le client public en clair

`templates/registration/login.html` envoie le grant `password` **directement depuis le navigateur** vers `https://sso.lyneerp.com/realms/lyneerp/protocol/openid-connect/token` :

```js
const KC_CONFIG = { clientId: "rh-core", clientSecret: null };
form.append("grant_type", "password");
form.append("username", username);
form.append("password", password);
```

- Le navigateur reçoit `access_token` et `refresh_token` puis les pose dans `localStorage` → vulnérable XSS. Le projet a déjà un endpoint backend `auth/keycloak/login` qui fait la même chose côté serveur ; les deux coexistent et l'utilisateur ne sait pas lequel est utilisé.
- Côté serveur, `/auth/exchange/` attend un `Authorization: Bearer <token>` mais le formulaire fait `POST /auth/exchange/ {access_token: ...}` → la session locale n'est pas créée correctement (`request.auth` reste vide), donc le user Django reste anonyme.
- **Recommandation** : ne garder que **un seul flow**. Le plus simple et le plus sûr : `Authorization Code Flow + PKCE` via `mozilla-django-oidc` (lien « Keycloak » déjà présent en SSO secondaire — inverser la priorité et supprimer le flow `password` côté navigateur).

### 3.2 🔴 BLOQUANT — `csrf_exempt` sur `keycloak_direct_login`

L'endpoint backend bypasse la protection CSRF. En l'état, n'importe quel site tiers peut soumettre un POST vers `/auth/keycloak/login` avec les credentials d'un user (logué côté navigateur). À retirer ; remplacer par un token CSRF habituel (puisque c'est le même domaine).

### 3.3 🔴 BLOQUANT — Pas de validation tenant ↔ user au login

`keycloak_direct_login` crée/récupère un `auth.User` à partir du seul `username`/`email` Keycloak, **sans jamais vérifier** :

1. Que ce user a un `TenantUser` actif sur le tenant déduit.
2. Que la licence du tenant est valide.
3. Que le rôle Keycloak est cohérent.

Conséquence : un utilisateur supprimé côté Keycloak conserve son compte local. Un utilisateur du tenant A peut se forger une session pour le tenant B en passant `?tenant_id=B`.

### 3.4 🟠 HAUT — Deux `KeycloakJWTAuthentication` concurrents

- `hr/auth.py` (utilisé par `REST_FRAMEWORK.DEFAULT_AUTHENTICATION_CLASSES`)
- `hr/api/keycloak.py` (orphelin)

À supprimer le doublon orphelin.

### 3.5 🟠 HAUT — Cookie de session insecure en dev mais aucune CSRF policy en prod

`prod.py` pose bien `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `SAMESITE`, `SESSION_COOKIE_DOMAIN=.lyneerp.com`. Manquent : `CSRF_COOKIE_HTTPONLY`, `SESSION_COOKIE_HTTPONLY = True` (par défaut OK), et l'âge de session est posé à 2h sans rappel d'inactivité côté UI.

### 3.6 🟡 MOYEN — `LICENSE_ENFORCEMENT = False`

Toutes les permissions licence sont des **no-op**. C'est un choix actuel mais documenter clairement et rendre l'enforcement piloté par tenant (pas globalement).

### 3.7 🟡 MOYEN — `tenants/forms.TenantAuthenticationForm.confirm_login_allowed` est vide

```python
def confirm_login_allowed(self, user):
    tenant_id = self.cleaned_data.get("tenant_id")
    # TODO: vérifier l'accès du user au tenant_id
    super().confirm_login_allowed(user)
```

Pareil que le backend : aucune isolation réelle.

---

## 4. Module HR

### 4.1 🔴 BLOQUANT — Filtrage tenant **désactivé** sur `EmploymentContractDetailView`

`hr/views.py` ligne 397-399 :

```python
# tenant_id = getattr(self.request, "tenant_id", None)
# if tenant_id:
#     qs = qs.filter(tenant_id=tenant_id)
```

→ **N'importe quel utilisateur authentifié peut consulter le contrat de n'importe quel tenant** en connaissant l'ID. Faille d'isolation grave.

### 4.2 🔴 BLOQUANT — `EmployeeUpdateView`/`EmployeeDeleteView` sans filtrage tenant

Idem, ces deux vues étendent `UpdateView`/`DeleteView` sans surcharger `get_queryset()` → un user du tenant A peut éditer/supprimer un employé du tenant B en connaissant son `pk`.

### 4.3 🟠 HAUT — Modèles HR au stockage tenant **incohérent**

Lecture rapide :

- `Department.tenant` : `ForeignKey(Tenant, null=True, blank=True, on_delete=SET_NULL, db_column='tenant_id')`
- `Position.tenant` : `ForeignKey(Tenant, on_delete=PROTECT, null=True, blank=True)` (autorise donc des Positions globales sans tenant — **fuite potentielle**)
- D'autres modèles utilisent `tenant_id = CharField`/`UUIDField` selon les cas

`BaseTenantViewSet.get_queryset` fait des `Q(tenant_id=str(tenant.id)) | Q(tenant_id=slug)` pour s'adapter — c'est une rustine. Il faut **uniformiser** sur `tenant = ForeignKey(Tenant, on_delete=CASCADE, related_name='%(app_label)s_%(class)ss')`, non-nullable, et supprimer toute trace de `tenant_id` en CharField.

### 4.4 🟠 HAUT — `BaseTenantViewSet` peu sûr

```python
def get_queryset(self):
    if self.request.user and self.request.user.is_superuser:
        return super().get_queryset()
    tenant = self.get_tenant()
    if not tenant:
        return self.queryset.none()
    ...
    return qs.none()
```

- Le fallback final renvoie `qs.none()` mais la branche `tenant.id`/`slug` peut renvoyer la queryset complète si **le modèle n'a pas de champ `tenant`** (vérification fragile via `hasattr`).
- Aucun raise explicite si `tenant` manquant et l'utilisateur n'est pas superuser → silent fail.

### 4.5 🟠 HAUT — `from django.contrib.auth.models import User` dans `hr/api/serializers.py`

Mauvaise pratique : si on passe à un custom user, tout casse. Utiliser `get_user_model()`.

### 4.6 🟠 HAUT — Statuts métier inconsistants

`LeaveRequest.status` est utilisé tantôt en minuscules (`"approved"`, `"pending"`, `"rejected"`, `"cancelled"`) tantôt comme `STATUS_CHOICES`. Idem `Recruitment.status` (`"OPEN"`, `"IN_REVIEW"`, …). À uniformiser via `TextChoices`.

### 4.7 🟠 HAUT — Code dupliqué : tenant resolver

`get_current_tenant_from_request` (dans `hr/views.py`), `tenants/utils.get_tenant_from_request`, `BaseTenantViewSet.get_tenant`, `RecruitmentStatsView._get_tenant`, `_resolve_tenant`, `_get_tenant_kwargs`… 6 implémentations différentes coexistent. À factoriser dans un module unique `tenants/services.py`.

### 4.8 🟠 HAUT — `hr/views.py` est massif (1674 lignes)

Mélange : helpers tenant, viewsets, permissions, exports xlsx/csv. À scinder :

- `hr/views/dashboard.py`
- `hr/views/employee.py` (web + API)
- `hr/views/recruitment.py`
- `hr/views/contracts.py`
- `hr/views/leave.py`
- `hr/views/attendance.py`
- `hr/views/medical.py`
- `hr/views/payroll.py`
- `hr/permissions.py` (déjà existant, à enrichir)
- `hr/services/employee_export.py` (déjà existant, à étoffer)
- `hr/services/contract_export.py`

### 4.9 🟡 MOYEN — Cohérence des serializers

- `RecruitmentSerializer` a `fields = "__all__"` + `read_only_fields = ("tenant", "status", ...)` → expose tous les champs internes y compris JSON.
- `EmploymentContractSerializer.Meta.fields = "__all__"` même remarque.
- Beaucoup de serializers déclarent `tenant_id` dans `fields` alors qu'il n'existe pas comme champ direct (uniquement via FK `tenant`) → erreurs DRF si sérialisation stricte.

### 4.10 🟡 MOYEN — Pas de `filterset_class` django-filter

`hr/filters.py` définit un `EmploymentContractFilter` mais aucun viewset ne l'utilise (pas d'import dans `hr/views.py`). Recommandation : déclarer `filter_backends = [DjangoFilterBackend, ...]` + `filterset_class` partout.

### 4.11 🟢 BAS — `hr/views_me.my_access` non câblée

Cette vue n'apparaît dans aucun `urls.py`. À supprimer ou exposer.

### 4.12 🟢 BAS — `hr/views.py` ligne 822-825 : code mort

```python
User = get_user_model()
log = logging.getLogger(__name__)
User = get_user_model()  # doublon
```

---

## 5. Module Finance

### 5.1 🟠 HAUT — `finance/views.py` / `finance/urls.py` cohérents mais confus

L'architecture **CRUD générique** via `crud_include` + `custom_include` est plutôt bonne, mais :

- `finance/urls.py` a 80 lignes de **code commenté** en bas du fichier (l'ancienne version) → suppression.
- Les vues `JournalEntry`/`Quote`/`Invoice`/`VendorBill`/`ExpenseReport`/`PaymentOrder` doivent toutes gérer un `inlineformset_factory` — non visible dans la portion lue mais à valider qu'on a bien `transaction.atomic`, `formset.is_valid()` et la sécurisation tenant sur les lignes.

### 5.2 🟠 HAUT — `finance/forms.py` toutes les forms exposent `fields = "__all__"`

Inclut le champ `tenant` (qui devient `disabled` via `TenantModelForm`), mais cela expose aussi des champs internes (`is_deleted`, `event_hash`, `prev_hash` pour l'audit, etc.). À durcir avec une liste blanche.

### 5.3 🟠 HAUT — `AuditEvent.save()` lit `created_at` avant insert

```python
"created_at": self.created_at.isoformat() if self.created_at else None,
```

Sur `auto_now_add=True`, `created_at` n'est défini qu'**après** le premier `super().save()`. La hash chain dans cette branche est donc fragile. Recommandation : injecter un `created_at = timezone.now()` explicite avant calcul du hash, ou faire le hash dans un `post_save` signal.

### 5.4 🟡 MOYEN — `finance/utils.tenant_to_company` lit `tenant.logo_url`

Comme noté en 2.4, c'est un `ImageField` → renvoie un `FieldFile`. Ce dict est utilisé dans les templates PDF (`templates/finance/invoice/pdf_premium.html`, `quote/pdf.html`) → l'URL réelle est manquante.

### 5.5 🟡 MOYEN — `MoneyFieldMixin` n'est pas utilisé

Le mixin existe mais aucun champ Money n'y a recours ; les modèles `Quote`, `Invoice`, `Payment` redéfinissent leurs propres `DecimalField`. À factoriser pour garantir la précision uniforme.

### 5.6 🟡 MOYEN — Pas de gestion d'**idempotence** sur les paiements

Modèle `Payment` non encore lu en détail, mais d'après les imports il n'y a pas de `idempotency_key` (header courant côté SaaS de paiement). Indispensable si on intègre Stripe / mobile money.

---

## 6. Templates / UI / accessibilité

### 6.1 🔴 BLOQUANT — Tailwind via CDN en prod

```html
<script src="https://cdn.tailwindcss.com"></script>
```

Présent dans `templates/hr/base.html` et `templates/registration/login.html`. La **doc officielle Tailwind** interdit explicitement ce CDN en prod (perf catastrophique, bundle 3 Mo, recompilation à chaque page). À remplacer par un build Tailwind v3 en local (`tailwindcss -i src.css -o static/dist/main.css --minify`) servi par WhiteNoise.

### 6.2 🟠 HAUT — Alpine.js et SweetAlert2 et FontAwesome via CDN

Idem, dépendant de réseaux externes en prod. À internaliser ou à servir via `staticfiles`. À défaut, ajouter une politique CSP explicite (actuellement : aucune).

### 6.3 🟠 HAUT — `templates/registration/login.html` envoie `grant_type=password` au browser

Cf. § 3.1. Du point de vue UI : le bouton « Keycloak (SSO) » fait `window.location='/oidc/authenticate/'` (correct), tandis que le formulaire principal lance le flow password en JS — incohérent et dangereux.

### 6.4 🟡 MOYEN — Templates HR `_tab_*.html`

Les onglets `templates/hr/employee/_tab_payroll.html`, `_tab_leaves.html` etc. à valider en détail (non lu intégralement). Premier coup d'œil : pas d'aria-roles ni de focus management pour la navigation onglets → WCAG 2.1 niveau A non garanti.

### 6.5 🟡 MOYEN — Templates finance « shared/list_skeleton.html »

À regarder s'il y a une stratégie commune. Si oui : OK, factoriser plus loin.

### 6.6 🟢 BAS — Multilingue / i18n

Tous les libellés sont en français en dur. Si LYNEERP cible aussi anglophone (tenants internationaux), il faut wrap en `{% trans %}` et activer `LocaleMiddleware`.

---

## 7. Tests, qualité, performance, déploiement

### 7.1 🔴 BLOQUANT — Tests inexistants

`tests.py` de chaque app fait 3 lignes (juste `from django.test import TestCase`). **Aucun test unitaire ni d'intégration** ne couvre :

- L'isolation multi-tenant (test critique)
- Le login Keycloak
- Les permissions DRF
- Les CRUD critiques (Employee, Invoice, JournalEntry)
- Les exports CSV/XLSX
- Le hash chain audit

### 7.2 🟠 HAUT — Aucune configuration de logging

Pas de `LOGGING` ni en `base.py` ni en `prod.py`. En prod, on perd toute trace structurée des erreurs. À ajouter (handler console + fichier rotatif + Sentry optionnel).

### 7.3 🟠 HAUT — Aucune configuration Celery visible

`hr/tasks.py` utilise `@shared_task` mais :

- Pas de `Lyneerp/celery.py` central
- Pas d'`__init__.py` qui import `celery_app`
- Pas de `CELERY_BROKER_URL`/`CELERY_RESULT_BACKEND` dans settings
- Aucun `beat_schedule` (alertes contrats expirants, dunning…)

### 7.4 🟠 HAUT — `requirements.txt` non figé / hétérogène

Présence de **`dotenv==0.9.9`** ET `python-dotenv==1.2.1` → conflit. `pypdf2`, `pdfminer.six`, `pdfplumber` cohabitent (3 lib PDF). `gunicorn` sans version. À nettoyer + scinder en `requirements/base.txt`, `requirements/dev.txt`, `requirements/prod.txt`.

### 7.5 🟠 HAUT — `.env` versionné

Le `.env` est **présent dans le repo** avec des secrets bien réels (`KEYCLOAK_CLIENT_SECRET=xyHrh7B4v6Nbgarq968cfdHLO2uGr1Fd`, `KEYCLOAK_ADMIN_PASSWORD=weddingLIFE@2018`, `DB_PASSWORD=weddingLIFE18`). Le `.gitignore` (10 octets seulement) ne l'exclut visiblement pas. **Faire une rotation immédiate des secrets** + `.env.example` en repo + ajouter `.env` à `.gitignore`.

### 7.6 🟠 HAUT — Performances : `select_related`/`prefetch_related` partiels

Bonne nouvelle : `hr/views.py` les utilise dans plusieurs endroits (Employee detail, Recruitment list…). Mais pas systématique : `LeaveRequestViewSet`, `AttendanceViewSet`, tous les viewsets Finance n'optimisent rien.

### 7.7 🟡 MOYEN — `Dockerfile` / `docker-compose.yml` à valider

Non lus en détail dans cet audit. À vérifier : utilisateur non-root, couches optimisées, healthchecks, secrets via `secrets:` plutôt que env, image `python:slim`.

### 7.8 🟡 MOYEN — Pas de `entrypoint.sh` robuste

Présent (`entrypoint.sh`, 730 octets) — à valider : `migrate`, `collectstatic`, `wait-for-it db redis keycloak`, `gunicorn` avec workers ajustés.

### 7.9 🟢 BAS — Fichiers parasites

- `cookies.txt` (130 octets) à la racine du repo — à supprimer.
- `.DS_Store` versionnés (macOS).
- `.idea/` versionné — à mettre dans `.gitignore`.
- `venv/` versionné — **gros problème**, à retirer du tracking.

---

## 8. Plan de correction priorisé

### Phase A — Stabiliser le socle (urgence)

1. Supprimer `Lyneerp/settings.py` (doublon).
2. Refondre `Lyneerp/settings/base.py` : retirer `redis` d'INSTALLED_APPS, retirer `from django.contrib import staticfiles`, ajouter LOGGING, REST_FRAMEWORK, structure config / cache / Celery.
3. Refondre `Lyneerp/settings/prod.py` : `DEBUG = False`, HSTS, X-Frame, secrets via env, supprimer code commenté.
4. Refondre `Lyneerp/settings/dev.py` : conserver simple mais propre.
5. Créer `.env.example`, ajouter `.env`/`.idea/`/`venv/`/`*.pyc`/`__pycache__` à `.gitignore`. **Rotation immédiate des secrets.**
6. Réécrire `Lyneerp/urls.py` : déplacer les vues HR sous `/hr/`, factoriser, renommer les `LicenseStatusView`.
7. Ajouter `Lyneerp/celery.py` + `Lyneerp/__init__.py` qui exporte `celery_app`.

### Phase B — Multi-tenant fiabilisé (critique)

8. Réécrire `tenants/middleware.py` : un seul middleware `TenantMiddleware` propre, supprimer les 3 autres.
9. Créer `Lyneerp/core/models.py` exposant `TenantOwnedModel` + `TenantManager`.
10. Réécrire `tenants/utils.py` (resolver unique).
11. Corriger `tenants/api_license.py` (filter `tenant__slug=` ou résolution explicite).
12. Corriger `tenants/auth_backends.py` (vrai contrôle d'accès).
13. Nettoyer `Lyneerp/tenant_filters.py` (à supprimer ou intégrer).
14. Renommer `Tenant.logo_url` → `logo` (ImageField).

### Phase C — Auth Keycloak unifiée

15. Supprimer le doublon `hr/api/keycloak.py`.
16. Réécrire `templates/registration/login.html` : utiliser `/oidc/authenticate/` (Authorization Code + PKCE), supprimer le grant `password` côté JS.
17. Sécuriser `tenants/auth_views.keycloak_direct_login` (CSRF + validation TenantUser).
18. Réécrire `hr/views_auth.ExchangeTokenView` pour valider le tenant et créer une session locale propre.
19. Documenter claims attendus côté Keycloak (`tenant`, `roles`, `email`).

### Phase D — Module HR durci

20. Activer le filtrage tenant sur `EmploymentContractDetailView`, `EmployeeUpdateView`, `EmployeeDeleteView`.
21. Réécrire `hr/permissions.py` (mixins pour DetailView + permission DRF).
22. Migrer `Department.tenant`, `Position.tenant`, etc. → `ForeignKey(Tenant, on_delete=CASCADE)` non-nullable + `related_name='hr_<modelname>s'`.
23. Splitter `hr/views.py` en sous-modules `hr/views/`.
24. Splitter `hr/models.py` en sous-modules `hr/models/`.
25. Splitter `hr/api/serializers.py` (ou au moins en sous-fichiers par domaine).
26. Brancher `EmploymentContractFilter` (django-filter) et créer les autres FilterSets.

### Phase E — Module Finance durci

27. Supprimer code commenté de `finance/urls.py`.
28. Restreindre `fields = "__all__"` dans les forms.
29. Robustifier la hash chain `AuditEvent`.
30. Ajouter `idempotency_key` sur `Payment`.
31. Vérifier que les vues lignes (Quote/Invoice/...) protègent bien le `tenant` dans `formset.save()`.

### Phase F — UI / Templates

32. Internaliser Tailwind v3 (build local + WhiteNoise).
33. Internaliser Alpine v3, SweetAlert2, FontAwesome.
34. Retirer le grant `password` côté JS du login.
35. Audit accessibilité (WCAG 2.1 AA) : focus management, ARIA roles, contraste, lang.
36. Ajouter `templates/404.html`, `403.html`, `500.html`, `400.html`.

### Phase G — Tests, perf, déploiement

37. Ajouter une suite de tests structurée (`tests/test_tenant_isolation.py`, `tests/test_login.py`, `tests/test_employee_crud.py`, `tests/test_invoice_crud.py`, `tests/test_audit_chain.py`).
38. Configurer `LOGGING` (console + fichier rotatif + format JSON).
39. Configurer Celery (`Lyneerp/celery.py`) + Celery Beat (alertes contrats, dunning).
40. Nettoyer `requirements.txt` en plusieurs fichiers, figer les versions.
41. Auditer `Dockerfile` + `docker-compose.yml` + `entrypoint.sh`.
42. Ajouter une CI minimale (GitHub Actions) : `ruff check`, `mypy --ignore-missing-imports` (optionnel), `pytest`.

---

## 9. Commandes pour relancer proprement après corrections

```bash
# 1. Rotation des secrets (Keycloak admin / DB / S3)
# 2. Reconstruire le venv
python -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements/dev.txt   # ou requirements.txt après nettoyage

# 3. Vérifications statiques
python manage.py check --deploy
python manage.py makemigrations --dry-run
python manage.py validate_templates  # via django-extensions si installé

# 4. Migrations
python manage.py makemigrations tenants hr finance
python manage.py migrate

# 5. Static
python manage.py collectstatic --noinput

# 6. Tests
pytest -x -q

# 7. Démarrage
DJANGO_ENV=dev python manage.py runserver 0.0.0.0:8000
celery -A Lyneerp worker -l INFO
celery -A Lyneerp beat -l INFO
```

---

## 10. Recommandations de déploiement production

- **HTTPS obligatoire** (Traefik / nginx) avec HSTS preload.
- **Postgres 14+** avec `pgbouncer` en pooler, sauvegardes chiffrées hors site.
- **Redis** dédié pour cache + Celery broker (séparer DB 0/1/2).
- **Keycloak** en HA (au moins 2 nœuds), realm `lyneerp`, client `rh-core` confidentiel + PKCE, audience explicite.
- **MinIO** ou S3 pour `MEDIA_ROOT` et exports PDF (avec lifecycle policies).
- **Gunicorn** : `workers = 2*CPU+1`, `--worker-class=gthread`, timeout 60s, `--max-requests=1000 --max-requests-jitter=50`.
- **WhiteNoise** OK en mode `CompressedManifestStaticFilesStorage`.
- **Sentry** branché sur `LOGGING` + DRF `EXCEPTION_HANDLER`.
- **Audit Trail** : sauvegarder `AuditEvent` dans Postgres principal **et** dupliquer vers un bucket WORM (immuabilité réglementaire).
- **CI/CD** : pipeline build → test → deploy avec migration en hook pré-démarrage.
- **Backups** : Postgres `pg_dump` quotidien chiffré, MinIO réplique cross-bucket, Keycloak export realm.
- **Monitoring** : Prometheus + Grafana (latence, erreurs DRF, file Celery, sessions actives par tenant).
- **WAF / rate-limiting** sur les endpoints `/auth/*`, `/api/license/*`.

---

*Fin du rapport. Les corrections concrètes fichier par fichier sont fournies à partir de la phase B (commit suivant).*
