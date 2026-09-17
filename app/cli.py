"""Interface en ligne de commande.

    python -m app.cli "Que dit le Nouveau Testament sur la tromperie ?"
    python -m app.cli --image scene.jpg "Quelle scène est-ce ?"
    python -m app.cli --messe 2026-09-17
    python -m app.cli --etat
"""

from __future__ import annotations

import argparse
import sys
from datetime import date as Date

from .config import config
from .corpus import recherche
from .ia.agent import AssistantBiblique, Image
from .sources.aelf import ClientAelf, SourceIndisponible

VERT = "\033[32m"
GRIS = "\033[90m"
ROUGE = "\033[31m"
FIN = "\033[0m"


def _couleur(texte: str, code: str) -> str:
    return f"{code}{texte}{FIN}" if sys.stdout.isatty() else texte


def commande_question(question: str, chemin_image: str | None) -> int:
    image = None
    if chemin_image:
        try:
            image = Image.depuis_fichier(chemin_image)
        except (ValueError, OSError) as erreur:
            print(_couleur(f"Image inutilisable : {erreur}", ROUGE), file=sys.stderr)
            return 1

    code_sortie = 0
    with AssistantBiblique(config) as assistant:
        for evenement in assistant.dialoguer(question, image):
            if evenement.type == "outil":
                print(_couleur(f"  → {evenement.contenu}", GRIS), file=sys.stderr)
            elif evenement.type == "resultat":
                print(_couleur(f"    {evenement.contenu}", GRIS), file=sys.stderr)
            elif evenement.type == "texte":
                print(evenement.contenu, end="", flush=True)
            elif evenement.type == "fin":
                print()
            elif evenement.type == "erreur":
                print(_couleur(f"\nErreur : {evenement.contenu}", ROUGE), file=sys.stderr)
                code_sortie = 1
    return code_sortie


def commande_messe(jour: str | None) -> int:
    with ClientAelf(config) as client:
        try:
            messe = client.messe(jour or Date.today().isoformat())
        except (SourceIndisponible, ValueError) as erreur:
            print(_couleur(str(erreur), ROUGE), file=sys.stderr)
            return 1

    print(_couleur(f"{messe['fete'] or 'Messe du jour'} — {messe['date']}", VERT))
    print(_couleur(messe["url"], GRIS))
    for lecture in messe["lectures"]:
        print()
        print(_couleur(f"{lecture['type']} — {lecture['reference']}", VERT))
        if lecture["titre"]:
            print(lecture["titre"])
        print(lecture["texte"])
    return 0


def commande_etat() -> int:
    pret = recherche.index_disponible(config)
    print(f"Modèle           : {config.modele} (effort {config.effort})")
    print(f"Zone liturgique  : {config.zone}")
    print(f"Données          : {config.donnees}")
    print("Sources          : aelf.org, sanctimaps.fr")
    if pret:
        try:
            print(f"Corpus           : {recherche.index(config).taille} versets indexés")
        except Exception as erreur:
            print(_couleur(f"Corpus           : illisible ({erreur})", ROUGE))
            return 1
    else:
        print(
            _couleur(
                "Corpus           : absent — lancez « python scripts/ingerer_bible.py »",
                ROUGE,
            )
        )
    return 0


def principal(argv: list[str] | None = None) -> int:
    analyseur = argparse.ArgumentParser(
        prog="app.cli",
        description="Assistant biblique adossé à AELF et sanctimaps.fr.",
    )
    analyseur.add_argument("question", nargs="?", help="La question à poser.")
    analyseur.add_argument("--image", help="Image d'une scène biblique à identifier.")
    analyseur.add_argument(
        "--messe",
        nargs="?",
        const="",
        metavar="AAAA-MM-JJ",
        help="Affiche les lectures de la messe (par défaut : aujourd'hui).",
    )
    analyseur.add_argument("--etat", action="store_true", help="Affiche l'état du service.")
    arguments = analyseur.parse_args(argv)

    if arguments.etat:
        return commande_etat()
    if arguments.messe is not None:
        return commande_messe(arguments.messe or None)
    if not arguments.question:
        analyseur.print_help()
        return 2
    return commande_question(arguments.question, arguments.image)


if __name__ == "__main__":
    raise SystemExit(principal())
