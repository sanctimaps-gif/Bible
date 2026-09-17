#!/bin/sh
# Démarrage du conteneur.
#
# Le corpus biblique n'est pas dans l'image : c'est le texte d'AELF, on ne le
# redistribue pas. Il est téléchargé au premier démarrage si le volume est vide,
# puis réutilisé tant que le volume persiste.

set -e

CORPUS="${BIBLE_DONNEES:-/données}/bible"

if [ "${BIBLE_INGERER_AU_DEMARRAGE:-1}" = "1" ]; then
  if [ -z "$(ls -A "$CORPUS" 2>/dev/null)" ]; then
    echo "Corpus absent : téléchargement depuis aelf.org (une dizaine de minutes)."
    echo "Montez un volume persistant sur ${BIBLE_DONNEES:-/données} pour ne le faire qu'une fois."
    python scripts/ingerer_bible.py --silencieux || {
      echo "Ingestion incomplète. Le service démarre quand même :"
      echo "la lecture d'un passage par sa référence et la messe du jour restent"
      echo "disponibles, seule la recherche par thème sera limitée."
    }
  else
    echo "Corpus déjà présent dans $CORPUS."
  fi
fi

exec uvicorn app.api:application --host 0.0.0.0 --port "${PORT:-8000}"
