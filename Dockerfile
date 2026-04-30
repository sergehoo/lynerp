# =============================================================================
# LYNEERP — Image Docker de production (multi-stage).
#
# Stage 1 (assets) : Node.js construit Tailwind CSS + copie les vendors.
# Stage 2 (final)  : Python 3.11 slim, sans Node, avec les assets buildés.
#
# Construction :
#   docker build -t lyneerp:latest .
# =============================================================================

# -----------------------------------------------------------------------------
# Stage 1 — Build des assets front (Tailwind, Alpine, FontAwesome, SweetAlert2)
# -----------------------------------------------------------------------------
FROM node:20-alpine AS assets

WORKDIR /build

# 1) Installer les deps node en cachant la couche.
COPY package.json package-lock.json* ./
RUN npm install --no-audit --no-fund

# 2) Copier sources nécessaires au build CSS (templates pour le purge Tailwind).
COPY tailwind.config.js ./
COPY scripts/ ./scripts/
COPY static/src/ ./static/src/
COPY templates/ ./templates/
COPY hr/ ./hr/
COPY finance/ ./finance/
COPY tenants/ ./tenants/

# 3) Build Tailwind + copie des vendors (Alpine, SweetAlert2, FontAwesome).
RUN mkdir -p static/dist static/vendor \
 && npx tailwindcss -i ./static/src/main.css -o ./static/dist/main.css --minify \
 && node ./scripts/copy-vendor.js


# -----------------------------------------------------------------------------
# Stage 2 — Image Python finale
# -----------------------------------------------------------------------------
FROM python:3.11-slim AS final

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DJANGO_ENV=prod

WORKDIR /app

# Dépendances système (Postgres, WeasyPrint, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
        netcat-openbsd \
        curl \
        wget \
        gcc \
        build-essential \
        libpq-dev \
        git \
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

# Entrypoint
COPY entrypoint.sh /entrypoint.sh
RUN sed -i 's/\r$//' /entrypoint.sh && chmod +x /entrypoint.sh

# Dépendances Python (couche cache)
COPY requirements.txt /app/requirements.txt
COPY requirements /app/requirements
RUN pip install --upgrade pip \
 && pip install -r /app/requirements/prod.txt

# Code applicatif
COPY . /app

# Récupère les assets buildés depuis le stage Node.
COPY --from=assets /build/static/dist  /app/static/dist
COPY --from=assets /build/static/vendor /app/static/vendor

# User non-root
RUN groupadd -r lyneerp \
 && useradd -r -g lyneerp -d /app -s /sbin/nologin lyneerp \
 && chown -R lyneerp:lyneerp /app
USER lyneerp

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/healthz || exit 1

ENTRYPOINT ["/entrypoint.sh"]
