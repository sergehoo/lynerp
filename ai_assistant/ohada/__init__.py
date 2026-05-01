"""
Sous-module ``ai_assistant.ohada``.

Base de connaissances structurée sur le droit OHADA (Organisation pour
l'Harmonisation en Afrique du Droit des Affaires) :

- 17 États-membres (Bénin, Burkina Faso, Cameroun, Centrafrique, Comores,
  Congo, Côte d'Ivoire, Gabon, Guinée, Guinée-Bissau, Guinée Équatoriale,
  Mali, Niger, RDC, Sénégal, Tchad, Togo).
- 9 Actes uniformes en vigueur (au moment du seed).

⚠️ Avertissement légal : les contenus stockés sont des **résumés-pivots**
à valeur informative. Ils ne se substituent pas à la consultation d'un
juriste OHADA agréé ni à la lecture des textes officiels.

Ressources :
- ``knowledge.py`` : référentiel structuré (constantes Python).
- ``retrieval.py`` : moteur de recherche full-text simple sur OHADAArticle.
- ``prompts.py`` : prompts juridiques OHADA injectés dans le runner IA.
"""
