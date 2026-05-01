"""
Vue générique Placeholder pour les modules en cours de construction.

Permet à toutes les routes "orphelines" (qui figurent dans la sidebar mais
qui n'ont pas encore de vue dédiée) de rendre une page propre et cohérente
plutôt qu'un 404.

Chaque entrée du registre PLACEHOLDER_PAGES définit :
- ``title``       : titre principal
- ``icon``        : classe FontAwesome (ex. "fa-solid fa-truck")
- ``color``       : palette d'accent (Tailwind, ex. "indigo")
- ``description`` : texte court visible
- ``next_steps``  : liste de bullets indiquant ce qui sera disponible
- ``related``     : liens utiles (ex. doc, page connexe)
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404, HttpRequest, HttpResponse
from django.views.generic import TemplateView


PLACEHOLDER_PAGES: Dict[str, Dict[str, Any]] = {
    # =================================================================== #
    # CORE
    # =================================================================== #
    "core.tasks": {
        "title": "Tâches & rappels",
        "icon": "fa-solid fa-list-check",
        "color": "indigo",
        "description": (
            "Centralisez vos tâches personnelles et celles de vos équipes : "
            "rappels d'échéances, actions à valider, suivi quotidien."
        ),
        "next_steps": [
            "Création d'une tâche depuis n'importe quel module (RH, Finance, Stock).",
            "Synchronisation avec les jalons de projets et les approbations.",
            "Notifications sur échéance dépassée.",
        ],
        "related": [
            ("Approbations en attente", "/workflows/requests/"),
            ("Notifications", "/workflows/notifications/"),
        ],
    },
    "core.documents": {
        "title": "GED — Documents",
        "icon": "fa-solid fa-folder-open",
        "color": "amber",
        "description": (
            "Gestion électronique de documents : contrats, factures scannées, "
            "procédures internes, archives RH. Tous chiffrés et tagués par tenant."
        ),
        "next_steps": [
            "Upload de documents avec extraction OCR automatique.",
            "Classement par dossier et étiquetage par compétence métier.",
            "Recherche full-text (Postgres) avec respect strict du périmètre tenant.",
            "Versionnage et signature électronique.",
        ],
        "related": [
            ("OCR factures fournisseurs", "/ocr/"),
            ("Documents RH", "/hr/employees/"),
        ],
    },
    "core.audit": {
        "title": "Journal & audit système",
        "icon": "fa-solid fa-shield-halved",
        "color": "slate",
        "description": "Vue consolidée des événements d'audit cross-modules.",
        "next_steps": [
            "Filtres avancés par module / sévérité / acteur.",
            "Export CSV / PDF pour audits externes.",
            "Alertes temps réel sur événements critiques.",
        ],
        "related": [
            ("Audit transversal", "/workflows/audit/"),
            ("Audit IA", "/admin/ai_assistant/aiauditlog/"),
        ],
    },

    # =================================================================== #
    # HR
    # =================================================================== #
    "hr.performance": {
        "title": "Évaluations de performance",
        "icon": "fa-solid fa-star",
        "color": "emerald",
        "description": (
            "Cycles d'évaluation 360°, fixation d'objectifs (OKR / SMART), "
            "feedbacks continus, plan de carrière."
        ),
        "next_steps": [
            "Templates d'entretien annuel paramétrables par tenant.",
            "Auto-évaluation collaborateur + évaluation manager.",
            "IA : génération de questions ciblées et synthèse rapport.",
        ],
        "related": [
            ("Employés", "/hr/employees/"),
            ("Recrutement", "/hr/recruitment/"),
        ],
    },
    "hr.training": {
        "title": "Formations",
        "icon": "fa-solid fa-graduation-cap",
        "color": "emerald",
        "description": (
            "Catalogue de formations, planification, présences, certificats. "
            "Compatible avec les obligations légales OHADA (ex. 1% formation)."
        ),
        "next_steps": [
            "Catalogue formations internes / externes.",
            "Inscription, présences, validation des acquis.",
            "Reporting fiscal (1 % formation).",
        ],
        "related": [
            ("Employés", "/hr/employees/"),
            ("Performance", "/hr/performance/"),
        ],
    },

    # =================================================================== #
    # SALES (CRM)
    # =================================================================== #
    "sales.sales_orders": {
        "title": "Commandes clients",
        "icon": "fa-solid fa-cart-shopping",
        "color": "pink",
        "description": (
            "Bons de commande clients (sales orders) avec validation et "
            "déclenchement de la livraison."
        ),
        "next_steps": [
            "Conversion d'un devis (Quote) accepté en commande.",
            "Transfert automatique vers le module Stock pour réservation.",
            "Génération de facture finale à la livraison.",
        ],
        "related": [
            ("Devis Finance", "/finance/quotes/"),
            ("Opportunités CRM", "/crm/opportunities/"),
        ],
    },
    "sales.customer_support": {
        "title": "Support client",
        "icon": "fa-solid fa-headset",
        "color": "pink",
        "description": (
            "Tickets, SLA, base de connaissances client, chat support."
        ),
        "next_steps": [
            "Tickets avec niveaux de priorité et SLA configurables.",
            "Intégration LyneAI pour réponses suggérées.",
            "Base de connaissances publique par tenant.",
        ],
        "related": [
            ("Comptes CRM", "/crm/"),
        ],
    },

    # =================================================================== #
    # OPS / Stock
    # =================================================================== #
    "ops.inventory_counts": {
        "title": "Inventaires physiques",
        "icon": "fa-solid fa-clipboard-check",
        "color": "amber",
        "description": (
            "Lancement de campagnes d'inventaire physique, écarts entre "
            "stock théorique et constaté, ajustements automatiques."
        ),
        "next_steps": [
            "Génération de listes d'inventaire par entrepôt / catégorie.",
            "Saisie mobile (lecture code-barres / QR).",
            "Ajustements de stock validés par AIAction.",
        ],
        "related": [
            ("Stock courant", "/inventory/"),
            ("Articles", "/inventory/articles/"),
        ],
    },
    "ops.shipments": {
        "title": "Expéditions",
        "icon": "fa-solid fa-truck-fast",
        "color": "amber",
        "description": (
            "Bons d'expédition, lettres de voiture (LMR-OHADA), suivi "
            "transporteur, accusés de livraison."
        ),
        "next_steps": [
            "Génération automatique de la lettre de voiture OHADA.",
            "Suivi multi-transporteurs.",
            "Notification client à chaque étape.",
        ],
        "related": [
            ("Stock", "/inventory/"),
            ("Tracking colis", "/ops/tracking/"),
        ],
    },
    "ops.tracking": {
        "title": "Tracking colis",
        "icon": "fa-solid fa-location-crosshairs",
        "color": "amber",
        "description": "Suivi temps réel des envois (GPS, transporteurs partenaires).",
        "next_steps": [
            "Connecteurs DHL / UPS / La Poste / acteurs locaux OHADA.",
            "Webhook de mise à jour statut.",
            "Carte temps réel dans le dashboard.",
        ],
        "related": [
            ("Expéditions", "/ops/shipments/"),
        ],
    },
    "ops.purchase_orders": {
        "title": "Bons de commande fournisseurs",
        "icon": "fa-solid fa-file-invoice",
        "color": "amber",
        "description": "Workflow d'approvisionnement complet, du brouillon à la réception.",
        "next_steps": [
            "Création depuis IA (recommandation de réapprovisionnement).",
            "Approbation multi-niveaux (workflow PO_APPROVAL).",
            "Réception partielle / totale + génération bon de réception.",
        ],
        "related": [
            ("Stock", "/inventory/"),
            ("Workflows", "/workflows/requests/"),
        ],
    },

    # =================================================================== #
    # PROJECTS
    # =================================================================== #
    "projects.kanban": {
        "title": "Vue Kanban",
        "icon": "fa-solid fa-table-columns",
        "color": "cyan",
        "description": (
            "Visualisation en colonnes des tâches d'un projet (To do / In progress / Review / Done). "
            "Drag-and-drop pour changer de statut."
        ),
        "next_steps": [
            "Drag-and-drop entre colonnes (mise à jour status sync).",
            "Filtres par assigné / priorité / tag.",
            "Indicateurs charge / capacité par membre.",
        ],
        "related": [
            ("Liste projets", "/projects/list/"),
        ],
    },
    "projects.gantt": {
        "title": "Diagramme de Gantt",
        "icon": "fa-solid fa-chart-gantt",
        "color": "cyan",
        "description": (
            "Planning visuel avec dépendances, jalons, chemin critique. "
            "Export PDF pour comités de pilotage."
        ),
        "next_steps": [
            "Édition graphique des dates par drag.",
            "Détection automatique du chemin critique.",
            "Synchronisation avec calendriers Outlook / Google.",
        ],
        "related": [
            ("Projets", "/projects/"),
        ],
    },
    "projects.project_costs": {
        "title": "Coûts projet",
        "icon": "fa-solid fa-sack-dollar",
        "color": "cyan",
        "description": (
            "Suivi budget vs réalisé : main d'œuvre (depuis time-tracking), "
            "achats imputés, marges. Données cross-modules Finance / Paie."
        ),
        "next_steps": [
            "Imputation automatique des achats Stock sur projet.",
            "Calcul de marge brute / nette par projet.",
            "Alertes dépassement budget (workflow validation).",
        ],
        "related": [
            ("Time tracking", "/projects/"),
            ("Finance", "/finance/"),
        ],
    },

    # =================================================================== #
    # BI
    # =================================================================== #
    "bi.reports": {
        "title": "Rapports",
        "icon": "fa-solid fa-file-lines",
        "color": "violet",
        "description": "Bibliothèque de rapports paramétrables (PDF, Excel).",
        "next_steps": [
            "Builder visuel de rapports (drag-and-drop).",
            "Planification d'envoi automatique par email.",
            "Templates standards SYSCOHADA inclus.",
        ],
        "related": [
            ("KPI", "/reporting/"),
        ],
    },
    "bi.exports": {
        "title": "Exports",
        "icon": "fa-solid fa-file-export",
        "color": "violet",
        "description": "Centre d'exports cross-modules (CSV, Excel, OFX, FEC).",
        "next_steps": [
            "Export FEC fiscal pour contrôles administration.",
            "Export OFX pour banques partenaires.",
            "Export Excel paramétrable de tout queryset DRF.",
        ],
        "related": [
            ("Reporting", "/reporting/"),
        ],
    },
    "bi.data_quality": {
        "title": "Qualité des données",
        "icon": "fa-solid fa-check-double",
        "color": "violet",
        "description": (
            "Détection automatique des incohérences (doublons, champs vides, "
            "écritures non équilibrées, périodes ouvertes…)."
        ),
        "next_steps": [
            "Règles de qualité paramétrables par tenant.",
            "Score de qualité par module.",
            "Suggestions de correction par LyneAI.",
        ],
        "related": [
            ("Audit", "/workflows/audit/"),
        ],
    },

    # =================================================================== #
    # ADMIN
    # =================================================================== #
    "admin.tenants": {
        "title": "Organisations (Tenants)",
        "icon": "fa-solid fa-building",
        "color": "slate",
        "description": (
            "Liste des organisations clientes (multi-tenant). Gestion des "
            "abonnements, plans, utilisateurs actifs."
        ),
        "next_steps": [
            "Vue admin global (super-administrateur LYNEERP).",
            "Création d'un tenant + provisionnement automatique des seeds.",
            "Suspension / réactivation par licence.",
        ],
        "related": [
            ("Admin Django", "/admin/tenants/tenant/"),
        ],
    },
    "admin.users_roles": {
        "title": "Utilisateurs & Rôles",
        "icon": "fa-solid fa-users-gear",
        "color": "slate",
        "description": (
            "Gestion des comptes utilisateurs et de leurs rôles dans "
            "l'organisation courante (OWNER / ADMIN / MANAGER / MEMBER / VIEWER)."
        ),
        "next_steps": [
            "Invitation par email avec rôle pré-défini.",
            "Bulk-import CSV.",
            "Audit des changements de rôle.",
        ],
        "related": [
            ("Permissions", "/admin/permissions/"),
            ("Admin Django", "/admin/auth/user/"),
        ],
    },
    "admin.permissions": {
        "title": "Permissions",
        "icon": "fa-solid fa-user-shield",
        "color": "slate",
        "description": (
            "Matrice fine des permissions par rôle et par module. "
            "Prédéfinis OHADA / RGPD inclus."
        ),
        "next_steps": [
            "Permissions par module (RH / Finance / Paie...) et par action.",
            "Templates pré-configurés (rôles métier standards).",
            "Test d'accès en simulation utilisateur.",
        ],
        "related": [
            ("Utilisateurs & rôles", "/admin/users-roles/"),
        ],
    },
    "admin.license": {
        "title": "Licences & abonnements",
        "icon": "fa-solid fa-receipt",
        "color": "slate",
        "description": (
            "Plan d'abonnement actuel, sièges utilisés, licences par module, "
            "facturation et historique de paiements."
        ),
        "next_steps": [
            "Affichage du plan + nombre de sièges consommés.",
            "Auto-attribution de siège (JIT) à la première connexion.",
            "Lien vers le portail de facturation Stripe / mobile money.",
        ],
        "related": [
            ("Statut licence", "/api/license/status/"),
        ],
    },
    "admin.logs": {
        "title": "Logs système",
        "icon": "fa-solid fa-scroll",
        "color": "slate",
        "description": "Journaux applicatifs filtrés par sévérité, module, période.",
        "next_steps": [
            "Streaming temps réel des logs par tenant.",
            "Filtres par niveau (DEBUG / INFO / WARNING / ERROR).",
            "Export pour analyse externe (ELK / Grafana).",
        ],
        "related": [
            ("Audit", "/workflows/audit/"),
        ],
    },
    "admin.settings": {
        "title": "Paramètres de l'organisation",
        "icon": "fa-solid fa-sliders",
        "color": "slate",
        "description": (
            "Configuration générale : devise, fuseau, identité légale, "
            "logos pour documents, adresses fiscales, mentions légales."
        ),
        "next_steps": [
            "Branding documents (logo, signature, footer).",
            "Configuration fiscale par défaut.",
            "Politique de mots de passe / 2FA.",
            "Connecteurs externes (Stripe, MailJet, MinIO).",
        ],
        "related": [
            ("Profil tenant", "/admin/tenants/tenant/"),
        ],
    },
}


def get_placeholder(key: str) -> Optional[Dict[str, Any]]:
    """Retourne la config de la page Placeholder par clé."""
    return PLACEHOLDER_PAGES.get(key)


def list_placeholders() -> List[str]:
    return sorted(PLACEHOLDER_PAGES.keys())


class PlaceholderView(LoginRequiredMixin, TemplateView):
    """
    Vue qui rend ``templates/lyneerp/placeholder.html`` avec un contexte
    spécifique selon la clé passée en argument d'URL.

    Usage URL :

        path("hr/performance/", PlaceholderView.as_view(key="hr.performance")),
    """

    template_name = "lyneerp/placeholder.html"
    key: str = ""

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        spec = get_placeholder(self.key)
        if spec is None:
            raise Http404(f"Placeholder '{self.key}' inconnu.")
        ctx.update(spec)
        ctx["placeholder_key"] = self.key
        return ctx
