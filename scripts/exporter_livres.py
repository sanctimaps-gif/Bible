#!/usr/bin/env python3
"""Engendre `site/livres.js` à partir de `app/corpus/livres.py`.

La version navigateur a besoin de la même table des livres que la version
serveur. Plutôt que d'en tenir deux à jour — et de les voir diverger —, on
engendre la seconde depuis la première. Le test `test_table_js_a_jour` échoue
si le fichier engendré n'est plus en phase.

    python scripts/exporter_livres.py            # réécrit site/livres.js
    python scripts/exporter_livres.py --verifier # se contente de comparer
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from app.corpus.livres import LIVRES  # noqa: E402

DESTINATION = RACINE / "site" / "livres.js"

ENTETE = """\
// Table des livres bibliques — engendrée depuis app/corpus/livres.py.
// Ne pas modifier à la main : régénérer avec `python scripts/exporter_livres.py`.
// Format : code AELF → [nombre de chapitres, nom complet, graphies acceptées]

export const LIVRES = {
"""

PIED = """\
};

/** Repli casse/accents, pour comparer « Isaïe », « isaie » et « ISAIE ». */
function clef(texte) {
  return texte
    .normalize("NFD")
    .replace(/[\\u0300-\\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]/g, "");
}

const PAR_CLEF = new Map();
for (const [code, [, nom, alias]] of Object.entries(LIVRES)) {
  PAR_CLEF.set(clef(code), code);
  PAR_CLEF.set(clef(nom), code);
  for (const graphie of alias) PAR_CLEF.set(clef(graphie), code);
  // « Genèse » doit marcher autant que « Livre de la Genèse ».
  const court = nom.replace(/^Livre (de la |des |du |d'|de )/, "");
  if (!PAR_CLEF.has(clef(court))) PAR_CLEF.set(clef(court), code);
}

/** Résout « Rm », « romains », « Lettre aux Romains » vers le même code. */
export function trouverLivre(nomOuCode) {
  if (!nomOuCode) return null;
  return PAR_CLEF.get(clef(nomOuCode)) || null;
}

/** Liste compacte pour le prompt système : « Gn (50 ch.) Livre de la Genèse ». */
export function catalogue() {
  return Object.entries(LIVRES)
    .map(([code, [chapitres, nom]]) => `${code} (${chapitres} ch.) ${nom}`)
    .join("\\n");
}
"""


def engendrer() -> str:
    lignes = [
        f"  {json.dumps(livre.code)}: [{livre.chapitres}, "
        f"{json.dumps(livre.nom, ensure_ascii=False)}, "
        f"{json.dumps(list(livre.alias), ensure_ascii=False)}],"
        for livre in LIVRES
    ]
    return ENTETE + "\n".join(lignes) + "\n" + PIED


def principal(argv: list[str] | None = None) -> int:
    analyseur = argparse.ArgumentParser(description=__doc__)
    analyseur.add_argument(
        "--verifier",
        action="store_true",
        help="N'écrit rien ; sort en erreur si le fichier engendré est périmé.",
    )
    arguments = analyseur.parse_args(argv)

    attendu = engendrer()
    actuel = DESTINATION.read_text(encoding="utf-8") if DESTINATION.exists() else ""

    if arguments.verifier:
        if actuel != attendu:
            print(
                "site/livres.js est périmé. Lancez : python scripts/exporter_livres.py",
                file=sys.stderr,
            )
            return 1
        print("site/livres.js est à jour.")
        return 0

    DESTINATION.parent.mkdir(parents=True, exist_ok=True)
    DESTINATION.write_text(attendu, encoding="utf-8")
    print(f"{DESTINATION.relative_to(RACINE)} engendré : {len(LIVRES)} livres.")
    return 0


if __name__ == "__main__":
    raise SystemExit(principal())
