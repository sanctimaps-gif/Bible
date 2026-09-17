"""Recherche plein texte dans le corpus AELF ingéré localement.

Pourquoi un index local ? AELF n'expose pas de moteur de recherche interrogeable
verset par verset. Pour répondre à « que dit le Nouveau Testament sur la
tromperie ? », il faut pouvoir balayer tout le corpus. On télécharge donc une
fois le texte depuis AELF (`scripts/ingerer_bible.py`), puis on cherche dedans.
La source reste AELF, et rien qu'AELF : l'index n'est qu'une copie consultable.

L'algorithme est un BM25 classique, avec deux adaptations au français :

* repli sur un **radical** (six premières lettres) pour que « tromperie »,
  « tromper » et « trompeur » tombent dans le même seau ;
* liste de mots vides, pour que « de », « la » et « qui » ne pèsent rien.
"""

from __future__ import annotations

import json
import math
import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from ..config import AELF_WEB, Config, config
from .livres import PAR_CODE, Livre

MOTS_VIDES = frozenset(
    """
    a au aux avec ce ces dans de des du elle en et eux il ils je la le les leur
    lui ma mais me meme mes moi mon ne nos notre nous on ou par pas pour qu que
    qui sa se ses son sur ta te tes toi ton tu un une vos votre vous y d l j n s
    c m t est sont etait etaient ete suis es sommes etes fut furent sera seront
    ai as avons avez ont avait avaient eu cette cet celui celle ceux celles
    dont donc car or ni si comme quand lors alors tout tous toute toutes plus
    moins tres bien deja encore aussi ainsi apres avant entre vers chez sans
    sous jusqu afin
    """.split()
)

LONGUEUR_RADICAL = 6


def _sans_accents(texte: str) -> str:
    decompose = unicodedata.normalize("NFD", texte)
    return "".join(c for c in decompose if unicodedata.category(c) != "Mn")


_SEPARATEURS = re.compile(r"[^0-9a-z]+")


def decouper(texte: str) -> list[str]:
    """Texte → liste de radicaux indexables."""
    normalise = _sans_accents(texte.lower()).replace("’", "'").replace("'", " ")
    jetons = [jeton for jeton in _SEPARATEURS.split(normalise) if jeton]
    return [
        jeton[:LONGUEUR_RADICAL]
        for jeton in jetons
        if len(jeton) > 1 and jeton not in MOTS_VIDES
    ]


@dataclass(frozen=True)
class Verset:
    code_livre: str
    chapitre: int
    numero: int
    texte: str

    @property
    def livre(self) -> Livre | None:
        return PAR_CODE.get(self.code_livre)

    @property
    def reference(self) -> str:
        return f"{self.code_livre} {self.chapitre}, {self.numero}"

    @property
    def url(self) -> str:
        return f"{AELF_WEB}/bible/{self.code_livre}/{self.chapitre}"

    def to_dict(self) -> dict[str, object]:
        livre = self.livre
        return {
            "reference": self.reference,
            "livre": livre.nom if livre else self.code_livre,
            "testament": livre.testament if livre else "",
            "section": livre.section if livre else "",
            "chapitre": self.chapitre,
            "verset": self.numero,
            "texte": self.texte,
            "url": self.url,
        }


class CorpusVide(RuntimeError):
    """Le corpus n'a pas encore été ingéré depuis AELF."""


