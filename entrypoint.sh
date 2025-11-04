#!/usr/bin/env bash
set -e

# Valeurs par défaut si non fournies
: "${DB_HOST:=postgres}"
: "${DB_PORT:=5432}"
: "${DJANGO_SETTINGS_MODULE:=Lyneerp.settings}"
: "${DJANGO_ENV:=dev}"
: "${BIND:=0.0.0.0:8000}"

echo "⏳ Attente de Postgres sur ${DB_HOST}:${DB_PORT} ..."
until nc -z "${DB_HOST}" "${DB_PORT}"; do
  sleep 1
done
echo "✅ Postgres OK"

# Migrations
echo "⚙️  Migrations Django"
python manage.py migrate --noinput

# Collecte des statics (décommente si nécessaire)
# echo "📦 collectstatic"
# python manage.py collectstatic --noinput

# Lancement
if [ "$DJANGO_ENV" = "prod" ]; then
  echo "🚀 Démarrage Gunicorn (prod) sur ${BIND}"
  exec gunicorn Lyneerp.wsgi:application --bind "${BIND}" --workers 3 --timeout 120
else
  echo "🚀 runserver (dev) sur ${BIND}"
  exec python manage.py runserver "${BIND}"
fi