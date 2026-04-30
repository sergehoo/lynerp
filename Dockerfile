# =============================================================================
# LYNEERP — Image Docker de production.
#
# Construction :
#   docker build -t lyneerp:latest .
# Lancement local :
#   docker run --rm -p 8000:8000 --env-file .env lyneerp:latest
# =============================================================================

FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DJANGO_ENV=prod

WORKDIR /app

# --- Dépendances système ---------------------------------------------------- #
RUN apt-get update && apt-get install -y --no-install-recommends \
        netcat-openbsd \
        curl \
        wget \
        gcc \
        build-essential \
        libpq-dev \
        git \
        # Dépendances WeasyPrint (génération de PDF)
        libcairo2 \
        libpango-1.0-0 \
        libpangocairo-1.0-0 \
        libgdk-pixbuf-2.0-0 \
        libglib2.0-0 \
        libgobject-2.0-0 \
        shared-mime-info \
        fonts-dejavu-core \
        fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

# --- Entrypoint ------------------------------------------------------------- #
COPY entrypoint.sh /entrypoint.sh
RUN sed -i 's/\r$//' /entrypoint.sh && chmod +x /entrypoint.sh

# --- Dépendances Python ----------------------------------------------------- #
# On copie d'abord UNIQUEMENT les fichiers requirements pour profiter du cache
# Docker (les couches ne se rebuildent pas à chaque modification de code).
COPY requirements.txt /app/requirements.txt
COPY requirements /app/requirements

RUN pip install --upgrade pip \
 && pip install -r /app/requirements/prod.txt

# --- Code applicatif -------------------------------------------------------- #
COPY . /app

# --- Création d'un user non-root -------------------------------------------- #
RUN groupadd -r lyneerp && useradd -r -g lyneerp -d /app -s /sbin/nologin lyneerp \
 && chown -R lyneerp:lyneerp /app
USER lyneerp

EXPOSE 8000

# Healthcheck : on tape /healthz qui est servi sans DB.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/healthz || exit 1

# L'entrypoint orchestre wait-for + migrate + collectstatic + gunicorn.
ENTRYPOINT ["/entrypoint.sh"]
