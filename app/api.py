"""API HTTP et service de l'interface web.

    uvicorn app.api:application --reload

Une seule route utile : `POST /api/question`, qui diffuse la réponse en
Server-Sent Events pour que l'interface montre les recherches en cours.
"""

from __future__ import annotations

import json
from datetime import date as Date
from pathlib import Path
from typing import Iterator

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from .config import config
from .corpus import recherche
from .corpus.livres import LIVRES
from .ia.agent import TYPES_IMAGE_ACCEPTES, AssistantBiblique, Image
from .sources.aelf import ClientAelf, SourceIndisponible

RACINE_WEB = Path(__file__).resolve().parent.parent / "web"

application = FastAPI(
    title="Assistant biblique AELF",
    description="Questions-réponses sur la Bible, adossées à aelf.org et sanctimaps.fr.",
    version="1.0.0",
)


@application.get("/api/etat")
def etat() -> dict[str, object]:
    """État du service : corpus ingéré, modèle, sources."""
    corpus_pret = recherche.index_disponible(config)
    versets = 0
    if corpus_pret:
        try:
            versets = recherche.index(config).taille
        except Exception:  # corpus présent mais illisible
            corpus_pret = False
    return {
        "modele": config.modele,
        "zone": config.zone,
        "sources": ["aelf.org", "sanctimaps.fr"],
        "corpus_pret": corpus_pret,
        "versets_indexes": versets,
        "livres_connus": len(LIVRES),
    }


@application.get("/api/messe")
def messe(date: str | None = None, zone: str | None = None) -> dict[str, object]:
    """Lectures de la messe, servies telles quelles depuis AELF."""
    with ClientAelf(config) as client:
        try:
            return client.messe(date or Date.today().isoformat(), zone)
        except (SourceIndisponible, ValueError) as erreur:
            return {"erreur": str(erreur)}


@application.post("/api/question")
async def question(
    texte: str = Form(...),
    image: UploadFile | None = File(default=None),
) -> StreamingResponse:
    """Pose une question. Répond en Server-Sent Events."""
    piece_jointe: Image | None = None
    if image is not None and image.filename:
        type_mime = image.content_type or ""
        if type_mime == "image/jpg":
            type_mime = "image/jpeg"
        if type_mime not in TYPES_IMAGE_ACCEPTES:
            return StreamingResponse(
                _sse_unique(
                    "erreur",
                    f"Format d'image non pris en charge : {type_mime or 'inconnu'}.",
                ),
                media_type="text/event-stream",
            )
        piece_jointe = Image(donnees=await image.read(), type_mime=type_mime)

    return StreamingResponse(
        _diffuser(texte, piece_jointe),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _diffuser(texte: str, image: Image | None) -> Iterator[str]:
    assistant = AssistantBiblique(config)
    try:
        for evenement in assistant.dialoguer(texte, image):
            charge = {
                "type": evenement.type,
                "contenu": evenement.contenu,
                **evenement.donnees,
            }
            yield f"data: {json.dumps(charge, ensure_ascii=False)}\n\n"
    except Exception as erreur:  # dernier filet : l'interface doit toujours être informée
        yield f"data: {json.dumps({'type': 'erreur', 'contenu': str(erreur)}, ensure_ascii=False)}\n\n"
    finally:
        assistant.fermer()
        yield "data: {\"type\": \"terminé\"}\n\n"


def _sse_unique(type_evenement: str, contenu: str) -> Iterator[str]:
    yield f"data: {json.dumps({'type': type_evenement, 'contenu': contenu}, ensure_ascii=False)}\n\n"
    yield "data: {\"type\": \"terminé\"}\n\n"


# ----------------------------------------------------------------------
# Interface web
# ----------------------------------------------------------------------

if RACINE_WEB.exists():
    application.mount("/static", StaticFiles(directory=RACINE_WEB), name="static")

    @application.get("/")
    def accueil() -> FileResponse:
        return FileResponse(RACINE_WEB / "index.html")
