"""
Module Logistique / Stock / Achats LYNEERP.

Couvre :
- articles, catégories, entrepôts ;
- mouvements de stock (entrées/sorties/transferts) ;
- inventaires physiques ;
- fournisseurs, bons de commande, réceptions ;
- alertes de réapprovisionnement.

Le module IA fournit : prévision rupture, recommandation réapprovisionnement,
analyse fournisseurs.
"""

default_app_config = "inventory.apps.InventoryConfig"
