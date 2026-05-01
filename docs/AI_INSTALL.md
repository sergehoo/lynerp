# LYNEERP — Module IA (`ai_assistant`) : installation et exploitation

Ce document explique comment activer et utiliser le module IA transversal de
LYNEERP. Le module fournit un assistant métier intégré (chat global +
analyses contextuelles dans chaque module ERP) basé sur **Ollama** en local.

> ⚠️ Garde-fou central : aucune action qui modifie la base n'est effectuée
> par l'IA seule. Les actions sensibles passent par une `AIAction` qui doit
> être approuvée par un humain habilité avant exécution.

---

## 1. Architecture

```
ai_assistant/
├── models.py         # AIConversation, AIMessage, AIAction, AIToolCall, AIAuditLog…
├── services/
│   ├── ollama.py            # client HTTP Ollama (sync + streaming)
│   ├── prompt_registry.py   # prompts versionnés par module (override en DB)
│   ├── tool_registry.py     # registre d'outils métier
│   ├── context.py           # contexte tenant/user injecté dans les prompts
│   ├── audit.py             # journalisation
│   └── runner.py            # orchestration d'une conversation
├── prompts/
│   ├── general.py           # prompts par défaut
│   ├── hr.py
│   ├── finance.py
│   ├── payroll.py
│   ├── logistics.py
│   └── admin.py
├── tools/
│   ├── general_tools.py     # who_am_i, tenant_info
│   ├── hr_tools.py          # analyze_resume, interview_questions, summarize_contract
│   └── finance_tools.py     # analyze_balance, detect_anomalies, suggest_journal_entry
├── api/
│   ├── views.py             # ConversationViewSet, ActionViewSet, ToolRunView
│   ├── serializers.py
│   └── urls.py
├── views.py                 # panel chat web, liste/detail actions
├── urls.py
├── permissions.py           # CanUseAI, CanApproveAIAction, CanRunDestructiveAITool
└── executors.py             # executors d'AIAction approuvées
```

---

## 2. Installation

### 2.1 Variables d'environnement (`.env`)

```bash
# Ollama
OLLAMA_URL=http://ollama:11434          # interne Docker
OLLAMA_MODEL=qwen2.5:7b                 # modèle préféré
OLLAMA_TIMEOUT=120
OLLAMA_DEFAULT_TEMPERATURE=0.2
OLLAMA_DEFAULT_TOP_P=0.9
OLLAMA_DEFAULT_MAX_TOKENS=2048
```

### 2.2 Service Docker

Le `docker-compose.yml` inclut désormais un service `ollama` avec
auto-pull du modèle au démarrage.

```bash
docker compose pull ollama
docker compose up -d ollama
docker compose logs -f ollama       # vérifier "[ollama] Pull qwen2.5:7b..."
```

Le modèle est mis en cache dans le volume `ollama_data` (persiste entre
redémarrages).

#### GPU (optionnel)

Décommenter le bloc `deploy.resources.reservations.devices` dans
`docker-compose.yml` (section `ollama`) si vous avez une GPU NVIDIA et
le runtime nvidia-docker installé.

### 2.3 Migrations

```bash
docker compose exec rh python manage.py makemigrations ai_assistant
docker compose exec rh python manage.py migrate
```

### 2.4 Vérification

```bash
# Test direct Ollama depuis Django
docker compose exec rh python manage.py shell -c "
from ai_assistant.services.ollama import get_ollama
print('online =', get_ollama().health())
print(get_ollama().list_models())
"
```

---

## 3. Utilisation

### 3.1 Panel chat global

Le bouton flottant **LyneAI** (en bas à droite des pages HR) ouvre le panel.
URL : `/ai/`.

- Sidebar conversations à gauche.
- Sélecteur de module (général, RH, finance, paie, logistique, admin).
- Zone de chat avec rendu Markdown, streaming SSE.
- Suggestions rapides en bas.

### 3.2 Boutons IA contextuels (RH)

| Endpoint API                                    | Effet                                         |
|-------------------------------------------------|-----------------------------------------------|
| `POST /api/rh/ai/analyze-resume/`                | Extrait skills/exp/edu, score de fit         |
| `POST /api/rh/ai/interview-questions/`           | Génère 8-12 questions ciblées                |
| `POST /api/rh/ai/summarize-contract/`            | Résume un contrat (clauses critiques)        |

Exemple `curl` :

```bash
curl -X POST https://rh.lyneerp.com/api/rh/ai/analyze-resume/ \
  -H "Content-Type: application/json" \
  -H "X-Tenant-Id: <uuid>" \
  -H "Cookie: sessionid=..." \
  -d '{"application_id": "<uuid_candidature>"}'
```

Réponse :

```json
{
  "tool": "hr.analyze_resume",
  "result": {
    "data": {
      "extracted_data": {...},
      "summary": "Profil senior...",
      "fit_score": 78,
      "strengths": [...],
      "concerns": [...]
    },
    "model": "qwen2.5:7b",
    "duration_ms": 4321
  }
}
```

