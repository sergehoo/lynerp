# LYNEERP — Guide de migration après audit

Ce guide accompagne la première vague de corrections apportées au projet
(socle Django, multi-tenant, auth Keycloak, UI). Il liste **toutes les
commandes à exécuter** pour basculer le projet sur la nouvelle base.

> Avant tout : faire un backup de la DB Postgres et committer la branche
> courante (les corrections suivantes vont casser certaines URLs et imports).

---

## 1. Faire la rotation des secrets exposés

Le fichier `.env` était versionné avec :

- `KEYCLOAK_CLIENT_SECRET=xyHrh7B4v6Nbgarq968cfdHLO2uGr1Fd`
- `KEYCLOAK_ADMIN_PASSWORD=weddingLIFE@2018`
- `DB_PASSWORD=weddingLIFE18`

**Considérez ces secrets comme compromis.** Faire la rotation :

```bash
# Côté Keycloak (admin console)
# 1) Régénérer le client secret du client `rh-core`
# 2) Changer le mot de passe de l'admin

# Côté Postgres
ALTER USER postgres WITH PASSWORD 'NOUVEAU_MOT_DE_PASSE';
# Mettre à jour DB_PASSWORD dans le nouveau .env
```

Mettre les nouveaux secrets dans le runtime (Docker secrets / k8s secrets / etc.).

## 2. Recréer un .env local depuis le template

```bash
cp .env.example .env
$EDITOR .env   # remplir avec les nouvelles valeurs
```

`./.env` est désormais ignoré par `.gitignore` (vérifier `git status`).

## 3. Recréer un venv propre

```bash
deactivate 2>/dev/null || true
rm -rf .venv venv
python -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements/dev.txt
```

## 4. Lancer les checks Django

```bash
python manage.py check
python manage.py check --deploy   # à exécuter avec DJANGO_ENV=prod en CI
python manage.py makemigrations --dry-run
```

Si vous voyez :

- `tenants.context_processors.current_tenant` introuvable → c'est OK, je l'ai créé.
- `Lyneerp.exception_handler.lyneerp_exception_handler` introuvable → idem.
- `Lyneerp.celery` ou `Lyneerp.core` non importable → vérifier que les
  fichiers `__init__.py` existent (créés par cette migration).

## 5. Migrations DB

```bash
python manage.py migrate
```

Les modèles ne sont pas changés dans cette première vague (sauf nettoyage des
imports). Aucune migration data n'est nécessaire pour l'instant. Les
recommandations restant à appliquer (uniformiser `tenant_id` → `tenant FK`,
`logo_url` → `logo`, etc.) feront l'objet de migrations ultérieures.

## 6. Build des assets front

```bash
npm install
npm run build:css       # Tailwind v3 → static/dist/main.css
npm run vendor:copy     # Copie Alpine, SweetAlert2, FontAwesome dans static/vendor/
python manage.py collectstatic --noinput
```

## 7. Lancer la suite de tests

```bash
pytest -x -q
# ou avec couverture
pytest --cov=. --cov-report=term-missing
```

Les tests fournis couvrent (à ce stade) :

- résolveur de tenant (`tests/test_tenant_resolver.py`)
- isolation multi-tenant API (`tests/test_tenant_isolation.py`)
- API licence (`tests/test_license_status.py`)
- login Keycloak (`tests/test_login_keycloak.py`)

Ce sont des **tests garde-fou** sur les zones critiques de sécurité.
Ajouter ensuite : tests CRUD employé, contrats, factures, audit chain.

## 8. Démarrage local

```bash
DJANGO_ENV=dev python manage.py runserver 0.0.0.0:8000
DJANGO_ENV=dev celery -A Lyneerp worker -l INFO
DJANGO_ENV=dev celery -A Lyneerp beat   -l INFO
```

## 9. Démarrage production (gunicorn)

```bash
DJANGO_ENV=prod python manage.py collectstatic --noinput
DJANGO_ENV=prod python manage.py migrate
DJANGO_ENV=prod gunicorn Lyneerp.wsgi:application \
    --workers 4 --worker-class gthread --threads 4 \
    --timeout 60 --max-requests 1000 --max-requests-jitter 50 \
    --bind 0.0.0.0:8000 --access-logfile - --error-logfile -
```

---

## URLs qui ont changé

| Ancien | Nouveau | Note |
|--------|---------|------|
| `/` | `/hr/` | racine redirige vers HR si authentifié |
| `/employees/...` | `/hr/employees/...` | sous préfixe `/hr/` |
| `/recruitment/` | `/hr/recruitment/` | idem |
| `/leaves/` | `/hr/leaves/` | idem |
| `/attendance/` | `/hr/attendance/` | idem |
| `/auth/keycloak/login` | `/api/auth/keycloak/login/` | namespace clarifié |
| `/auth/exchange/` | `/api/auth/exchange/` | idem |
| `/api/auth/whoami/` | `/api/auth/whoami/` | inchangé |
| `/api/license/status/` | `/api/license/status/` (tenant) ou `/api/license/rh/status/` (status simple) | scindé |
| `/schema/` | `/api/schema/` | regroupement /api/ |
| `/docs/` | `/api/docs/` | idem |

Mettre à jour les liens dans le front si vous les codez en dur.

---

## Ce qui reste à faire (phases 5 et 6 — modules HR & Finance)

La consolidation détaillée des deux modules métier demande plus de travail et
sera traitée dans des sessions dédiées :

1. **HR** :
   - Splitter `hr/views.py` (1674 lignes) en `hr/views/` modulaire.
   - Splitter `hr/models.py` (1988 lignes) en `hr/models/`.
   - Migrer `Department.tenant`, `Position.tenant` etc. en FK non-nullable.
   - Brancher `EmploymentContractFilter` (django-filter) sur tous les viewsets.
   - Réécrire `BaseTenantViewSet` pour utiliser `Lyneerp.core.permissions.TenantQuerysetMixin`.

2. **Finance** :
   - Restreindre `fields = "__all__"` dans `finance/forms.py`.
   - Robustifier le hash chain `AuditEvent`.
   - Ajouter `idempotency_key` sur `Payment`.
   - Auditer formsets (Quote/Invoice/...) + transactions atomiques.

3. **Templates** :
   - Vérifier `_tab_*.html` pour ARIA / focus management (WCAG 2.1 AA).
   - Internaliser tous les CDN restants.

4. **Tests** :
   - CRUD employés / contrats / factures
   - Hash chain audit
   - Permissions par rôle Keycloak

Le plan global et les corrections déjà appliquées sont consignées dans
`docs/AUDIT_LYNEERP.md`.
