# docker/Dockerfile.rh
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    netcat-openbsd build-essential \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Installe tes deps Python ici si besoin
# COPY requirements.txt /app/
# RUN pip install -r requirements.txt

# Copie du code (si tu as un .dockerignore, vérifie qu'il n'exclut pas ce qu'il faut)
COPY . /app

# ✅ Copie l’entrypoint explicitement à la racine pour éviter tout souci de chemin
COPY entrypoint.sh /entrypoint.sh
# Fix CRLF éventuels si le fichier vient de Windows
RUN sed -i 's/\r$//' /entrypoint.sh && chmod +x /entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]