### 3.3 Boutons IA contextuels (Finance)

| Endpoint API                                       | Effet                                       |
|----------------------------------------------------|---------------------------------------------|
| `POST /api/finance/ai/analyze-balance/`             | Rapport Markdown sur la balance            |
| `POST /api/finance/ai/detect-anomalies/`            | Détection JSON des écritures suspectes     |
| `POST /api/finance/ai/suggest-journal-entry/`       | Crée une **AIAction PROPOSED** (validation) |

### 3.4 Workflow `AIAction`

Quand l'IA propose une écriture comptable, un employé à créer, etc., elle
crée une `AIAction` en statut **PROPOSED**. L'utilisateur doit alors :

1. Aller sur **`/ai/actions/`**.
2. Cliquer sur l'action → page de détail.
3. **Approuver** (rôles `OWNER`/`ADMIN`/`MANAGER`/`HR_BPO`) ou **Rejeter**.
4. Une fois approuvée : cliquer **Exécuter** → l'executor associé est
   appelé (ex. `finance.post_journal_entry` crée un `JournalEntry` en
   brouillon).

Les actions `requires_double_approval=True` exigent deux approbateurs
distincts.

> Le proposeur ne peut JAMAIS approuver sa propre action (séparation des
> privilèges).

---

## 4. Sécurité

| Garde-fou                                  | Implémentation                                  |
|--------------------------------------------|--------------------------------------------------|
| Isolation tenant                           | Tous modèles héritent de `TenantOwnedModel`     |
| Filtre obligatoire dans les viewsets       | `_request_tenant(request)` partout              |
| Validation humaine action sensible         | `AIAction` PROPOSED → APPROVED → EXECUTED       |
| Auto-approbation interdite                 | `CanApproveAIAction.has_object_permission`     |
| Audit trail append-only                    | `AIAuditLog` à chaque événement                |
| Masquage secrets                           | `services/context.py:redact()`                  |
| Outils destructifs bloqués via API publique | `ToolRunView` refuse `RISK_DESTRUCTIVE`        |

### Logs d'audit

Tous les événements `PROMPT_SENT`, `RESPONSE_RECEIVED`, `TOOL_CALLED`,
`ACTION_PROPOSED/APPROVED/REJECTED/EXECUTED/FAILED` et `PERMISSION_DENIED`
sont consignés dans `AIAuditLog`. Visible côté admin Django, exportable.

---

## 5. Personnalisation des prompts par tenant

Un tenant peut overrider un prompt par défaut sans toucher au code :

```python
from ai_assistant.models import AIPromptTemplate

AIPromptTemplate.objects.create(
    tenant=mon_tenant,
    name="hr.cv_analysis",
    module="hr",
    title="Prompt CV custom MaSociété",
    template="<texte personnalisé>",
    version=1,
    is_active=True,
)
```

Le `PromptRegistry` priorise l'override DB sur le prompt par défaut.

---

## 6. Tests

```bash
docker compose exec rh pytest tests/test_ai_*.py -q
```

Couvre :

- isolation tenant des conversations
- workflow AIAction (PROPOSED → APPROVED → EXECUTED)
- séparation des privilèges (auto-approbation interdite)
- audit log robuste
- registre d'outils

---

## 7. Recommandations production

- Déployer Ollama sur une **machine GPU dédiée** pour la latence.
- Utiliser un modèle **quantifié** (ex. `qwen2.5:7b-q4_K_M`) si RAM limitée.
- Augmenter `OLLAMA_KEEP_ALIVE` à `30m` ou `1h` pour éviter le rechargement
  du modèle entre requêtes.
- Activer un **rate limiting par tenant** sur `/api/ai/conversations/<id>/messages/`
  (ex. 30 req/min/user).
- Surveiller la table `AIAuditLog` (croissance) — purger ou archiver
  trimestriellement.
- En cas d'incident : `AIAction` peut être bloqué globalement en posant
  `LICENSE_ENFORCEMENT=1` + condition métier dans `executors.py`.
- **Conformité RGPD** : `AIMessage.content` peut contenir des données
  personnelles → prévoir une procédure d'effacement par utilisateur (à droit
  d'oubli appliqué).

---

## 8. Modules à venir (sessions ultérieures)

- Module **Paie** complet avec calculs déterministes (rubriques, profils,
  cotisations OHADA) + assistance IA (explication bulletin, anomalies).
- Module **Logistique / Stock / Achats** avec prévision rupture, recommandation
  réapprovisionnement.
- Module **Administration / Workflows** : assistant configuration, recommandations
  de circuits de validation.
- **Function calling natif** quand qwen2.5 supportera mieux le tool-use d'OpenAI.

Pour ces phases : référez-vous au plan détaillé dans
`docs/AUDIT_LYNEERP.md` et au backlog dans la TaskList du projet.
