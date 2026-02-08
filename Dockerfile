# docker/Dockerfile
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Dépendances OS (nc pour wait-for)
RUN apt-get update && apt-get install -y --no-install-recommends \
    netcat-openbsd curl wget gcc build-essential libpq-dev git \
 && rm -rf /var/lib/apt/lists/*

RUN apt-get update && apt-get install -y --no-install-recommends \
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
# Entrypoint (copié depuis la racine du repo)
COPY entrypoint.sh /entrypoint.sh
# Normalise les fins de ligne si jamais le fichier a du CRLF
RUN sed -i 's/\r$//' /entrypoint.sh && chmod +x /entrypoint.sh

# Requirements
COPY requirements.txt /requirements.txt
RUN pip install --upgrade pip && pip install -r /requirements.txt

# Code de l’app
COPY . /app

EXPOSE 8000

# Tu peux aussi définir l’ENTRYPOINT ici, sinon on le mettra dans compose :
# ENTRYPOINT ["/entrypoint.sh"]