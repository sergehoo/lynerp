# LYNEERP — Modules Paie, Stock/Logistique, Workflows

Document d'installation et d'usage des trois nouveaux modules livrés en
extension du socle ERP + IA.

---

## 1. Module Paie (`payroll`)

### 1.1 Concepts

```
PayrollItem (rubrique : SAL_BASE, CNPS_SAL, ITS, ...)
        ▼
PayrollProfile (modèle : "OHADA_EMPLOYE", "OHADA_CADRE")
        ▼
EmployeePayrollProfile (lien employé ↔ profil + base_salary)
        ▼
PayrollPeriod (mois courant) + Payslip + PayslipLine
```

### 1.2 Rubriques OHADA standards

Catalogue fourni par `payroll.services.seed.OHADA_DEFAULT_ITEMS` :

- **Gains** : `SAL_BASE`, `PRIME_TRANSPORT`, `PRIME_PERF`, `HEURES_SUP`
- **Retenues salarié** : `CNPS_SAL` (6.3 %), `ITS` (10 % indicatif), `AVANCE_SAL`
- **Charges patronales** : `CNPS_PAT` (16.5 %), `ACCIDENT_TRAV` (2 %)

> ⚠️ Les taux fournis sont **indicatifs**. À valider avec votre comptable
> avant production. Les overrides se font via `PayrollProfileItem.rate_override`
> ou directement sur `PayrollItem`.

### 1.3 Initialisation tenant

```bash
# Tous les tenants actifs
docker compose exec rh python manage.py seed_payroll --all

# Un tenant spécifique
docker compose exec rh python manage.py seed_payroll --tenant <slug|uuid>
```

### 1.4 Workflow de calcul

1. Créer une `PayrollPeriod` (mois courant).
2. Pour chaque employé : créer un `EmployeePayrollProfile` (profil + base_salary).
3. Créer un `Payslip(employee, period, employee_profile)` en statut DRAFT.
4. Saisir les `PayrollAdjustment` (heures sup, primes exceptionnelles, etc.).
5. Lancer le calcul :

   ```bash
   POST /api/payroll/payslips/<id>/compute/
   POST /api/payroll/periods/<id>/compute/   # batch sur la période
   ```

6. Approuver chaque bulletin :

   ```bash
   POST /api/payroll/payslips/<id>/approve/
   POST /api/payroll/payslips/<id>/mark-paid/
   ```

7. Clôturer la période :

   ```bash
   POST /api/payroll/periods/<id>/close/
   ```

   Génère automatiquement un `PayrollJournal` agrégé.

### 1.5 IA Paie

| Endpoint                                       | Effet                                 |
|------------------------------------------------|---------------------------------------|
| `POST /api/payroll/ai/explain-payslip/`         | Explication pédagogique du bulletin   |
| `POST /api/payroll/ai/detect-anomalies/`        | Détection statistique (outliers 2σ)   |
| `POST /api/payroll/ai/simulate-salary/`         | Simulation brut/net sans persistance  |

### 1.6 Garde-fou

Le **moteur de calcul est déterministe** — aucun calcul n'est délégué au LLM.
L'IA ne fait que pédagogie / détection / simulation.

---

## 2. Module Stock / Logistique (`inventory`)

### 2.1 Concepts

```
ArticleCategory ─► Article ─► Inventory (par entrepôt)
                       │
                       └─► StockMovement (IN/OUT/ADJUST/TRANSFER)
                                  │
                                  ▼
                         signal post_save
                                  │
                                  ▼
                       Inventory mis à jour + StockAlert si seuil
                                  
Supplier ─► PurchaseOrder ─► PurchaseOrderLine
                  │
                  └─► GoodsReceipt ─► GoodsReceiptLine
```

### 2.2 Endpoints clés

```bash
GET  /api/inventory/articles/                  # CRUD articles
GET  /api/inventory/inventories/               # stocks consolidés (lecture)
POST /api/inventory/movements/                 # créer un mouvement (déclenche maj+alertes)
POST /api/inventory/purchase-orders/<id>/submit/    # soumettre un BC
POST /api/inventory/purchase-orders/<id>/approve/   # approuver (rôles élevés)
POST /api/inventory/alerts/<id>/acknowledge/        # reconnaître une alerte
POST /api/inventory/alerts/<id>/resolve/            # résoudre
```

### 2.3 IA Logistique

