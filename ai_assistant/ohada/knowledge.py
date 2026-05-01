"""
Référentiel OHADA structuré (résumés-pivots).

Chaque entrée représente un article ou un groupe d'articles avec :
- ``reference`` : identifiant canonique (ex. "AUSCGIE-Art.4").
- ``title``    : titre court.
- ``summary``  : résumé-pivot informatif.
- ``keywords`` : mots-clés pour le retrieval.
- ``related_modules`` : modules ERP qui doivent considérer l'article.

⚠️ Avertissement légal :
Les contenus sont rédigés à des fins **informatives** et ne reproduisent
pas le texte officiel de l'Acte uniforme. Toujours consulter le Journal
officiel de l'OHADA et un juriste agréé pour les décisions critiques.

Référence : Traité OHADA (Port-Louis, 1993, révisé Québec 2008) + Actes
uniformes en vigueur publiés au Journal Officiel de l'OHADA.
"""
from __future__ import annotations

# fmt: off

OHADA_KNOWLEDGE = [

    # =====================================================================
    # ACTE UNIFORME - DROIT COMMERCIAL GÉNÉRAL (DCG)
    # Adopté 17/04/1997, révisé 15/12/2010, en vigueur 16/05/2011
    # =====================================================================
    {
        "acte": "DCG",
        "reference": "DCG-Art.1-2",
        "article_number": "1-2",
        "livre": "Livre I — Statut du commerçant",
        "title": "Définition et obligations du commerçant",
        "summary": (
            "Est commerçant toute personne physique ou morale qui accomplit "
            "des actes de commerce de manière habituelle et en fait sa "
            "profession. Tout commerçant doit s'immatriculer au Registre du "
            "Commerce et du Crédit Mobilier (RCCM). L'immatriculation crée "
            "une présomption de qualité de commerçant. La radiation "
            "intervient en cas de cessation d'activité, décès ou liquidation."
        ),
        "keywords": ["commerçant", "RCCM", "immatriculation", "actes de commerce"],
        "related_modules": ["hr", "finance", "admin"],
        "related_references": ["DCG-Art.34", "DCG-Art.65"],
    },
    {
        "acte": "DCG",
        "reference": "DCG-Art.34-37",
        "article_number": "34-37",
        "livre": "Livre I — RCCM",
        "title": "Registre du Commerce et du Crédit Mobilier",
        "summary": (
            "Le RCCM est tenu par le greffe du tribunal compétent. "
            "Immatriculation obligatoire dans le mois suivant le début "
            "d'activité pour les personnes physiques ; à la constitution "
            "pour les sociétés. Mentions obligatoires : identité, activité, "
            "adresse, capital social. Modifications à déclarer dans le mois."
        ),
        "keywords": ["RCCM", "immatriculation", "greffe", "personne physique", "société"],
        "related_modules": ["finance", "admin"],
    },
    {
        "acte": "DCG",
        "reference": "DCG-Art.50-58",
        "article_number": "50-58",
        "livre": "Livre II — Comptabilité du commerçant",
        "title": "Obligations comptables du commerçant",
        "summary": (
            "Tout commerçant tient une comptabilité conforme au SYSCOHADA. "
            "Livres obligatoires : journal, grand-livre, livre d'inventaire. "
            "Conservation 10 ans. Établissement d'états financiers annuels "
            "(bilan, compte de résultat, tableau des flux, notes annexes). "
            "Obligation d'audit pour les sociétés au-delà de seuils."
        ),
        "keywords": ["comptabilité", "SYSCOHADA", "bilan", "états financiers", "audit"],
        "related_modules": ["finance", "payroll"],
        "related_references": ["SYSCOHADA-Art.1", "SYSCOHADA-Art.111"],
    },
    {
        "acte": "DCG",
        "reference": "DCG-Art.65-100",
        "article_number": "65-100",
        "livre": "Livre III — Bail à usage professionnel",
        "title": "Bail commercial — durée et renouvellement",
        "summary": (
            "Bail commercial : durée minimale variable (souvent 3 ans). "
            "Droit au renouvellement automatique si exploitation effective ≥ 2 ans. "
            "Refus de renouvellement = indemnité d'éviction (équivalente à la perte "
            "subie : valeur du fonds, frais de réinstallation). Loyer révisable "
            "tous les 3 ans. Cession libre du bail (sauf clause contraire)."
        ),
        "keywords": ["bail commercial", "renouvellement", "indemnité d'éviction", "loyer"],
        "related_modules": ["hr", "finance", "admin"],
    },
    {
        "acte": "DCG",
        "reference": "DCG-Art.106-150",
        "article_number": "106-150",
        "livre": "Livre IV — Fonds de commerce",
        "title": "Fonds de commerce — éléments et cession",
        "summary": (
            "Le fonds de commerce comprend : la clientèle, le nom commercial, "
            "l'enseigne, le droit au bail, les marchandises, le matériel, et "
            "les droits de propriété industrielle (marques, brevets). Cession "
            "ou nantissement par acte authentique ou sous seing privé enregistré. "
            "Publicité légale obligatoire (greffe + journal d'annonces). "
            "Privilège du vendeur impayé."
        ),
        "keywords": ["fonds de commerce", "cession", "nantissement", "clientèle", "privilège"],
        "related_modules": ["finance", "admin"],
        "related_references": ["SURETES-Art.158", "DCG-Art.34"],
    },
    {
        "acte": "DCG",
        "reference": "DCG-Art.169-237",
        "article_number": "169-237",
        "livre": "Livre VI — Vente commerciale",
        "title": "Vente commerciale — formation et exécution",
        "summary": (
            "Régit les ventes entre commerçants ou avec un État-membre OHADA. "
            "Formation : offre + acceptation. Effet entre les parties dès "
            "l'accord. Obligations vendeur : livraison, conformité, garantie "
            "des vices cachés. Obligations acheteur : paiement, prise de "
            "livraison. Transfert des risques à la délivrance. Délais courts "
            "pour réclamer (raisonnables). Prescription : 2 ans à compter de "
            "la livraison."
        ),
        "keywords": ["vente commerciale", "livraison", "conformité", "vices cachés", "prescription"],
        "related_modules": ["finance", "inventory"],
    },

    # =====================================================================
    # AUSCGIE — DROIT DES SOCIÉTÉS COMMERCIALES ET DU GIE
    # Adopté 17/04/1997, révisé 30/01/2014, en vigueur 05/05/2014
    # =====================================================================
    {
        "acte": "AUSCGIE",
        "reference": "AUSCGIE-Art.4-9",
        "article_number": "4-9",
        "livre": "Livre I — Dispositions générales",
        "title": "Définition de la société commerciale",
        "summary": (
            "Société = contrat ou acte unilatéral par lequel une ou plusieurs "
            "personnes affectent en commun leurs biens, leur industrie ou les "
            "deux. Personnalité juridique acquise à l'immatriculation au RCCM. "
            "Formes admises : SA, SAS, SARL, SNC, SCS, SCA, SCS-OHADA, "
            "société en participation, société de fait, GIE."
        ),
        "keywords": ["société commerciale", "personnalité juridique", "RCCM", "formes sociales"],
        "related_modules": ["admin", "finance"],
    },
    {
        "acte": "AUSCGIE",
        "reference": "AUSCGIE-Art.13-21",
        "article_number": "13-21",
        "livre": "Livre I — Statuts",
        "title": "Statuts de société — mentions obligatoires",
        "summary": (
            "Statuts par acte authentique ou sous seing privé déposé au rang "
            "des minutes d'un notaire. Mentions obligatoires : forme, "
            "dénomination, siège, durée (max 99 ans), objet, capital, "
            "apports, nombre de titres, identités des associés et dirigeants. "
            "Modification des statuts en assemblée extraordinaire majorité "
            "qualifiée (souvent 2/3)."
        ),
        "keywords": ["statuts", "siège social", "objet social", "capital", "modification"],
        "related_modules": ["admin"],
    },
    {
        "acte": "AUSCGIE",
        "reference": "AUSCGIE-Art.65-67",
        "article_number": "65-67",
        "livre": "Livre I — Capital social",
        "title": "Apports et libération du capital",
        "summary": (
            "Apports en numéraire, nature ou industrie (industrie sauf SA). "
            "Apports en nature évalués par commissaire aux apports si > seuil. "
            "Libération minimale légale du capital à la souscription : SA = 1/4, "
            "SARL = totalité ou échelonnement selon statuts. Le solde libérable "
            "dans 3 ans pour SA. Apport en industrie n'entre pas dans le capital "
            "mais donne droit à des parts d'industrie."
        ),
        "keywords": ["apport", "capital", "libération", "commissaire aux apports", "numéraire"],
        "related_modules": ["finance", "admin"],
    },
    {
        "acte": "AUSCGIE",
        "reference": "AUSCGIE-Art.124-131",
        "article_number": "124-131",
        "livre": "Livre I — Dirigeants",
        "title": "Responsabilité des dirigeants",
        "summary": (
            "Les dirigeants sont responsables individuellement ou solidairement "
            "envers la société et les tiers : violation des statuts, violation "
            "des dispositions légales ou réglementaires, fautes commises dans "
            "leur gestion. Action en responsabilité (action sociale ut singuli) "
            "ouverte aux associés. Prescription : 3 ans à compter du fait "
            "dommageable, 10 ans pour faits qualifiés crime."
        ),
        "keywords": ["dirigeants", "responsabilité", "action ut singuli", "faute de gestion"],
        "related_modules": ["admin", "hr"],
    },
    {
        "acte": "AUSCGIE",
        "reference": "AUSCGIE-Art.137-160",
        "article_number": "137-160",
        "livre": "Livre I — Comptes sociaux",
        "title": "Comptes annuels et affectation du résultat",
        "summary": (
            "Établissement annuel des états financiers (bilan, compte de résultat, "
            "tableau des flux, notes annexes) selon SYSCOHADA. Approbation par "
            "l'assemblée ordinaire dans 6 mois après clôture. Réserve légale : "
            "10 % du bénéfice net jusqu'à 20 % du capital. Distribution de "
            "dividendes uniquement sur bénéfice distribuable + réserves "
            "disponibles. Acomptes sur dividendes encadrés."
        ),
        "keywords": ["comptes annuels", "réserve légale", "dividendes", "assemblée ordinaire"],
        "related_modules": ["finance", "admin"],
        "related_references": ["SYSCOHADA-Art.111", "AUSCGIE-Art.546"],
    },
    {
        "acte": "AUSCGIE",
        "reference": "AUSCGIE-Art.200-218",
        "article_number": "200-218",
        "livre": "Livre I — Dissolution",
        "title": "Dissolution et liquidation des sociétés",
        "summary": (
            "Causes de dissolution : arrivée du terme, réalisation/extinction "
            "de l'objet, dissolution anticipée par les associés, perte de "
            "plus de la moitié du capital non régularisée, liquidation "
            "judiciaire. Liquidation amiable ou judiciaire. Liquidateur "
            "nommé. Publicité au RCCM. Boni partagé entre associés au "
            "prorata, après remboursement des apports et paiement des dettes."
        ),
        "keywords": ["dissolution", "liquidation", "boni", "liquidateur"],
        "related_modules": ["admin", "finance"],
    },
    {
        "acte": "AUSCGIE",
        "reference": "AUSCGIE-Art.309-318",
        "article_number": "309-318",
        "livre": "Livre II — SARL",
        "title": "SARL — capital, parts sociales, gérance",
        "summary": (
            "Capital minimum : 1 million FCFA (ou montant fixé par État-membre). "
            "Parts sociales nominatives, indivisibles, non négociables (cession "
            "soumise à agrément). Nombre d'associés : 1 (unipersonnelle) à 100. "
            "Gérance : 1+ gérants, associés ou non. Décisions ordinaires : "
            "majorité simple ; statutaires : majorité 3/4 des parts."
        ),
        "keywords": ["SARL", "capital minimum", "parts sociales", "gérance", "agrément"],
        "related_modules": ["admin", "finance"],
    },
    {
        "acte": "AUSCGIE",
        "reference": "AUSCGIE-Art.385-415",
        "article_number": "385-415",
        "livre": "Livre III — SA",
        "title": "Société Anonyme — capital et organes",
        "summary": (
            "Capital minimum : 10 millions FCFA (100 millions si SA avec APE). "
            "Actions nominatives ou au porteur (selon État-membre). 1 ou plus "
            "actionnaires (1 = SA unipersonnelle). Deux modes d'administration : "
            "(a) Conseil d'administration + DG, (b) Administrateur Général "
            "(petites SA). Commissaire aux comptes obligatoire dans la plupart "
            "des cas."
        ),
        "keywords": ["SA", "société anonyme", "actions", "conseil d'administration", "commissaire aux comptes"],
        "related_modules": ["admin", "finance"],
    },
    {
        "acte": "AUSCGIE",
        "reference": "AUSCGIE-Art.853-1-25",
        "article_number": "853-1 à 853-25",
        "livre": "Livre III bis — SAS",
        "title": "SAS — Société par Actions Simplifiée",
        "summary": (
            "Forme introduite par la révision de 2014. Grande liberté "
            "statutaire. 1+ associés. Capital minimum : 1 FCFA (libre). "
            "Pas de droit de vote proportionnel obligatoire. Direction par "
            "un Président obligatoire. Inadaptée à l'appel public à l'épargne. "
            "Idéale pour startups et joint-ventures."
        ),
        "keywords": ["SAS", "société par actions simplifiée", "Président", "liberté statutaire"],
        "related_modules": ["admin", "finance"],
    },
    {
        "acte": "AUSCGIE",
        "reference": "AUSCGIE-Art.546-549",
        "article_number": "546-549",
        "livre": "Livre IV — Affectation du résultat",
        "title": "Distribution de dividendes",
        "summary": (
            "Dividende = bénéfice distribuable décidé par l'assemblée ordinaire. "
            "Bénéfice distribuable = bénéfice net comptable - pertes antérieures - "
            "réserve légale - autres réserves obligatoires + report bénéficiaire. "
            "Mise en paiement dans 9 mois après clôture (sauf prorogation par "
            "tribunal). Paiement en numéraire ou en actions. Action en répétition "
            "si distribution irrégulière (3 ans)."
        ),
        "keywords": ["dividende", "bénéfice distribuable", "réserve légale", "répétition"],
        "related_modules": ["finance", "admin"],
    },
    {
        "acte": "AUSCGIE",
        "reference": "AUSCGIE-Art.869-882",
        "article_number": "869-882",
        "livre": "Livre VI — GIE",
        "title": "Groupement d'Intérêt Économique",
        "summary": (
            "Le GIE permet à des personnes physiques ou morales de mettre en "
            "commun des moyens pour faciliter ou développer leur activité, "
            "sans rechercher de bénéfices propres. Capital non obligatoire. "
            "Personnalité juridique au RCCM. Responsabilité solidaire et "
            "indéfinie des membres pour les dettes du GIE. Souvent utilisé "
            "pour mutualiser logistique, achats, recherche."
        ),
        "keywords": ["GIE", "groupement", "moyens communs", "responsabilité solidaire"],
        "related_modules": ["admin", "finance"],
    },
    {
        "acte": "AUSCGIE",
        "reference": "AUSCGIE-Art.886-905",
        "article_number": "886-905",
        "livre": "Livre VII — Pénalités",
        "title": "Infractions pénales en droit des sociétés",
        "summary": (
            "Distribution de dividendes fictifs (peines : amende + prison). "
            "Présentation de comptes inexacts. Abus de biens sociaux : "
            "utilisation des biens de la société à des fins personnelles "
            "ou pour favoriser une autre société dans laquelle on est "
            "intéressé directement ou indirectement. Délit puni dans tous "
            "les États-membres."
        ),
        "keywords": ["abus de biens sociaux", "dividendes fictifs", "pénalités", "infractions"],
        "related_modules": ["admin", "finance"],
    },

    # =====================================================================
    # AU - SÛRETÉS
    # Adopté 17/04/1997, révisé 15/12/2010, en vigueur 16/05/2011
    # =====================================================================
    {
        "acte": "SURETES",
        "reference": "SURETES-Art.4-12",
        "article_number": "4-12",
        "livre": "Titre I — Sûretés personnelles",
        "title": "Cautionnement",
        "summary": (
            "Le cautionnement est l'engagement d'une personne (caution) à "
            "exécuter l'obligation du débiteur principal en cas de défaillance. "
            "Forme écrite obligatoire avec mention manuscrite (montant en "
            "lettres et chiffres, durée). Cautionnement simple : bénéfice de "
            "discussion + division. Cautionnement solidaire : créancier peut "
            "agir directement contre la caution."
        ),
        "keywords": ["cautionnement", "caution", "solidaire", "bénéfice de discussion"],
        "related_modules": ["finance"],
    },
    {
        "acte": "SURETES",
        "reference": "SURETES-Art.39-90",
        "article_number": "39-90",
        "livre": "Titre II — Sûretés mobilières",
        "title": "Nantissement et gage",
        "summary": (
            "Gage avec dépossession (meuble corporel) ou sans dépossession "
            "(stocks, fonds de commerce, créances). Nantissement de droits "
            "mobiliers (créances, comptes bancaires, titres). Inscription au "
            "RCCM obligatoire pour opposabilité aux tiers. Réalisation : "
            "vente forcée ou attribution judiciaire. Pacte commissoire admis "
            "sauf pour le gage de stocks."
        ),
        "keywords": ["nantissement", "gage", "stocks", "créances", "RCCM"],
        "related_modules": ["finance", "inventory"],
    },
    {
        "acte": "SURETES",
        "reference": "SURETES-Art.158-170",
        "article_number": "158-170",
        "livre": "Titre II — Sûretés mobilières",
        "title": "Nantissement du fonds de commerce",
        "summary": (
            "Le fonds de commerce peut être donné en nantissement. Inscription "
            "obligatoire au RCCM. Le nantissement porte sur le droit au bail, "
            "le nom commercial, l'enseigne, la clientèle, les marques et "
            "matériels (sauf marchandises sauf inscription spécifique). "
            "Privilège pour 5 ans, renouvelable."
        ),
        "keywords": ["nantissement", "fonds de commerce", "RCCM", "privilège"],
        "related_modules": ["finance", "admin"],
    },
    {
        "acte": "SURETES",
        "reference": "SURETES-Art.190-225",
        "article_number": "190-225",
        "livre": "Titre III — Sûretés immobilières",
        "title": "Hypothèque",
        "summary": (
            "L'hypothèque est une sûreté grevant un immeuble sans dépossession. "
            "Forme authentique (acte notarié) + inscription au livre foncier. "
            "Hypothèque conventionnelle, judiciaire, légale. Rang déterminé "
            "par la date d'inscription. Réalisation : saisie immobilière, "
            "vente aux enchères. Subrogation du créancier suivant rang."
        ),
        "keywords": ["hypothèque", "immeuble", "livre foncier", "rang", "saisie"],
        "related_modules": ["finance"],
    },

    # =====================================================================
    # AU - PROCÉDURES COLLECTIVES D'APUREMENT DU PASSIF
    # Adopté 10/04/1998, révisé 10/09/2015
    # =====================================================================
    {
        "acte": "PROCED_COLL",
        "reference": "PROCED_COLL-Art.5-9",
        "article_number": "5-9",
        "livre": "Titre I — Conciliation",
        "title": "Procédure de conciliation",
        "summary": (
            "Procédure préventive ouverte aux entreprises en difficulté qui "
            "ne sont pas en cessation de paiements. Demande au tribunal qui "
            "désigne un conciliateur. Mission : favoriser l'accord avec les "
            "principaux créanciers. Durée maximale : 4 mois (+ 1 mois). "
            "Confidentielle. Aboutit à un accord homologué (force exécutoire) "
            "ou non (entre parties)."
        ),
        "keywords": ["conciliation", "préventive", "difficulté", "accord amiable"],
        "related_modules": ["finance", "admin"],
    },
    {
        "acte": "PROCED_COLL",
        "reference": "PROCED_COLL-Art.21-25",
        "article_number": "21-25",
        "livre": "Titre II — Règlement préventif",
        "title": "Règlement préventif",
        "summary": (
            "Procédure ouverte au débiteur en situation économique et financière "
            "difficile mais non en cessation de paiements. Suspension provisoire "
            "des poursuites. Concordat préventif soumis à l'assemblée des "
            "créanciers. Si homologué par le tribunal : devient obligatoire pour "
            "les créanciers. Durée d'exécution : jusqu'à 3 ans."
        ),
        "keywords": ["règlement préventif", "concordat", "suspension poursuites"],
        "related_modules": ["finance", "admin"],
    },
    {
        "acte": "PROCED_COLL",
        "reference": "PROCED_COLL-Art.25-39",
        "article_number": "25-39",
        "livre": "Titre III — Redressement judiciaire",
        "title": "Redressement judiciaire",
        "summary": (
            "Ouvert au débiteur en cessation de paiements (impossibilité de "
            "faire face au passif exigible avec son actif disponible). "
            "Déclaration obligatoire dans 30 jours. Désignation d'un syndic. "
            "Période d'observation pour évaluer la viabilité. Plan de "
            "continuation ou cession totale/partielle. Suspension des "
            "poursuites individuelles. Nullité de la période suspecte."
        ),
        "keywords": ["redressement", "cessation de paiements", "syndic", "période suspecte"],
        "related_modules": ["finance", "admin"],
    },
    {
        "acte": "PROCED_COLL",
        "reference": "PROCED_COLL-Art.33-39",
        "article_number": "33-39",
        "livre": "Titre IV — Liquidation des biens",
        "title": "Liquidation des biens",
        "summary": (
            "Procédure ouverte quand le redressement est manifestement "
            "impossible. Dissolution + vente des actifs. Désignation d'un "
            "liquidateur. Vérification des créances. Distribution selon ordre "
            "des privilèges. Cas particuliers : super-privilège des salaires "
            "(60 derniers jours), créances de la procédure, créanciers "
            "privilégiés (hypothèque, gage), créances chirographaires."
        ),
        "keywords": ["liquidation", "vérification créances", "privilèges", "super-privilège salaires"],
        "related_modules": ["finance", "payroll", "admin"],
    },
    {
        "acte": "PROCED_COLL",
        "reference": "PROCED_COLL-Art.95-105",
        "article_number": "95-105",
        "livre": "Titre VI — Période suspecte",
        "title": "Nullités de la période suspecte",
        "summary": (
            "Période suspecte = entre la date de cessation de paiements et "
            "le jugement d'ouverture (max 18 mois). Actes nuls de plein droit : "
            "actes à titre gratuit, paiements anticipés, paiements de dettes "
            "non échues, hypothèques constituées sur biens antérieurs. Actes "
            "annulables sur demande : si connaissance par le tiers de la "
            "cessation de paiements."
        ),
        "keywords": ["période suspecte", "nullités", "paiements anticipés"],
        "related_modules": ["finance", "admin"],
    },

    # =====================================================================
    # AU - PROCÉDURES SIMPLIFIÉES DE RECOUVREMENT
    # Adopté 10/04/1998
    # =====================================================================
    {
        "acte": "RECOUVREMENT",
        "reference": "RECOUVREMENT-Art.1-18",
        "article_number": "1-18",
        "livre": "Livre I — Injonction de payer",
        "title": "Injonction de payer",
        "summary": (
            "Procédure simplifiée pour le recouvrement de créance certaine, "
            "liquide et exigible (montant et date connus). Requête au "
            "président du tribunal compétent. Ordonnance d'injonction non "
            "contradictoire. Signification au débiteur qui dispose de 15 "
            "jours pour former opposition. À défaut : exécutoire. Idéal pour "
            "factures impayées documentées."
        ),
        "keywords": ["injonction de payer", "créance", "exigible", "recouvrement"],
        "related_modules": ["finance"],
    },
    {
        "acte": "RECOUVREMENT",
        "reference": "RECOUVREMENT-Art.19-27",
        "article_number": "19-27",
        "livre": "Livre I — Injonction de délivrer/restituer",
        "title": "Injonction de délivrer ou restituer",
        "summary": (
            "Pour obtenir la délivrance ou restitution d'un meuble corporel "
            "déterminé. Conditions : créance fondée sur écrit + obligation "
            "claire. Procédure rapide. Ordonnance signifiée. Opposition dans "
            "15 jours. Particulièrement utile pour récupérer marchandises "
            "non payées sous clause de réserve de propriété."
        ),
        "keywords": ["injonction délivrer", "réserve de propriété", "marchandises"],
        "related_modules": ["finance", "inventory"],
    },
    {
        "acte": "RECOUVREMENT",
        "reference": "RECOUVREMENT-Art.28-50",
        "article_number": "28-50",
        "livre": "Livre II — Voies d'exécution",
        "title": "Saisie-attribution de créances",
        "summary": (
            "Saisie d'une créance du débiteur sur un tiers (banque, employeur). "
            "Effet : attribution immédiate de la créance au profit du créancier. "
            "Acte d'huissier. Tiers saisi devient personnellement débiteur. "
            "Dénonciation au débiteur dans 8 jours. Contestation possible. "
            "Très utilisée pour la saisie de comptes bancaires."
        ),
        "keywords": ["saisie-attribution", "tiers saisi", "compte bancaire", "huissier"],
        "related_modules": ["finance", "payroll"],
    },
    {
        "acte": "RECOUVREMENT",
        "reference": "RECOUVREMENT-Art.157-180",
        "article_number": "157-180",
        "livre": "Livre II — Saisies",
        "title": "Saisie-vente de meubles",
        "summary": (
            "Saisie de biens meubles corporels appartenant au débiteur. "
            "Inventaire par huissier. Période d'inaliénabilité. Vente "
            "aux enchères publiques après publicité. Distribution du "
            "prix selon ordre des privilèges. Limitations : objets "
            "indispensables à la vie quotidienne et au travail (saisis "
            "uniquement pour le paiement de leur prix)."
        ),
        "keywords": ["saisie-vente", "enchères", "privilèges", "inventaire"],
        "related_modules": ["finance"],
    },

    # =====================================================================
    # AU - DROIT COMPTABLE ET INFORMATION FINANCIÈRE (SYSCOHADA RÉVISÉ)
    # Adopté 26/01/2017, en vigueur 01/01/2018 (entreprises) - 01/01/2019 (consolidées)
    # =====================================================================
    {
        "acte": "SYSCOHADA",
        "reference": "SYSCOHADA-Art.1-11",
        "article_number": "1-11",
        "livre": "Titre I — Champ d'application",
        "title": "Personnes assujetties au Système Comptable OHADA",
        "summary": (
            "Sont assujettis : toutes les entités exerçant à titre principal "
            "ou accessoire une activité économique sur le territoire des "
            "États-membres OHADA. Trois systèmes selon la taille : système "
            "normal, système minimal de trésorerie (SMT, micro-entreprises), "
            "système simplifié (PME). Banques, assurances, organismes à but "
            "non lucratif ont leur propre référentiel."
        ),
        "keywords": ["SYSCOHADA", "système normal", "SMT", "PME", "micro-entreprise"],
        "related_modules": ["finance"],
    },
    {
        "acte": "SYSCOHADA",
        "reference": "SYSCOHADA-Art.111",
        "article_number": "111",
        "livre": "Titre III — États financiers",
        "title": "États financiers annuels obligatoires",
        "summary": (
            "Quatre états financiers du système normal : (1) Bilan, "
            "(2) Compte de résultat, (3) Tableau des flux de trésorerie, "
            "(4) Notes annexes. Plus l'état supplémentaire IFRS pour les "
            "entités cotées. Format normalisé OHADA. Présentation comparative "
            "exercice N et N-1. Datés et signés par le représentant légal. "
            "Dépôt obligatoire au RCCM dans les 6 mois."
        ),
        "keywords": ["états financiers", "bilan", "compte de résultat", "flux de trésorerie", "notes annexes"],
        "related_modules": ["finance"],
        "related_references": ["DCG-Art.50", "AUSCGIE-Art.137"],
    },
    {
        "acte": "SYSCOHADA",
        "reference": "SYSCOHADA-Plan-Comptable",
        "article_number": "PCG",
        "livre": "Plan Comptable Général",
        "title": "Plan Comptable OHADA — Classes 1 à 9",
        "summary": (
            "Classes : 1 Comptes de ressources durables (capital, dettes "
            "long terme, réserves), 2 Actif immobilisé, 3 Stocks, 4 Tiers "
            "(clients, fournisseurs, État), 5 Trésorerie, 6 Charges par "
            "nature, 7 Produits par nature, 8 Charges/produits HAO (hors "
            "activités ordinaires), 9 Comptabilité analytique (interne)."
        ),
        "keywords": ["plan comptable", "PCG OHADA", "classes", "compte"],
        "related_modules": ["finance", "payroll"],
    },
    {
        "acte": "SYSCOHADA",
        "reference": "SYSCOHADA-Art.137",
        "article_number": "137",
        "livre": "Titre IV — Évaluation",
        "title": "Évaluation des actifs et passifs",
        "summary": (
            "Évaluation initiale : coût d'acquisition (achat) ou coût de "
            "production (interne). Coûts inclus : prix d'achat + droits "
            "non récupérables + frais directement attribuables. À la "
            "clôture : test de dépréciation si indice de perte de valeur. "
            "Stocks : CMUP ou FIFO autorisés. Dotations aux amortissements "
            "sur durée d'utilité économique."
        ),
        "keywords": ["évaluation", "coût d'acquisition", "amortissement", "CMUP", "FIFO"],
        "related_modules": ["finance", "inventory"],
    },
    {
        "acte": "SYSCOHADA",
        "reference": "SYSCOHADA-Art.143-146",
        "article_number": "143-146",
        "livre": "Titre V — Traitement spécifique",
        "title": "Charges de personnel — comptes 66 et 64",
        "summary": (
            "Compte 661 : Salaires bruts. Compte 662 : Charges sociales (CNPS "
            "patronale, mutuelle…). Compte 663 : Œuvres sociales. Compte 664 : "
            "Indemnités de fin de contrat (préavis, licenciement). Compte 665 : "
            "Autres charges de personnel. Le 421 (personnel) crédite le net à "
            "payer. Les 431/432 créditent les organismes sociaux. Le 421 "
            "(personnel acompte) débite les avances."
        ),
        "keywords": ["charges de personnel", "compte 66", "CNPS", "salaires", "421"],
        "related_modules": ["finance", "payroll"],
    },
    {
        "acte": "SYSCOHADA",
        "reference": "SYSCOHADA-Art.150-160",
        "article_number": "150-160",
        "livre": "Titre VI — Consolidation",
        "title": "Comptes consolidés",
        "summary": (
            "Obligatoires pour les entités contrôlant directement ou "
            "indirectement d'autres entités au-delà de seuils (chiffre "
            "d'affaires + total bilan + effectif). Méthodes : intégration "
            "globale (contrôle exclusif), intégration proportionnelle "
            "(contrôle conjoint), mise en équivalence (influence notable). "
            "Format normalisé OHADA. Audit obligatoire."
        ),
        "keywords": ["consolidation", "intégration globale", "mise en équivalence", "filiale"],
        "related_modules": ["finance"],
    },
    {
        "acte": "SYSCOHADA",
        "reference": "SYSCOHADA-IRPP",
        "article_number": "IRPP/ITS",
        "livre": "Référentiel - Fiscalité salariale",
        "title": "Imposition des salaires (ITS/IRPP) — barèmes",
        "summary": (
            "L'imposition des salaires varie selon l'État-membre OHADA mais "
            "suit généralement un barème progressif sur le salaire net imposable. "
            "Côte d'Ivoire (ex.) : ITS sur traitement net imposable après "
            "abattement pour frais professionnels (15-25%). Sénégal : IRPP "
            "tranches 0-40%. Cameroun : IRPP tranches 10-35%. Tous prévoient "
            "des charges familiales (parts) et déductions spécifiques."
        ),
        "keywords": ["ITS", "IRPP", "imposition salaires", "barème progressif", "abattement"],
        "related_modules": ["payroll", "finance"],
    },
    {
        "acte": "SYSCOHADA",
        "reference": "SYSCOHADA-CNPS",
        "article_number": "CNPS",
        "livre": "Référentiel - Cotisations sociales",
        "title": "CNPS — Cotisations sociales OHADA (taux indicatifs)",
        "summary": (
            "Caisse Nationale de Prévoyance Sociale — cotisations gérées par "
            "État-membre. Taux INDICATIFS (à valider par État) : Côte d'Ivoire "
            "= 6,3% salarié + 16,5% patronal (retraite, vieillesse, maladie). "
            "Sénégal = 6% salarié + 14% patronal (IPRES + CSS). Cameroun = "
            "4,2% salarié + 12,95% patronal. Plafond CNPS variable. AT (accidents "
            "du travail) supporté par employeur seul (1-5%)."
        ),
        "keywords": ["CNPS", "cotisations sociales", "retraite", "AT", "plafond"],
        "related_modules": ["payroll", "finance"],
    },

    # =====================================================================
    # AU - ARBITRAGE
    # Adopté 11/03/1999, révisé 23/11/2017
    # =====================================================================
    {
        "acte": "ARBITRAGE",
        "reference": "ARBITRAGE-Art.1-9",
        "article_number": "1-9",
        "livre": "Titre I — Convention d'arbitrage",
        "title": "Convention d'arbitrage",
        "summary": (
            "L'arbitrage règle les différends commerciaux par la décision de "
            "tribunaux arbitraux choisis par les parties. Convention par "
            "écrit (clause compromissoire dans contrat ou compromis "
            "postérieur au litige). Autonome du contrat principal. Tribunal "
            "étatique doit se déclarer incompétent si convention valable. "
            "Sentence arbitrale a autorité de chose jugée."
        ),
        "keywords": ["arbitrage", "clause compromissoire", "compromis", "sentence"],
        "related_modules": ["admin", "finance"],
    },
    {
        "acte": "ARBITRAGE",
        "reference": "ARBITRAGE-Art.30-35",
        "article_number": "30-35",
        "livre": "Titre IV — Sentence arbitrale",
        "title": "Exequatur et exécution forcée des sentences",
        "summary": (
            "Sentence arbitrale rendue par majorité. Notifiée aux parties. "
            "Pour exécution forcée : exequatur du juge étatique compétent. "
            "Refus possible uniquement pour cas limitativement énumérés "
            "(non-conformité ordre public international OHADA, défaut de "
            "convention, etc.). Sentence CCJA (Cour Commune de Justice et "
            "d'Arbitrage) directement exécutoire dans les 17 États-membres."
        ),
        "keywords": ["exequatur", "sentence", "CCJA", "ordre public", "exécution"],
        "related_modules": ["admin", "finance"],
    },

    # =====================================================================
    # AU - TRANSPORT DE MARCHANDISES PAR ROUTE
    # Adopté 22/03/2003, en vigueur 01/01/2004
    # =====================================================================
    {
        "acte": "TRANSPORT",
        "reference": "TRANSPORT-Art.4-12",
        "article_number": "4-12",
        "livre": "Chapitre I — Contrat",
        "title": "Lettre de voiture (LMR-OHADA)",
        "summary": (
            "Contrat de transport matérialisé par une lettre de voiture en "
            "trois originaux (expéditeur, transporteur, destinataire). "
            "Mentions obligatoires : identité parties, marchandises, lieu "
            "+ date de chargement, lieu prévu de livraison, prix transport. "
            "Présomption simple sur les marchandises (sauf réserves). "
            "Régit transports nationaux et internationaux entre États-membres."
        ),
        "keywords": ["lettre de voiture", "transport", "expéditeur", "transporteur"],
        "related_modules": ["inventory", "finance"],
    },
    {
        "acte": "TRANSPORT",
        "reference": "TRANSPORT-Art.16-22",
        "article_number": "16-22",
        "livre": "Chapitre III — Responsabilité",
        "title": "Responsabilité du transporteur",
        "summary": (
            "Responsabilité du transporteur pour perte totale, perte partielle "
            "ou avarie pendant la prise en charge jusqu'à la livraison. "
            "Causes d'exonération limitatives : faute de l'ayant droit, ordre "
            "de l'expéditeur, défaut propre de la marchandise, force majeure. "
            "Indemnité plafonnée à 5 000 FCFA/kg (sauf déclaration de valeur). "
            "Délai de réclamation : 7 jours pour avaries apparentes."
        ),
        "keywords": ["responsabilité", "transporteur", "perte", "avarie", "force majeure"],
        "related_modules": ["inventory", "finance"],
    },

    # =====================================================================
    # AU - SOCIÉTÉS COOPÉRATIVES
    # Adopté 15/12/2010, en vigueur 16/05/2011
    # =====================================================================
    {
        "acte": "COOPERATIVES",
        "reference": "COOPERATIVES-Art.4-15",
        "article_number": "4-15",
        "livre": "Titre I — Définition",
        "title": "Société coopérative — principes",
        "summary": (
            "Groupement autonome de personnes volontairement réunies pour "
            "satisfaire leurs aspirations économiques, sociales et culturelles "
            "communes. Principes : adhésion libre, gestion démocratique "
            "(1 personne = 1 voix), participation économique des membres, "
            "autonomie, éducation, coopération entre coopératives. Capital "
            "minimum non requis. Immatriculation au registre des coopératives."
        ),
        "keywords": ["coopérative", "1 personne 1 voix", "ristourne", "autonomie"],
        "related_modules": ["admin", "finance"],
    },
    {
        "acte": "COOPERATIVES",
        "reference": "COOPERATIVES-Art.83-95",
        "article_number": "83-95",
        "livre": "Titre III — Excédents",
        "title": "Affectation des excédents et ristournes",
        "summary": (
            "Excédent net de la coopérative = produits - charges + provisions. "
            "Affectation prioritaire : réserves obligatoires (15-20%), réserves "
            "indivisibles, fonds spéciaux. Distribution sous forme de "
            "ristournes au prorata des opérations effectuées par chaque "
            "coopérateur (et non au prorata du capital). Intérêt limité au "
            "capital."
        ),
        "keywords": ["excédent", "ristourne", "réserves indivisibles", "intérêt limité"],
        "related_modules": ["finance", "admin"],
    },

    # =====================================================================
    # AU - MÉDIATION (2017)
    # =====================================================================
    {
        "acte": "MEDIATION",
        "reference": "MEDIATION-Art.1-15",
        "article_number": "1-15",
        "livre": "Titre I — Médiation conventionnelle",
        "title": "Médiation — principes",
        "summary": (
            "Mode alternatif de règlement des différends. Le médiateur "
            "facilite la communication entre parties pour aboutir à un "
            "accord amiable. Confidentialité absolue. Volontaire et "
            "consensuelle. Suspension de la prescription pendant la médiation. "
            "Accord écrit signé par les parties + médiateur. Possibilité de "
            "demander l'exequatur pour force exécutoire."
        ),
        "keywords": ["médiation", "amiable", "confidentialité", "exequatur"],
        "related_modules": ["admin"],
    },
]
# fmt: on
