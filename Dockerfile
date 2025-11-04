FROM ubuntu:latest
LABEL authors="ogahserge"

ENTRYPOINT ["top", "-b"]

set -e

# Attendre que Postgres réponde
echo "⏳ Attente de Postgres..."
until nc -z ${DB_HOST:-postgres} ${DB_PORT:-5432}; do
  sleep 1
done
echo "✅ Postgres OK"

# Migrations
echo "⚙️  Migrations Django"
python manage.py migrate --noinput

# Collecte static (si tu utilises l’admin/collectstatic)
# echo "📦 collectstatic"
# python manage.py collectstatic --noinput

# Lancer le serveur dev (auto-reload). Pour prod, utilise gunicorn.
echo "🚀 runserver"
python manage.py runserver 0.0.0.0:8000