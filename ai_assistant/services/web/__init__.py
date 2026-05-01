"""
Sous-module ``ai_assistant.services.web``.

Services de recherche web et fetch d'URL pour LyneAI :
- ``search`` : moteur de recherche pluggable (DuckDuckGo HTML, Brave, Searx).
- ``fetch``  : téléchargement d'URL + extraction de texte propre.
- ``policy`` : allowlist / blocklist / rate-limit / cache.

Garde-fous :
- Aucune requête sans timeout strict.
- Aucune URL en RFC1918 / loopback / 169.254 / file:// (SSRF protection).
- Allowlist/blocklist domaines configurables.
- Audit immédiat de chaque appel.
- Cache Redis (ou LocMem) avec TTL pour éviter les requêtes répétées.
"""
from __future__ import annotations
