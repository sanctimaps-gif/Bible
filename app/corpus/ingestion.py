"""Ingestion du texte biblique depuis AELF vers le corpus local.

Un livre par fichier JSON, reprise possible après interruption : un chapitre
déjà présent n'est pas retéléchargé. Le rythme est volontairement lent
(`BIBLE_DELAI_INGESTION`) — AELF est un service gratuit, on ne le martèle pas.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

from ..config import Config, config
from ..sources.aelf import ClientAelf, SourceIndisponible
from .livres import LIVRES, Livre, trouver_livre


@dataclass
class Avancement:
    livre: str
    chapitre: int
    total_chapitres: int
    versets: int
    etat: str  # « ingéré », « déjà présent » ou « échec »
    detail: str = ""


Observateur = Callable[[Avancement], None]


def _fichier_livre(cfg: Config, livre: Livre) -> Path:
    return cfg.racine_bible / f"{livre.code}.json"


def charger_livre(cfg: Config, livre: Livre) -> dict:
    fichier = _fichier_livre(cfg, livre)
    if fichier.exists():
        try:
            return json.loads(fichier.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {"code": livre.code, "nom": livre.nom, "chapitres": {}}


def enregistrer_livre(cfg: Config, livre: Livre, donnees: dict) -> None:
    fichier = _fichier_livre(cfg, livre)
    fichier.parent.mkdir(parents=True, exist_ok=True)
    provisoire = fichier.with_suffix(".tmp")
    provisoire.write_text(
        json.dumps(donnees, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    provisoire.replace(fichier)


def selectionner_livres(noms: Iterable[str] | None) -> list[Livre]:
    """Résout une liste de noms/codes en livres ; vide → tout le canon."""
    if not noms:
        return list(LIVRES)
    choisis: list[Livre] = []
    for nom in noms:
        livre = trouver_livre(nom)
        if livre is None:
            raise ValueError(f"Livre inconnu : {nom!r}")
        if livre not in choisis:
            choisis.append(livre)
    return choisis


def ingerer(
    livres: Iterable[Livre] | None = None,
    cfg: Config | None = None,
    client: ClientAelf | None = None,
    observateur: Observateur | None = None,
    reprendre: bool = True,
) -> dict[str, int]:
    """Télécharge les chapitres demandés et écrit le corpus local.

    Retourne un décompte : chapitres ingérés, ignorés, en échec.
    """
    cfg = cfg or config
    cfg.preparer_repertoires()
    livres = list(livres or LIVRES)
    doit_fermer = client is None
    client = client or ClientAelf(cfg)

    compteurs = {"ingeres": 0, "ignores": 0, "echecs": 0}

    try:
        for livre in livres:
            donnees = charger_livre(cfg, livre)
            chapitres = donnees.setdefault("chapitres", {})
            modifie = False

            for numero in range(1, livre.chapitres + 1):
                clef = str(numero)
                if reprendre and chapitres.get(clef):
                    compteurs["ignores"] += 1
                    if observateur:
                        observateur(
                            Avancement(livre.code, numero, livre.chapitres,
                                       len(chapitres[clef]), "déjà présent")
                        )
                    continue

                try:
                    passage = client.chapitre(livre.code, numero, livre.nom)
                except SourceIndisponible as erreur:
                    compteurs["echecs"] += 1
                    if observateur:
                        observateur(
                            Avancement(livre.code, numero, livre.chapitres, 0,
                                       "échec", str(erreur))
                        )
                    time.sleep(cfg.delai_ingestion)
                    continue

                chapitres[clef] = [
                    {"n": numero_verset, "t": texte} for numero_verset, texte in passage.versets
                ]
                modifie = True
                compteurs["ingeres"] += 1
                if observateur:
                    observateur(
                        Avancement(livre.code, numero, livre.chapitres,
                                   len(passage.versets), "ingéré")
                    )
                time.sleep(cfg.delai_ingestion)

            if modifie:
                enregistrer_livre(cfg, livre, donnees)
    finally:
        if doit_fermer:
            client.fermer()

    return compteurs
