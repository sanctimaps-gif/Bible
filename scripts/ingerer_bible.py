#!/usr/bin/env python3
"""Télécharge le texte biblique depuis AELF vers le corpus local.

    python scripts/ingerer_bible.py                 # tout le canon
    python scripts/ingerer_bible.py Jonas Isaïe     # quelques livres
    python scripts/ingerer_bible.py --nouveau       # Nouveau Testament seul
    python scripts/ingerer_bible.py --forcer Jn     # retélécharge même si présent

L'opération est longue (1 334 chapitres au total) et reprend là où elle s'est
arrêtée : on peut l'interrompre et la relancer sans rien perdre.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import config  # noqa: E402
from app.corpus.ingestion import Avancement, ingerer, selectionner_livres  # noqa: E402
from app.corpus.livres import LIVRES  # noqa: E402


def principal(argv: list[str] | None = None) -> int:
    analyseur = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    analyseur.add_argument("livres", nargs="*", help="Livres à ingérer (code ou nom). Vide = tous.")
    analyseur.add_argument("--ancien", action="store_true", help="Ancien Testament seulement.")
    analyseur.add_argument("--nouveau", action="store_true", help="Nouveau Testament seulement.")
    analyseur.add_argument("--forcer", action="store_true", help="Retélécharge les chapitres déjà présents.")
    analyseur.add_argument("--silencieux", action="store_true", help="N'affiche que le bilan final.")
    arguments = analyseur.parse_args(argv)

    try:
        livres = selectionner_livres(arguments.livres)
    except ValueError as erreur:
        print(f"Erreur : {erreur}", file=sys.stderr)
        print("Livres connus :", ", ".join(livre.code for livre in LIVRES), file=sys.stderr)
        return 1

    if arguments.ancien:
        livres = [livre for livre in livres if livre.testament == "ancien"]
    if arguments.nouveau:
        livres = [livre for livre in livres if livre.testament == "nouveau"]

    total = sum(livre.chapitres for livre in livres)
    print(f"Ingestion de {len(livres)} livre(s), {total} chapitre(s), depuis aelf.org.")
    print(f"Destination : {config.racine_bible}")
    print(f"Délai entre requêtes : {config.delai_ingestion} s\n")

    def afficher(avancement: Avancement) -> None:
        if arguments.silencieux:
            return
        marqueurs = {"ingéré": "✓", "déjà présent": "·", "échec": "✗"}
        marqueur = marqueurs.get(avancement.etat, "?")
        ligne = (
            f"{marqueur} {avancement.livre} {avancement.chapitre}/"
            f"{avancement.total_chapitres}"
        )
        if avancement.etat == "ingéré":
            ligne += f" — {avancement.versets} versets"
        elif avancement.etat == "échec":
            ligne += f" — {avancement.detail}"
        print(ligne, flush=True)

    try:
        compteurs = ingerer(
            livres, cfg=config, observateur=afficher, reprendre=not arguments.forcer
        )
    except KeyboardInterrupt:
        print("\nInterrompu. Relancez la commande pour reprendre où vous en êtes.")
        return 130

    print(
        f"\nBilan : {compteurs['ingeres']} chapitre(s) ingéré(s), "
        f"{compteurs['ignores']} déjà présent(s), {compteurs['echecs']} en échec."
    )
    if compteurs["echecs"]:
        print(
            "Des chapitres ont échoué. Relancez la commande : seuls les manquants "
            "seront retentés."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(principal())
