# docker/Dockerfile
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# OS deps (netcat pour wait-for, build deps)
RUN apt-get update && apt-get install -y --no-install-recommends \
    netcat-openbsd curl wget gcc build-essential libpq-dev git \
    && rm -rf /var/lib/apt/lists/*

# Requirements
COPY requirements.txt /requirements.txt
RUN pip install --upgrade pip && pip install -r /requirements.txt

# Code + scripts
COPY . /app
RUN chmod +x /entrypoint.sh

EXPOSE 8000

# Gunicorn via entrypoint (cmd passée par docker-compose)
## docker/Dockerfile.rh
#FROM python:3.12-slim
#
#ENV PYTHONDONTWRITEBYTECODE=1 \
#    PYTHONUNBUFFERED=1 \
#    PIP_NO_CACHE_DIR=1
#
#RUN apt-get update && apt-get install -y --no-install-recommends \
#    netcat-openbsd build-essential \
#  && rm -rf /var/lib/apt/lists/*
#
#WORKDIR /app
#
## Installe tes deps Python ici si besoin
## COPY requirements.txt /app/
## RUN pip install -r requirements.txt
#
## Copie du code (si tu as un .dockerignore, vérifie qu'il n'exclut pas ce qu'il faut)
#COPY . /app
#
## ✅ Copie l’entrypoint explicitement à la racine pour éviter tout souci de chemin
#COPY entrypoint.sh /entrypoint.sh
## Fix CRLF éventuels si le fichier vient de Windows
#RUN sed -i 's/\r$//' /entrypoint.sh && chmod +x /entrypoint.sh
#
#EXPOSE 8000
#
#ENTRYPOINT ["/entrypoint.sh"]