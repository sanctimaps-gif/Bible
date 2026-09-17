#!/usr/bin/env python3
"""Prépare les données statiques que la page consulte, sans serveur ni IA.

Le corpus téléchargé depuis AELF (`data/bible/`) est transformé en fichiers
que le navigateur sait lire directement :

    site/donnees/catalogue.json       la liste des livres et ce qui est disponible
    site/donnees/livres/<code>.json   un livre, chapitre par chapitre
    site/donnees/corpus.json          tous les versets, à plat, pour la recherche
    site/donnees/messe/<date>.json    les lectures d'un jour
    site/donnees/messe/index.json     les dates disponibles

    python scripts/exporter_site.py             # corpus seul
    python scripts/exporter_site.py --messes 7  # + les messes des 7 prochains jours
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date as Date, timedelta
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from app.config import config  # noqa: E402
from app.corpus.livres import LIVRES  # noqa: E402
from app.sources.aelf import ClientAelf, SourceIndisponible  # noqa: E402

DESTINATION = RACINE / "site" / "donnees"


def _ecrire(chemin: Path, donnees: object, compact: bool = True) -> int:
    """Écrit du JSON et rend la taille obtenue, en octets."""
    chemin.parent.mkdir(parents=True, exist_ok=True)
    texte = json.dumps(
        donnees,
        ensure_ascii=False,
        separators=(",", ":") if compact else (", ", ": "),
    )
    chemin.write_text(texte, encoding="utf-8")
    return len(texte.encode("utf-8"))


def exporter_corpus() -> dict[str, int]:
    """Livres et index de recherche, depuis le corpus ingéré."""
    catalogue = []
    corpus: list[list] = []
    total_versets = 0
    poids = 0

    for livre in LIVRES:
        source = config.racine_bible / f"{livre.code}.json"
        chapitres: dict[str, list] = {}
        if source.exists():
            try:
                chapitres = json.loads(source.read_text(encoding="utf-8")).get(
                    "chapitres", {}
                )
            except (json.JSONDecodeError, OSError):
                chapitres = {}

        # On ne garde que les chapitres réellement remplis.
        chapitres = {
            numero: versets for numero, versets in chapitres.items() if versets
        }

        catalogue.append(
            {
                "code": livre.code,
                "nom": livre.nom,
                "chapitres": livre.chapitres,
                "testament": livre.testament,
                "section": livre.section,
                "alias": list(livre.alias),
                "disponibles": sorted(int(n) for n in chapitres),
            }
        )

        if chapitres:
            poids += _ecrire(
                DESTINATION / "livres" / f"{livre.code}.json",
                {"code": livre.code, "nom": livre.nom, "chapitres": chapitres},
            )

        for numero_chapitre, versets in chapitres.items():
            for verset in versets:
                texte = (verset.get("t") or "").strip()
                if not texte:
                    continue
                # Format compact : chaque verset pèse dans le fichier chargé
                # par le navigateur pour la recherche.
                corpus.append(
                    [livre.code, int(numero_chapitre), int(verset.get("n") or 0), texte]
                )
                total_versets += 1

    poids += _ecrire(DESTINATION / "catalogue.json", catalogue)
    poids += _ecrire(DESTINATION / "corpus.json", corpus)

    return {"versets": total_versets, "octets": poids}


def exporter_messes(jours: int, depuis: Date | None = None) -> dict[str, int]:
    """Lectures de la messe pour les prochains jours, lues chez AELF."""
    depuis = depuis or Date.today()
    dates: list[str] = []
    echecs = 0

    dossier = DESTINATION / "messe"
    dossier.mkdir(parents=True, exist_ok=True)

    with ClientAelf(config) as client:
        for decalage in range(jours):
            jour = (depuis + timedelta(days=decalage)).isoformat()
            try:
                messe = client.messe(jour)
            except (SourceIndisponible, ValueError) as erreur:
                print(f"  ✗ {jour} — {erreur}", file=sys.stderr)
                echecs += 1
                continue
            _ecrire(dossier / f"{jour}.json", messe)
            dates.append(jour)
            print(f"  ✓ {jour} — {messe['fete'] or 'messe du jour'}")

    # On conserve les dates déjà présentes : l'export est incrémental.
    connues = {fichier.stem for fichier in dossier.glob("*.json")} - {"index"}
    _ecrire(dossier / "index.json", sorted(connues))

    return {"dates": len(dates), "echecs": echecs}


def principal(argv: list[str] | None = None) -> int:
    analyseur = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    analyseur.add_argument(
        "--messes",
        type=int,
        default=0,
        metavar="N",
        help="Exporte aussi les lectures des N prochains jours (défaut : 0).",
    )
    analyseur.add_argument(
        "--sans-corpus",
        action="store_true",
        help="N'exporte que les messes.",
    )
    arguments = analyseur.parse_args(argv)

    if not arguments.sans_corpus:
        print("Export du corpus biblique…")
        bilan = exporter_corpus()
        if bilan["versets"] == 0:
            print(
                "Aucun verset exporté : le corpus est vide. "
                "Lancez d'abord scripts/ingerer_bible.py.",
                file=sys.stderr,
            )
        print(
            f"  {bilan['versets']} versets, "
            f"{bilan['octets'] / 1_048_576:.1f} Mio écrits dans site/donnees/"
        )

    if arguments.messes:
        print(f"Export des lectures ({arguments.messes} jour(s))…")
        bilan = exporter_messes(arguments.messes)
        print(f"  {bilan['dates']} date(s) exportée(s), {bilan['echecs']} en échec.")

    return 0


if __name__ == "__main__":
    raise SystemExit(principal())
