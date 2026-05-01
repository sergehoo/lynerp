# Module IA — Connaissance OHADA intégrée

LyneAI dispose d'une base de connaissances structurée du droit OHADA
intégrée au modèle ``ai_assistant.OHADAArticle``. Elle alimente :

- l'outil IA ``ohada.search`` (recherche full-text),
- l'outil IA ``ohada.cite`` (référence canonique),
- l'outil IA ``ohada.compliance_check`` (vérification de conformité),
- l'enrichissement automatique des prompts métier (RH, Finance, Paie).

## États-membres OHADA (17)

Bénin · Burkina Faso · Cameroun · République Centrafricaine · Comores ·
Congo-Brazzaville · Côte d'Ivoire · Gabon · Guinée · Guinée-Bissau ·
Guinée Équatoriale · Mali · Niger · République Démocratique du Congo ·
Sénégal · Tchad · Togo.

## Actes uniformes couverts (10)

| Code           | Acte uniforme                                                          |
|----------------|-----------------------------------------------------------------------|
| `DCG`          | Droit Commercial Général (1997, révisé 2010)                          |
| `AUSCGIE`      | Sociétés Commerciales et Groupement d'Intérêt Économique (rév. 2014)  |
| `SURETES`      | Sûretés (rév. 2010)                                                   |
| `PROCED_COLL`  | Procédures Collectives d'apurement du passif (rév. 2015)              |
| `RECOUVREMENT` | Procédures Simplifiées de Recouvrement et Voies d'Exécution           |
| `SYSCOHADA`    | Droit Comptable et Information Financière — SYSCOHADA révisé 2017     |
| `ARBITRAGE`    | Arbitrage (rév. 2017)                                                 |
| `TRANSPORT`    | Transport de Marchandises par Route                                   |
| `COOPERATIVES` | Sociétés Coopératives                                                 |
| `MEDIATION`    | Médiation (2017)                                                      |

## Articles seedés (extraits pivots)

Le seed contient les articles-clés de chaque Acte (~ 35 entrées initiales,
extensibles). Chaque article contient :

- ``reference`` : identifiant canonique (ex. `AUSCGIE-Art.4-9`).
- ``title`` : titre court.
- ``summary`` : résumé pivot (3-10 lignes).
- ``keywords`` : mots-clés pour le retrieval.
- ``related_modules`` : modules ERP qui doivent considérer l'article
  (`hr`, `payroll`, `finance`, `inventory`, `admin`).

## Initialisation

```bash
# Charger la base de connaissances OHADA (référentiel global, pas par tenant)
docker compose exec rh python manage.py seed_ohada

# Reseed propre (purge avant)
docker compose exec rh python manage.py seed_ohada --reset
```

## Utilisation côté IA

### 1. Outil de recherche directe

```bash
POST /api/ai/tools/ohada.search/run/
{
  "query": "renouvellement bail commercial",
  "actes": ["DCG"],            // optionnel
  "modules": ["finance"],       // optionnel
  "limit": 8
}
```

### 2. Citation par référence

```bash
POST /api/ai/tools/ohada.cite/run/
{"reference": "AUSCGIE-Art.4-9"}
```

### 3. Vérification de conformité contextuelle

```bash
POST /api/ai/tools/ohada.compliance_check/run/
{
  "context": "Notre société souhaite émettre un bon de commande de 50M XOF...",
  "country": "Côte d'Ivoire",
  "modules": ["finance", "inventory"]
}
```

### 4. Dans le chat IA

Sélectionner le module **"Administration"** dans le panel `/ai/` puis
demander : *"Quels sont les seuils pour rendre obligatoire la nomination
d'un commissaire aux comptes en SA ?"*. LyneAI interroge automatiquement
``ohada.search`` et cite les références ``AUSCGIE-Art.385-415``.

### 5. Enrichissement automatique des prompts métier

Les prompts ``hr.system``, ``finance.system``, ``payroll.system`` ont été
enrichis pour citer les Actes uniformes pertinents et inviter LyneAI à
utiliser ``ohada.search`` quand une question juridique précise se pose.

## Annotations privées par tenant

Chaque tenant peut ajouter ses propres mémos / jurisprudence locale via
``OHADANote`` (ForeignKey vers ``OHADAArticle``). Ces notes sont privées
au tenant et n'influencent pas le retrieval global.

## Avertissement légal

Les contenus stockés sont des **résumés-pivots** à valeur informative.
Ils :

1. Ne reproduisent pas le texte officiel des Actes uniformes (consulter
   le Journal Officiel de l'OHADA pour la version intégrale).
2. Ne se substituent pas à la consultation d'un juriste OHADA agréé.
3. Restent indicatifs sur les taux de cotisations et barèmes fiscaux —
   à valider auprès des autorités nationales (CNPS, DGI, etc.).

LyneAI termine systématiquement ses réponses juridiques par un rappel
de cet avertissement.

## Extension du référentiel

Pour ajouter de nouveaux articles :

1. Éditer `ai_assistant/ohada/knowledge.py` (ajouter une entrée à
   `OHADA_KNOWLEDGE`).
2. Relancer `python manage.py seed_ohada` (idempotent).

Pour des cas critiques, vous pouvez aussi insérer directement en DB
via l'admin Django (`/admin/ai_assistant/ohadaarticle/`).