class IndexBiblique:
    """Index inversé BM25 sur les versets du corpus AELF."""

    K1 = 1.5
    B = 0.75

    def __init__(self, versets: list[Verset]) -> None:
        if not versets:
            raise CorpusVide(
                "Corpus vide. Lancez d'abord : python scripts/ingerer_bible.py"
            )
        self.versets = versets
        self._frequences: list[dict[str, int]] = []
        self._longueurs: list[int] = []
        self._postings: dict[str, list[int]] = defaultdict(list)

        for position, verset in enumerate(versets):
            jetons = decouper(verset.texte)
            compte: dict[str, int] = defaultdict(int)
            for jeton in jetons:
                compte[jeton] += 1
            self._frequences.append(dict(compte))
            self._longueurs.append(len(jetons))
            for jeton in compte:
                self._postings[jeton].append(position)

        self.longueur_moyenne = (sum(self._longueurs) / len(self._longueurs)) or 1.0
        self._total = len(versets)

    # ------------------------------------------------------------------

    def chercher(
        self,
        requete: str,
        *,
        limite: int = 12,
        testament: str | None = None,
        codes_livres: list[str] | None = None,
    ) -> list[tuple[Verset, float]]:
        """Renvoie les versets les plus pertinents, du plus fort au plus faible."""
        jetons = decouper(requete)
        if not jetons:
            return []

        filtre_codes = set(codes_livres or [])
        scores: dict[int, float] = defaultdict(float)

        for jeton in set(jetons):
            postings = self._postings.get(jeton)
            if not postings:
                continue
            idf = math.log(1 + (self._total - len(postings) + 0.5) / (len(postings) + 0.5))
            for position in postings:
                verset = self.versets[position]
                if filtre_codes and verset.code_livre not in filtre_codes:
                    continue
                if testament:
                    livre = verset.livre
                    if livre is None or livre.testament != testament:
                        continue
                frequence = self._frequences[position][jeton]
                longueur = self._longueurs[position] or 1
                numerateur = frequence * (self.K1 + 1)
                denominateur = frequence + self.K1 * (
                    1 - self.B + self.B * longueur / self.longueur_moyenne
                )
                scores[position] += idf * numerateur / denominateur

        if not scores:
            return []

        # Bonus si la requête apparaît littéralement : une citation exacte doit
        # primer sur une simple cooccurrence de mots.
        expression = _sans_accents(requete.lower()).strip()
        if len(expression) > 8:
            for position in list(scores):
                if expression in _sans_accents(self.versets[position].texte.lower()):
                    scores[position] *= 1.5

        meilleurs = sorted(scores.items(), key=lambda paire: paire[1], reverse=True)[:limite]
        return [(self.versets[position], score) for position, score in meilleurs]

    def passage(
        self, code_livre: str, chapitre: int, debut: int | None = None, fin: int | None = None
    ) -> list[Verset]:
        """Versets d'un chapitre (ou d'une tranche) déjà présents dans le corpus."""
        resultat = [
            verset
            for verset in self.versets
            if verset.code_livre == code_livre and verset.chapitre == chapitre
        ]
        if debut is not None:
            resultat = [v for v in resultat if v.numero >= debut]
        if fin is not None:
            resultat = [v for v in resultat if v.numero <= fin]
        return sorted(resultat, key=lambda v: v.numero)

    def contexte(self, verset: Verset, marge: int = 2) -> list[Verset]:
        """Versets voisins, pour ne jamais citer une phrase hors de son contexte."""
        return self.passage(
            verset.code_livre,
            verset.chapitre,
            debut=max(1, verset.numero - marge),
            fin=verset.numero + marge,
        )

    @property
    def taille(self) -> int:
        return self._total


# ----------------------------------------------------------------------
# Chargement du corpus
# ----------------------------------------------------------------------


def charger_versets(racine: Path) -> list[Verset]:
    """Lit les fichiers JSON produits par l'ingestion."""
    versets: list[Verset] = []
    if not racine.exists():
        return versets
    for fichier in sorted(racine.glob("*.json")):
        try:
            donnees = json.loads(fichier.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        code = donnees.get("code") or fichier.stem
        for chapitre_brut, liste in (donnees.get("chapitres") or {}).items():
            try:
                chapitre = int(chapitre_brut)
            except (TypeError, ValueError):
                continue
            for entree in liste:
                texte = (entree.get("t") or "").strip()
                if not texte:
                    continue
                versets.append(
                    Verset(
                        code_livre=code,
                        chapitre=chapitre,
                        numero=int(entree.get("n") or 0),
                        texte=texte,
                    )
                )
    return versets


@lru_cache(maxsize=1)
def index(cfg: Config | None = None) -> IndexBiblique:
    """Index partagé, construit une seule fois par processus."""
    cfg = cfg or config
    return IndexBiblique(charger_versets(cfg.racine_bible))


def index_disponible(cfg: Config | None = None) -> bool:
    cfg = cfg or config
    racine = cfg.racine_bible
    return racine.exists() and any(racine.glob("*.json"))
