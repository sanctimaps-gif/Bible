#!/usr/bin/env python3
"""Décrit la structure d'une page AELF, pour régler l'extraction des versets.

Le développement se fait dans un environnement qui n'a pas accès à aelf.org.
Ce script est donc lancé par GitHub Actions, qui y a accès, et son résultat
sert à ajuster `_extraire_versets`.

    python scripts/diagnostic_aelf.py bible/Jon/1 bible/Ab/1
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

import httpx  # noqa: E402
from bs4 import BeautifulSoup  # noqa: E402

from app.sources.aelf import _extraire_versets  # noqa: E402

CHEMINS_PAR_DEFAUT = ["bible/Jon/1", "bible/Ab/1", "bible/Gn/1"]


def signature(noeud) -> str:
    classes = ".".join(noeud.get("class") or [])
    identifiant = f"#{noeud.get('id')}" if noeud.get("id") else ""
    return f"{noeud.name}{identifiant}{'.' + classes if classes else ''}"


def decrire(chemin: str, client: httpx.Client) -> None:
    url = f"https://www.aelf.org/{chemin}"
    print(f"\n{'=' * 70}\n{url}\n{'=' * 70}")

    try:
        reponse = client.get(url)
    except httpx.HTTPError as erreur:
        print(f"ÉCHEC réseau : {erreur}")
        return

    print(f"statut : {reponse.status_code}  ·  {len(reponse.text)} octets")
    if reponse.status_code >= 400:
        return

    soupe = BeautifulSoup(reponse.text, "lxml")
    for indesirable in soupe.find_all(["script", "style"]):
        indesirable.decompose()

    # Quelles classes reviennent le plus ? C'est là que se trouve le texte.
    classes = Counter()
    for noeud in soupe.find_all(True):
        for classe in noeud.get("class") or []:
            classes[f"{noeud.name}.{classe}"] += 1
    print("\nClasses les plus fréquentes :")
    for nom, compte in classes.most_common(25):
        print(f"  {compte:5d}  {nom}")

    # L'arbre des conteneurs, jusqu'à la profondeur 4.
    print("\nStructure (profondeur 4, blocs de plus de 200 caractères) :")

    def parcourir(noeud, profondeur=0):
        if profondeur > 4 or noeud.name is None:
            return
        texte = noeud.get_text(strip=True)
        if len(texte) > 200:
            print(f"  {'  ' * profondeur}{signature(noeud)}  ({len(texte)} car.)")
        for enfant in noeud.find_all(recursive=False):
            parcourir(enfant, profondeur + 1)

    parcourir(soupe.body or soupe)

    # Ce que l'extraction actuelle en tire.
    versets = _extraire_versets(reponse.text)
    print(f"\nExtraction actuelle : {len(versets)} verset(s)")
    for numero, texte in versets[:4]:
        print(f"  {numero}. {texte[:110]!r}")

    # Les nœuds portant « verse » dans leur classe, tels quels.
    print("\nNœuds dont la classe contient « verse » ou « verset » (5 premiers) :")
    for noeud in soupe.select("[class*=verse], [class*=verset]")[:5]:
        apercu = noeud.get_text(" ", strip=True)[:110]
        print(f"  {signature(noeud)} → {apercu!r}")

    # Le sommaire des chapitres pollue les versets : où vit-il ?
    print("\nNœuds contenant « chapitre N » en série (candidats sommaire) :")
    for noeud in soupe.find_all(True):
        texte = noeud.get_text(" ", strip=True)
        if texte.count("chapitre") >= 3 and len(texte) < 4000:
            enfants = noeud.find_all(True, recursive=False)
            if not any(
                enfant.get_text(" ", strip=True).count("chapitre") >= 3
                for enfant in enfants
            ):
                print(f"  {signature(noeud)} → {texte[:120]!r}")
                parent = noeud.parent
                chaine = []
                while parent is not None and parent.name not in ("body", "[document]"):
                    chaine.append(signature(parent))
                    parent = parent.parent
                print(f"      ancêtres : {' < '.join(chaine[:5])}")
                break


def principal(argv: list[str] | None = None) -> int:
    chemins = (argv or sys.argv[1:]) or CHEMINS_PAR_DEFAUT
    with httpx.Client(
        timeout=20.0,
        follow_redirects=True,
        headers={
            "User-Agent": "assistant-biblique-aelf/1.0 (diagnostic)",
            "Accept-Language": "fr",
        },
    ) as client:
        for chemin in chemins:
            decrire(chemin, client)
    return 0


if __name__ == "__main__":
    raise SystemExit(principal())
