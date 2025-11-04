# docker/Dockerfile.rh
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Paquets système utiles (netcat pour attendre Postgres, build deps si besoin)
RUN apt-get update && apt-get install -y --no-install-recommends \
    netcat-openbsd \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Si tu as un requirements.txt
# COPY requirements.txt /app/
# RUN pip install -r requirements.txt

# Si tu utilises Poetry (exemple) :
# COPY pyproject.toml poetry.lock /app/
# RUN pip install poetry && poetry config virtualenvs.create false && poetry install --no-interaction --no-ansi

# Copie du code
COPY . /app

# Rendre l’entrypoint exécutable
RUN chmod +x /app/docker/entrypoint.sh

EXPOSE 8000

# On garde la commande dans l’entrypoint (migrations, wait db, etc.)
ENTRYPOINT ["/app/docker/entrypoint.sh"]