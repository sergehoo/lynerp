# Modules CRM, Projets, Reporting, OCR

Documentation des nouveaux modules livrés en complément.

---

## 1. Module CRM (`crm`)

### Modèles

```
Account ──► Contact (multi)
        ──► Opportunity ──► Pipeline / Stage
                       ──► Activity (call, email, meeting…)

Lead (prospect non qualifié) ──[convert]──► Account + Contact
```

### URLs

| URL                                | Effet                                          |
|------------------------------------|------------------------------------------------|
| `/crm/`                             | Dashboard avec pipelines + KPIs               |
| `/crm/leads/`                       | Liste leads                                    |
| `/crm/opportunities/`               | Liste opportunités                            |
| `/api/crm/accounts/`                | CRUD comptes                                   |
| `/api/crm/contacts/`                | CRUD contacts                                  |
| `/api/crm/pipelines/`, `/stages/`   | CRUD pipelines                                 |
| `/api/crm/opportunities/`           | CRUD + actions `mark-won` / `mark-lost`       |
| `/api/crm/leads/<id>/convert/`      | Conversion lead → compte + contact            |
| `/api/crm/activities/`              | CRUD activités                                 |

### IA CRM

| Outil                         | Effet                                        |
|-------------------------------|----------------------------------------------|
| `crm.score_lead`               | Score 0-100 d'un lead + explication         |
| `crm.next_best_actions`        | Recommandations d'actions sur opportunités  |

---

## 2. Module Projets (`projects`)

### Modèles

```
Project ──► Phase ──► Task (subtasks possibles)
        ──► Milestone
        ──► ProjectMember (lien user + rôle + TJM)

TimeEntry : pointage temps lié à une Task
```

### URLs

| URL                              | Effet                                |
|----------------------------------|--------------------------------------|
| `/projects/`                      | Dashboard (projets actifs + tâches) |
| `/projects/list/`                 | Liste                                |
| `/projects/<id>/`                 | Détail + phases + jalons + tâches   |
| `/api/projects/projects/`         | CRUD                                 |
| `/api/projects/tasks/`            | CRUD tâches                          |
| `/api/projects/time-entries/`     | Pointage                             |

### IA Projets

| Outil                              | Effet                                  |
|------------------------------------|----------------------------------------|
| `projects.summarize`                | Résumé Markdown d'un projet           |
| `projects.priority_recommendations` | Plan d'attaque sur les tâches dues    |

---

## 3. Reporting / BI (`reporting`)

### Modèles

- `Dashboard` + `Widget` (KPI, line, bar, pie, table)
- `KPISnapshot` : valeurs périodiques pour graphiques temporels

### KPIs natifs (registre)

| Code                                | Description                            |
|-------------------------------------|---------------------------------------|
| `hr.headcount`                       | Effectif actif                       |
| `hr.new_hires_30d`                   | Embauches 30 jours                   |
| `payroll.total_net_last_period`      | Net total dernière période clôturée |
| `crm.pipeline_open_amount`           | Pipeline CRM ouvert                  |
| `inventory.open_alerts`              | Alertes stock ouvertes               |
| `projects.active_count`              | Projets actifs                       |
| `ai.actions_pending`                 | Actions IA à valider                 |

### URL

`/reporting/` — dashboard global.

Pour ajouter un KPI : `register_kpi("mon.kpi")` dans n'importe quel module
(ex. `reporting.services` ou un fichier d'extension).

---

## 4. OCR factures (`ocr`)

### Modèles

- `DocumentUpload` : fichier (PDF / DOCX / TXT) + statut
- `ExtractedField` : paire clé/valeur extraite + confiance

### Pipeline

```
Upload ─► extract_text() ─► Ollama (chat_json INVOICE_EXTRACTION_PROMPT)
                          ─► flatten JSON ─► ExtractedField (clé/valeur)
                          ─► statut EXTRACTED
```

L'humain valide / corrige les champs avant import comptable. Une étape
ultérieure (executor `finance.post_journal_entry`) peut générer
l'écriture comptable.

### URLs

| URL                              | Effet                                |
|----------------------------------|--------------------------------------|
| `/ocr/`                           | Liste documents                      |
| `/ocr/<id>/`                      | Détail + champs extraits             |
| `POST /api/ocr/documents/`        | Upload                               |
| `POST /api/ocr/documents/<id>/process/` | Lance l'extraction              |

### Limites MVP

- Lecture des PDF avec ``pdfplumber``, des DOCX avec ``python-docx``,
  des TXT directement.
- Les **images** (JPG/PNG) ne sont PAS encore extraites — brancher
  `pytesseract` ou un service Vision API si besoin.
- L'extraction structurée dépend du LLM (qwen2.5:7b). Pour la prod,
  prévoir un test de précision et augmenter le `temperature=0.1` pour
  plus de déterminisme.

---

## 5. Initialisation rapide

```bash
# Migrations
docker compose exec rh python manage.py makemigrations \
    crm projects reporting ocr ai_assistant

docker compose exec rh python manage.py migrate

# Seed OHADA (référentiel global)
docker compose exec rh python manage.py seed_ohada

# (Optionnel) Seeds tenant
docker compose exec rh python manage.py seed_payroll --tenant <slug>
docker compose exec rh python manage.py seed_inventory_demo --tenant <slug>
docker compose exec rh python manage.py seed_workflows --tenant <slug>

# Tests
docker compose exec rh pytest -q
```

---

## 6. URLs ajoutées au routage racine

| URL                       | Module      |
|---------------------------|-------------|
| `/crm/`, `/api/crm/`       | CRM         |
| `/projects/`, `/api/projects/` | Projets |
| `/reporting/`             | Reporting   |
| `/ocr/`, `/api/ocr/`       | OCR         |
| (existants)               | hr, finance, payroll, inventory, workflows, ai |

Le menu `_includes/lyneerp_modules_menu.html` peut être enrichi pour
exposer ces nouveaux modules dans la sidebar.
