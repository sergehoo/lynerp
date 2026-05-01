"""
Prompts système par module ERP.

Chaque module exporte un dict ``PROMPTS = {"<module>.<nom>": "<texte>"}``.
Le ``PromptRegistry`` charge automatiquement le module à partir du nom.
"""
