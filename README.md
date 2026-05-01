# LYNEERP

ERP multi-tenant moderne (Django 4.2 + DRF + PostgreSQL + Redis + Celery
+ Tailwind 3 + Alpine 3 + Keycloak SSO + MinIO/S3) avec un module IA
transversal basé sur **Ollama** local (`qwen2.5:7b` par défaut).

> **Garde-fou central** : l'IA n'exécute jamais une action irréversible
> sans validation humaine. Tout passe par le workflow ``AIAction`` (status
> ``PROPOSED → APPROVED → EXECUTED``) avec audit complet.

---

## Sommaire

1. [Architecture](#1-architecture)
2. [Modules](#2-modules)
3. [Démarrage rapide](#3-démarrage-rapide)
4. [Initialisation tenant](#4-initialisation-tenant)
5. [Tests](#5-tests)
6. [Documentation détaillée](#6-documentation-détaillée)
7. [Déploiement production](#7-déploiement-production)

---

## 1. Architecture

```
Lyneerp/                 # config Django (settings, urls, celery, exception_handler)
  core/                  # modèles abstraits (TenantOwnedModel, TenantManager) + tenant resolver

tenants/                 # multi-tenant : Tenant, TenantUser, License, SeatAssignment,
                         # middleware unifié, context processor

hr/                      # Ressources Humaines : Employee, Recruitment, JobApplication,
                         # Contracts, Leaves, Attendance, Payroll history…

finance/                 # Comptabilité : plan comptable, journaux, écritures, taxes,
                         # factures clients/fournisseurs, paiements, audit hash chain

payroll/                 # Paie : rubriques, profils, périodes, bulletins, journal de paie
                         # Moteur DÉTERMINISTE (services/engine.py)

inventory/               # Stock / Achats : articles, entrepôts, mouvements, alertes,
                         # fournisseurs, bons de commande, réceptions

workflows/               # Workflows d'approbation génériques + notifications + audit
                         # transversal (AuditEvent, Notification, ApprovalRequest)

ai_assistant/            # Module IA transversal :
                         #   - services Ollama (chat sync + streaming SSE)
                         #   - registre prompts par module (override en DB)
                         #   - registre outils métier
                         #   - workflow AIAction avec validation humaine
                         #   - audit complet (AIAuditLog)
                         #   - panel chat web (Tailwind + Alpine)
```

Tous les modèles métier héritent de `Lyneerp.core.models.TenantOwnedModel`,
ce qui garantit l'isolation multi-tenant **par construction**.

---

## 2. Modules

### 🟪 RH (`hr`)

- Employés, départements, postes
- Recrutements, candidatures (avec scoring IA)
- Contrats, avenants, alertes
- Congés, soldes, approbations
- Pointage, performance, médical

### 🟦 Finance (`finance`)

- Plan comptable (SYSCOHADA / PCG / IFRS)
- Journaux, écritures, lignes, taxes
- Factures clients et fournisseurs
- Paiements (avec idempotency_key)
- Audit hash chain immuable
- Banque, rapprochements

### 🟩 Paie (`payroll`)

- Rubriques (gain / retenue / patronale / info)
- Profils OHADA standards (`OHADA_EMPLOYE`, `OHADA_CADRE`)
- Périodes mensuelles + bulletins + lignes
- **Moteur déterministe** (jamais de LLM dans les calculs)
- Journal de paie + executor pour passation comptable
- IA : explication bulletin, anomalies, simulation

### 🟧 Stock / Achats (`inventory`)

- Articles, catégories, entrepôts
- Mouvements (IN/OUT/ADJUST/TRANSFER) + signal automatique
- Inventaires consolidés (cache calculé)
- Alertes seuils (LOW_STOCK / OUT_OF_STOCK / OVERSTOCK)
- Fournisseurs, bons de commande, réceptions
- IA : prévision rupture, recommandation réapprovisionnement, analyse fournisseurs

### 🟫 Workflows (`workflows`)

- `ApprovalWorkflow` + `ApprovalStep` génériques (n'importe quel objet)
- `Notification` multi-canal (in-app, email, webhook)
- `AuditEvent` cross-module
- Signaux automatiques : paie validée → notif salarié, stock OUT → notif managers

### 🟪 IA Transversale (`ai_assistant`)

- Chat global (`/ai/`) + module-aware
- Streaming SSE
- Prompts versionnés par module + override DB par tenant
- Registre d'outils (`@registry.tool`)
- Workflow `AIAction` (validation humaine obligatoire pour les actions write)
- Executors d'actions approuvées
- Audit complet (`AIAuditLog`)

---

## 3. Démarrage rapide

### Prérequis

- Docker + Docker Compose
- 16 Go RAM minimum (Ollama + Postgres + Keycloak + MinIO)

### Lancement

```bash
# 1. Variables d'environnement
cp .env.example .env
$EDITOR .env       # remplir SECRETS, ALLOWED_HOSTS, KEYCLOAK_*, OLLAMA_*

# 2. Build + démarrage
docker compose up -d --build

# 3. Migrations
docker compose exec rh python manage.py makemigrations
docker compose exec rh python manage.py migrate

# 4. Pull du modèle Ollama (qwen2.5:7b par défaut)
docker compose logs -f ollama          # patientez "[ollama] Pull qwen2.5:7b..."
```

URLs disponibles :

- `https://rh.<domain>/` — root → `/hr/` ou `/login/`
- `https://rh.<domain>/hr/` — module RH
- `https://rh.<domain>/finance/` — Finance
- `https://rh.<domain>/payroll/` — Paie
- `https://rh.<domain>/inventory/` — Stock
- `https://rh.<domain>/workflows/requests/` — Approbations
- `https://rh.<domain>/workflows/notifications/` — Notifications
- `https://rh.<domain>/ai/` — Panel chat IA
- `https://rh.<domain>/ai/actions/` — Actions IA à valider
- `https://rh.<domain>/api/docs/` — Swagger
- `https://rh.<domain>/admin/` — Django admin

---

## 4. Initialisation tenant

Pour un nouveau tenant, après création (Tenant + TenantUser admin) :

```bash
# Référentiel paie OHADA
docker compose exec rh python manage.py seed_payroll --tenant <slug>

# Référentiel stock (jeu démo)
docker compose exec rh python manage.py seed_inventory_demo --tenant <slug>

# Workflows standards (PO, paie, contrat)
docker compose exec rh python manage.py seed_workflows --tenant <slug>
```

Puis créer en admin :
1. Plan comptable (Account) — minimal pour la passation paie : `4311`, `4421`, `4711`, `6311`, `6411`
2. Période comptable OPEN couvrant la période de paie
3. Pour chaque employé : `EmployeePayrollProfile` (profil + base_salary)

---

## 5. Tests

```bash
docker compose exec rh pytest -q
```

Suite couvre :

- Isolation tenant (resolver, middleware, viewsets)
- Auth Keycloak (login, validation, refus cross-tenant)
- Module IA : isolation conversations, workflow AIAction, séparation privilèges
- Hash chain audit Finance (détection altération)
- Idempotence Payment (double paiement bloqué)
- Moteur paie : équilibre brut/net + idempotence du recalcul
- Stock : mouvement → maj inventory + alertes seuils
- Workflows : avancement étapes, rejet, audit

---

## 6. Documentation détaillée

| Document | Contenu |
|----------|---------|
| `docs/AUDIT_LYNEERP.md` | Audit initial + plan de correction par phase |
| `docs/MIGRATION_GUIDE.md` | Migration de l'ancien projet vers le nouveau socle |
| `docs/PHASE_5_6_NOTES.md` | Détails Phase 5 (HR durci) + Phase 6 (Finance hash chain, idempotency) |
| `docs/AI_INSTALL.md` | Installation et exploitation du module IA transversal |
| `docs/MODULES_PAIE_STOCK_WORKFLOWS.md` | Documentation des modules Paie / Stock / Workflows |

---

## 7. Déploiement production

### Stack recommandée

- **Reverse proxy** : Traefik avec TLS/Let's Encrypt
- **Postgres 16** dédié (pgbouncer en pooler)
- **Redis 7** pour cache + Celery broker (DBs séparées)
- **Keycloak 26** en mode HA (2 nœuds)
- **MinIO** ou S3 pour `MEDIA_ROOT` et exports PDF
- **Ollama** sur machine GPU dédiée (NVIDIA)
- **Sentry** sur DJANGO + DRF

### Sécurité

- `DEBUG=False` strict (le code lève `RuntimeError` si oublié en prod)
- `SECRET_KEY` ≥ 50 caractères, rotation périodique
- HSTS preload activé (`SECURE_HSTS_SECONDS=31536000`)
- Cookies `Secure` + `HttpOnly` + `SameSite=Lax`
- CSP stricte au niveau Traefik
- Audit `AIAuditLog` archivé en bucket WORM (immutabilité réglementaire)
- Backups Postgres chiffrés quotidiens, MinIO réplique cross-bucket

### Performance

- Gunicorn `--workers $(2*CPU+1)` `--worker-class gthread` `--threads 4`
- Cache Redis avec `IGNORE_EXCEPTIONS=True` (best-effort)
- WhiteNoise + `CompressedStaticFilesStorage`
- Build assets en multi-stage Docker (Node 20 → Python 3.11 slim)

### Conformité

- **RGPD** : `AIMessage.content` peut contenir des données personnelles —
  prévoir une procédure d'effacement par utilisateur.
- **OHADA** : taux paie indicatifs, à valider par un comptable agréé.
- **Droit du travail local** : la rédaction IA des contrats reste informative,
  validation juridique obligatoire avant signature.

### CI/CD recommandé

```yaml
# .github/workflows/ci.yml (exemple)
- ruff check .
- pytest --cov=. --cov-report=xml
- python manage.py check --deploy --settings=Lyneerp.settings.prod
- docker build -t lyneerp:${{ github.sha }} .
- docker push registry/lyneerp:${{ github.sha }}
```

---

## Crédits

LYNEERP — ERP intelligent multi-tenant.
Architecture mise au standard production en plusieurs sessions d'audit
et refonte (cf. `docs/AUDIT_LYNEERP.md`).
