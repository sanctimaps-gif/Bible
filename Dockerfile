# Image de l'assistant biblique.
#
# L'application est un serveur : elle détient la clé API Anthropic et interroge
# AELF. Elle ne peut donc pas être hébergée sur GitHub Pages (statique seul).
# Cette image tourne telle quelle sur n'importe quel hébergeur qui accepte
# Docker : Render, Railway, Fly.io, Hugging Face Spaces, Scaleway, un VPS…

FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    BIBLE_DONNEES=/données

WORKDIR /app

# Les dépendances d'abord : cette couche ne change qu'avec requirements.txt.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY web/ ./web/
COPY scripts/ ./scripts/
COPY entrypoint.sh .
RUN chmod +x entrypoint.sh

# Le corpus biblique vit ici. Montez-y un volume persistant : sans cela, il est
# retéléchargé depuis AELF à chaque redémarrage (≈ 11 minutes).
VOLUME ["/données"]

# La plupart des hébergeurs imposent le port par la variable PORT.
ENV PORT=8000
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
    CMD python -c "import os,urllib.request; urllib.request.urlopen(f\"http://127.0.0.1:{os.environ.get('PORT','8000')}/api/etat\").read()"

ENTRYPOINT ["./entrypoint.sh"]
