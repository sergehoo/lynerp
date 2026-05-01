# LyneAI — Recherche web et fetch d'URL (deep research)

LyneAI peut désormais aller chercher des informations sur internet quand
sa base locale (ERP + OHADA + connaissance générale du modèle) ne suffit
pas. Cette extension est conçue pour rendre LYNEERP **autonome en
information** tout en restant **sûr** (SSRF, allowlist, audit, rate-limit).

## Sommaire

1. [Architecture](#1-architecture)
2. [Providers de recherche](#2-providers)
3. [Garde-fous](#3-garde-fous)
4. [Outils IA disponibles](#4-outils-ia)
5. [Endpoints API directs](#5-endpoints-api)
6. [UI : bouton de recherche profonde](#6-ui)
7. [Configuration](#7-configuration)
8. [Tests](#8-tests)
9. [Recommandations production](#9-prod)

---

## 1. Architecture

```
ai_assistant/
├── services/
│   └── web/
│       ├── policy.py    # SSRF, allowlist/blocklist, rate-limit, clean_url
│       ├── search.py    # dispatcher providers (ddg / brave / searx)
│       ├── fetch.py     # téléchargement URL + extraction texte
│       └── research.py  # pipeline deep research (search → fetch → synthèse Ollama)
├── tools/
│   └── web_tools.py     # outils @registry.tool : web.search, web.fetch, web.research
├── api/
│   └── web_views.py     # endpoints DRF directs : /api/ai/web/*
└── models.py
    └── WebFetchAudit    # journal de toutes les requêtes web
```

## 2. Providers

| Provider | Configuration | Avantages | Limites |
|----------|--------------|-----------|---------|
| `ddg`    | aucune (par défaut) | gratuit, pas de clé API | scraping HTML, peut casser sur changement DDG |
| `brave`  | `BRAVE_API_KEY=...` | API officielle, stable | quota mensuel selon plan |
| `searx`  | `SEARX_URL=...`     | auto-hébergé, contrôle total | nécessite déployer SearxNG |

Le provider est sélectionnable :

- globalement via `WEB_SEARCH_PROVIDER` (env)
- ponctuellement via le paramètre `provider` des outils.

## 3. Garde-fous

### SSRF (Server-Side Request Forgery)

`policy.ssrf_safe(url)` rejette automatiquement :

- les schémas non-HTTP/HTTPS (`file://`, `gopher://`, etc.)
- les hostnames `localhost`, `0`, `broadcasthost`
- les adresses IP privées RFC1918 (`10.0.0.0/8`, `172.16/12`, `192.168/16`)
- la loopback (`127.0.0.0/8`, `::1`)
- le link-local (`169.254/16`, `fe80::/10`)
- les ULAs IPv6 (`fc00::/7`)
- les hostnames dont la résolution DNS pointe vers une IP privée

Cette protection s'applique avant toute requête HTTP.

### Allowlist / Blocklist

Variables d'env :

- `WEB_ALLOWLIST=domaine1.com,domaine2.com` → si non vide, **seuls** ces domaines passent.
- `WEB_BLOCKLIST=facebook.com,instagram.com,tiktok.com` → toujours bloqués.

Match par suffixe : `example.com` couvre aussi `foo.example.com`.

### Rate-limit par tenant

- **Recherche** : 30 appels / 60 secondes / tenant.
- **Fetch URL** : 60 appels / 60 secondes / tenant.

Implémenté via cache Redis (LocMem en fallback). Configurable.

### Limite de taille

- `WEB_FETCH_MAX_BYTES` (défaut : 2 Mo) → pas de téléchargement de fichiers
  massifs.
- Refus automatique des binaires non-HTML (PDF, images, archives).

### Cache

- Recherche : TTL 30 min (`WEB_SEARCH_CACHE_TTL`).
- Fetch URL : TTL 6h (`WEB_FETCH_CACHE_TTL`).

Cache Redis si configuré, sinon LocMem.

### Audit

Modèle `WebFetchAudit` : chaque appel (search / fetch / research) est
journalisé avec tenant, user, action, target, succès, détails. Visible
dans l'admin Django.

### Cleansing URL

`policy.clean_url(url)` retire automatiquement les paramètres de tracking
(`utm_*`, `fbclid`, `gclid`, etc.) avant fetch.

## 4. Outils IA

### `web.search`

```python
search(query="taux IRPP Côte d'Ivoire 2026", locale="fr-fr", limit=8)
# → {"provider": "ddg", "results": [{"title", "url", "snippet"}, ...]}
```

### `web.fetch`

```python
fetch(url="https://example.com/article", max_chars=8000)
# → {"url", "title", "text", "char_count", "duration_ms", "cached"}
```

### `web.research`

Pipeline deep research : combine search + fetch des N premiers résultats
+ synthèse Ollama avec citations.

```python
research(question="Quel est le taux de TVA en vigueur au Sénégal en 2026 ?",
         locale="fr-fr", pages=3)
# → {
#     "question": "...",
#     "sources": [{"index": 1, "title": "...", "url": "...", "snippet": "..."}, ...],
#     "synthesis_markdown": "...",
#     "model": "qwen2.5:7b",
#     "duration_ms": 4500,
#     "provider": "ddg"
# }
```

LyneAI est instruit (via `general.system`) d'utiliser `web.research` en
fallback dès qu'il manque d'information locale.

## 5. Endpoints API

Pour des intégrations externes ou des tests directs :

| Endpoint                               | Body                                       |
|----------------------------------------|--------------------------------------------|
| `POST /api/ai/web/search/`              | `{query, locale?, limit?, provider?}`     |
| `POST /api/ai/web/fetch/`               | `{url, max_chars?}`                        |
| `POST /api/ai/web/research/`            | `{question, locale?, pages?, provider?}`   |
| `POST /api/ai/tools/web.search/run/`    | (générique tool runner)                    |
| `POST /api/ai/tools/web.research/run/`  | (générique tool runner)                    |

Permission : `IsAuthenticated + CanUseAI` (membre actif d'un tenant).

Exemple `curl` :

```bash
curl -X POST https://rh.lyneerp.com/api/ai/web/research/ \
  -H "Content-Type: application/json" \
  -H "X-CSRFToken: ..." \
  -H "X-Tenant-Id: <uuid>" \
  -b "sessionid=..." \
  -d '{"question": "Taux CNPS Côte d Ivoire 2026", "pages": 3}'
```

## 6. UI

Le panel chat IA (`/ai/`) affiche désormais :

- une **barre de recherche profonde** dédiée au-dessus du composer
  (icône globe, déclenchée par Entrée ou clic),
- les **sources web** sous chaque réponse provenant d'une recherche
  profonde, avec numéro [1], [2]… cliquables vers les URLs.

## 7. Configuration

### `.env` minimal (DuckDuckGo, zéro config)

```bash
# Aucune variable n'est strictement requise. Defaults =
# WEB_SEARCH_PROVIDER=ddg
# WEB_BLOCKLIST=facebook.com,instagram.com,tiktok.com
```

### `.env` recommandé (Brave Search)

```bash
WEB_SEARCH_PROVIDER=brave
BRAVE_API_KEY=BSA_xxx_yyy           # https://brave.com/search/api/
WEB_FETCH_MAX_BYTES=2097152          # 2 Mo
WEB_SEARCH_CACHE_TTL=1800            # 30 min
WEB_FETCH_CACHE_TTL=21600            # 6 h
WEB_ALLOWLIST=                        # vide = ouvert
WEB_BLOCKLIST=facebook.com,instagram.com,tiktok.com
```

### `.env` SearxNG auto-hébergé

```bash
WEB_SEARCH_PROVIDER=searx
SEARX_URL=https://searx.intranet.lyneerp.com
```

### Dépendances Python recommandées

- `requests` (déjà présent)
- `beautifulsoup4` (déjà via finance / weasyprint indirectement)
- `trafilatura` (optionnel, recommandé pour une extraction texte propre)

Pour installer trafilatura :

```bash
pip install trafilatura
```

Si `trafilatura` n'est pas installé, le service tombe en fallback sur
BeautifulSoup, puis sur regex. La qualité d'extraction varie en
conséquence.

## 8. Tests

```bash
docker compose exec rh pytest \
    tests/test_web_policy.py \
    tests/test_web_search_provider.py \
    tests/test_web_fetch.py -q
```

Couvre :

- protection SSRF (IP privées, localhost, schémas exotiques)
- allowlist / blocklist
- nettoyage URL (utm, fbclid)
- parsing du HTML DuckDuckGo
- exigence de clé pour Brave / SearxNG
- extraction de texte HTML
- refus des binaires (PDF, etc.)

## 9. Recommandations production

- **Provider** : préférer Brave Search (officiel, stable) ou SearxNG
  auto-hébergé. DDG HTML est un bon défaut, mais peut casser si la
  structure HTML évolue.
- **Cache** : utiliser **Redis** plutôt que LocMem pour partager entre
  Gunicorn workers.
- **Quotas tenant** : si vous facturez à l'usage, exposer un quota
  mensuel par tenant (à brancher sur `policy.rate_limit_ok`).
- **Allowlist en environnement régulé** : pour des secteurs sensibles
  (santé, défense), définir `WEB_ALLOWLIST` à une liste fermée de
  domaines de confiance.
- **Audit RGPD** : le contenu textuel récupéré peut contenir des données
  personnelles. Prévoir une politique d'expiration (`WebFetchAudit`).
- **Robots.txt** : LyneAI respecte les User-Agent identifiables. Pour
  scraper agressivement, utiliser `WEB_SEARCH_USER_AGENT` cohérent et
  surveiller les blocages de votre IP par les sites cibles.
- **Disclaimer utilisateur** : rappeler que les informations web
  peuvent être inexactes ou obsolètes — toujours vérifier les sources
  citées.

---

## Cas d'usage typiques

- **Taux fiscaux nationaux** : "Quel est le taux d'IRPP en vigueur au
  Sénégal en 2026 ?"
- **Jurisprudence récente** : "Cherche la jurisprudence CCJA récente sur
  la responsabilité du gérant de SARL."
- **Veille concurrentielle** : "Compare les fonctionnalités d'Odoo et de
  Sage Business Cloud Comptabilité."
- **Conformité documentaire** : "Quels sont les modèles de contrat de
  travail conformes au code du travail Camerounais ?"
- **Données macro-économiques** : "Quel est le taux d'inflation prévu
  pour la zone UEMOA en 2026 ?"

Pour chaque cas, LyneAI exécute `web.research`, fetche 3 pages au-dessus
de la barre, synthétise et cite ses sources [1] [2] [3].
