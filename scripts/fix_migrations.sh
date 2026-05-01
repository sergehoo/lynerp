#!/usr/bin/env bash
# ============================================================================
# fix_migrations.sh — Génère et applique TOUTES les migrations LYNEERP
#
# À exécuter UNE FOIS après avoir cloné/mis à jour le projet, avant
# de tester l'application.
#
#   • En local (venv) :   ./scripts/fix_migrations.sh
#   • Dans Docker      :   docker compose exec web ./scripts/fix_migrations.sh
# ============================================================================
set -euo pipefail

# Couleurs (si terminal supporté)
if [[ -t 1 ]]; then
    GREEN=$'\033[0;32m'; YELLOW=$'\033[0;33m'; RESET=$'\033[0m'
else
    GREEN=""; YELLOW=""; RESET=""
fi

PYTHON="${PYTHON_BIN:-python}"
MANAGE="$PYTHON manage.py"

APPS=(
    tenants
    hr
    finance
    ai_assistant
    payroll
    inventory
    workflows
    crm
    projects
    reporting
    ocr
)

echo "${YELLOW}▶ Génération des migrations LYNEERP…${RESET}"
$MANAGE makemigrations "${APPS[@]}"

echo
echo "${YELLOW}▶ Application des migrations (incluant Django core)…${RESET}"
$MANAGE migrate

echo
echo "${GREEN}✓ Base de données à jour. Vous pouvez relancer le serveur.${RESET}"
echo
echo "Étapes recommandées ensuite :"
echo "  1. ${YELLOW}$MANAGE seed_ohada${RESET}    # 46 articles OHADA"
echo "  2. ${YELLOW}$MANAGE collectstatic --noinput${RESET}  # si prod"
echo "  3. Recharger /ai/ dans le navigateur."
