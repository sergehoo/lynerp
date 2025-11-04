#!/usr/bin/env bash
set -euo pipefail

echo "🔧 Environment:"
echo "  DB_HOST=${DB_HOST:-postgres}"
echo "  DB_PORT=${DB_PORT:-5432}"
echo "  REDIS_HOST=${REDIS_HOST:-redis}"
echo "  DEBUG=${DEBUG:-False}"

wait_for_tcp() {
  local host=$1
  local port=$2
  local name=${3:-$host:$port}
  echo "⏳ Attente de $name..."
  for i in $(seq 1 120); do
    if nc -z "$host" "$port" >/dev/null 2>&1; then
      echo "✅ $name joignable"
      return 0
    fi
    sleep 1
  done
  echo "❌ Timeout en attendant $name"; exit 1
}

wait_for_tcp "${DB_HOST:-postgres}" "${DB_PORT:-5432}" "Postgres"
wait_for_tcp "${REDIS_HOST:-redis}" "${REDIS_PORT:-6379}" "Redis"

echo "⚙️  Migrations Django"
python manage.py migrate --noinput

echo "📦 collectstatic"
python manage.py collectstatic --noinput || true

# Health endpoint facultatif
python manage.py check || true

echo "🚀 Lancement: $*"
exec "$@"
##!/usr/bin/env bash
#set -e
#
#: "${DB_HOST:=postgres}"
#: "${DB_PORT:=5432}"
#: "${DJANGO_SETTINGS_MODULE:=Lyneerp.settings}"
#: "${DJANGO_ENV:=dev}"
#: "${BIND:=0.0.0.0:8000}"
#
#echo "⏳ Attente de Postgres sur ${DB_HOST}:${DB_PORT} ..."
#until nc -z "${DB_HOST}" "${DB_PORT}"; do
#  sleep 1
#done
#echo "✅ Postgres OK"
#
#echo "⚙️  Migrations Django"
#python manage.py migrate --noinput
#
## echo "📦 collectstatic"
## python manage.py collectstatic --noinput
#
#if [ "$DJANGO_ENV" = "prod" ]; then
#  echo "🚀 Gunicorn sur ${BIND}"
#  exec gunicorn Lyneerp.wsgi:application --bind "${BIND}" --workers 3 --timeout 120
#else
#  echo "🚀 runserver (dev) sur ${BIND}"
#  exec python manage.py runserver "${BIND}"
#fi