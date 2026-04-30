#!/usr/bin/env bash
# =============================================================================
# Entrypoint Docker LYNEERP.
# - Attend la disponibilité de Postgres (et Redis si défini)
# - Applique les migrations
# - En prod : `collectstatic` + Gunicorn
# - En dev  : `runserver`
# =============================================================================
set -euo pipefail

: "${DB_HOST:=postgres}"
: "${DB_PORT:=5432}"
: "${REDIS_HOST:=}"
: "${REDIS_PORT:=6379}"
: "${DJANGO_SETTINGS_MODULE:=Lyneerp.settings}"
: "${DJANGO_ENV:=dev}"
: "${BIND:=0.0.0.0:8000}"
: "${GUNICORN_WORKERS:=3}"
: "${GUNICORN_TIMEOUT:=120}"
: "${GUNICORN_MAX_REQUESTS:=1000}"
: "${GUNICORN_MAX_REQUESTS_JITTER:=50}"

export DJANGO_SETTINGS_MODULE
export DJANGO_ENV

wait_for() {
  local host="$1" port="$2" name="$3"
  echo "⏳ Attente de ${name} sur ${host}:${port} ..."
  local tries=0
  until nc -z "${host}" "${port}"; do
    tries=$((tries + 1))
    if [ "${tries}" -gt 60 ]; then
      echo "❌ Timeout en attendant ${name} (${host}:${port})"
      exit 1
    fi
    sleep 1
  done
  echo "✅ ${name} OK"
}

wait_for "${DB_HOST}" "${DB_PORT}" "Postgres"
if [ -n "${REDIS_HOST}" ]; then
  wait_for "${REDIS_HOST}" "${REDIS_PORT}" "Redis"
fi

echo "⚙️  Migrations Django (DJANGO_ENV=${DJANGO_ENV})"
python manage.py migrate --noinput

if [ "${DJANGO_ENV}" = "prod" ]; then
  echo "📦 collectstatic"
  python manage.py collectstatic --noinput

  echo "🚀 Gunicorn sur ${BIND} (workers=${GUNICORN_WORKERS})"
  exec gunicorn Lyneerp.wsgi:application \
    --bind "${BIND}" \
    --workers "${GUNICORN_WORKERS}" \
    --timeout "${GUNICORN_TIMEOUT}" \
    --max-requests "${GUNICORN_MAX_REQUESTS}" \
    --max-requests-jitter "${GUNICORN_MAX_REQUESTS_JITTER}" \
    --access-logfile - \
    --error-logfile -
else
  echo "🚀 runserver (dev) sur ${BIND}"
  exec python manage.py runserver "${BIND}"
fi