| Endpoint                                            | Effet                                  |
|-----------------------------------------------------|----------------------------------------|
| `POST /api/inventory/ai/forecast-stockouts/`         | Prédiction ruptures (déterministe)     |
| `POST /api/inventory/ai/recommend-reorder/`          | Suggestion BC + AIAction validation    |
| `POST /api/inventory/ai/analyze-suppliers/`          | Analyse comparative fournisseurs       |

`recommend-reorder` ne crée **pas** de bon de commande directement : il
crée une `AIAction` que le responsable achats doit valider via `/ai/actions/`.

### 2.4 Alertes seuils

Les alertes (`StockAlert`) sont créées automatiquement lors d'un mouvement
si :

- `quantity ≤ 0` → `OUT_OF_STOCK`
- `quantity ≤ article.min_stock` → `LOW_STOCK`
- `quantity ≥ article.max_stock` → `OVERSTOCK`

Les doublons sur alerte ouverte sont évités. UI : `/inventory/alerts/`.

---

## 3. Workflows / Notifications / Audit (`workflows`)

### 3.1 Workflows d'approbation

Modèle générique pour valider n'importe quel objet métier :

```python
from workflows.services import submit_for_approval, approve_step
from workflows.models import ApprovalWorkflow

wf = ApprovalWorkflow.objects.get(tenant=tenant, code="PO_APPROVAL")
req = submit_for_approval(
    tenant=tenant, workflow=wf, requested_by=user,
    title="BC #1234", target_obj=purchase_order,
)
approve_step(request=req, decided_by=approver, comment="OK")
```

L'objet ciblé est attaché via une `GenericForeignKey`.

### 3.2 Notifications

Multi-canal (`IN_APP`, `EMAIL`, `WEBHOOK`). Helper :

```python
from workflows.services import notify
notify(
    tenant=tenant, user=user,
    title="Bulletin disponible",
    body="Votre bulletin avril est prêt.",
    url="/payroll/payslips/<id>/",
)
```

### 3.3 Audit transversal

`AuditEvent` : journal cross-module (différent de `AIAuditLog` pour les
actions IA). Filtrable par sévérité (`LOW`/`MEDIUM`/`HIGH`/`CRITICAL`).

### 3.4 IA Admin

| Endpoint                                  | Effet                                              |
|-------------------------------------------|----------------------------------------------------|
| `inventory.recent_activities` (outil)      | Résumé Markdown des événements récents             |
| `admin.unusual_actions` (outil)            | Liste des événements HIGH/CRITICAL des dernières 24h |

Disponibles via le panel chat IA (sélecteur module = "Administration") ou
via `POST /api/ai/tools/<name>/run/`.

---

## 4. Migrations à appliquer

```bash
docker compose exec rh python manage.py makemigrations payroll inventory workflows
docker compose exec rh python manage.py migrate
```

Vous devriez voir :

```
Migrations for 'payroll':
  payroll/migrations/0001_initial.py
    - Create model PayrollItem, PayrollProfile, PayrollProfileItem,
      EmployeePayrollProfile, PayrollPeriod, Payslip, PayslipLine,
      PayrollAdjustment, PayrollJournal
Migrations for 'inventory':
  inventory/migrations/0001_initial.py
    - Create model Article, ArticleCategory, Warehouse, Inventory,
      StockMovement, Supplier, PurchaseOrder, PurchaseOrderLine,
      GoodsReceipt, GoodsReceiptLine, StockAlert
Migrations for 'workflows':
  workflows/migrations/0001_initial.py
    - Create model ApprovalWorkflow, ApprovalStep, ApprovalRequest,
      ApprovalDecision, Notification, AuditEvent
```

## 5. Tests garde-fou

```bash
docker compose exec rh pytest \
  tests/test_payroll_engine.py \
  tests/test_inventory_engine.py \
  -q
```

Couvre :
- Cohérence brut/net sur le moteur paie
- Idempotence du recalcul
- Mise à jour automatique de l'inventaire sur mouvement
- Déclenchement des alertes LOW_STOCK / OUT_OF_STOCK

## 6. Recommandations prod

- Initialiser le seeder paie pour chaque nouveau tenant à sa création.
- Lancer `compute_period` en tâche **Celery** pour les gros effectifs.
- Stocker les bulletins PDF dans MinIO (`Payslip.pdf_url`) — une commande
  `manage.py generate_payslip_pdfs` est à venir.
- Activer le hook compta : `PayrollJournal` peut générer automatiquement
  un `JournalEntry` finance via un executor `ai_assistant.executors`.
- Configurer un workflow `PO_APPROVAL` par tenant pour les bons de
  commande > seuil défini.
