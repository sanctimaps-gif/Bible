"""Analyse des références bibliques telles qu'on les écrit en français.

Exemples reconnus :

    « Jn 3, 16 »            → Jean, chapitre 3, verset 16
    « Rm 12, 1-5 »          → Romains 12, versets 1 à 5
    « 1 Co 13 »             → 1 Corinthiens, chapitre 13 entier
    « Genèse 22, 1-19 »     → nom complet accepté
    « Mt 5, 3-12.17 »       → plusieurs tranches de versets
    « Ps 22 (23) »          → numérotation double des psaumes

La sortie est une `Reference`, structure normalisée que le reste du programme
manipule sans jamais refaire d'analyse de chaîne.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .livres import Livre, trouver_livre


@dataclass(frozen=True)
class Reference:
    livre: Livre
    chapitre: int
    versets: tuple[tuple[int, int], ...] = ()  # tranches (début, fin) incluses

    @property
    def chapitre_entier(self) -> bool:
        return not self.versets

    def contient(self, verset: int) -> bool:
        if self.chapitre_entier:
            return True
        return any(debut <= verset <= fin for debut, fin in self.versets)

    def __str__(self) -> str:
        if self.chapitre_entier:
            return f"{self.livre.code} {self.chapitre}"
        tranches = ".".join(
            str(debut) if debut == fin else f"{debut}-{fin}" for debut, fin in self.versets
        )
        return f"{self.livre.code} {self.chapitre}, {tranches}"

    def libelle(self) -> str:
        """Référence en toutes lettres, pour une phrase de réponse."""
        if self.chapitre_entier:
            return f"{self.livre.nom}, chapitre {self.chapitre}"
        return f"{self.livre.nom} {self.chapitre}, {self.__str__().split(', ', 1)[1]}"


# Le nom du livre peut comporter un chiffre initial (1 Co), des lettres
# accentuées, des apostrophes et des espaces. On capture le plus large possible,
# puis `trouver_livre` tranche.
_MOTIF = re.compile(
    r"""^\s*
    (?P<livre>\d?\s*[^\d,;]+?)          # nom ou code du livre
    \s+
    (?P<chapitre>\d{1,3})               # chapitre
    (?:\s*\(\s*\d{1,3}\s*\))?           # numérotation alternative, ex. Ps 22 (23)
    (?:\s*[,.:]\s*(?P<versets>\d[\d\s,.\-–—a-z]*))?  # versets facultatifs (« 16a » admis)
    \s*$""",
    re.VERBOSE,
)


def analyser(brut: str) -> Reference | None:
    """Analyse une référence. Retourne None si elle n'est pas reconnaissable."""
    if not brut or not brut.strip():
        return None

    texte = brut.strip().replace("–", "-").replace("—", "-")
    # Les références liturgiques portent parfois des suffixes de lecture
    # (« Lc 2, 41-52 — psaume »). On coupe au premier séparateur fort.
    texte = re.split(r"\s+[—|]\s+", texte)[0].strip()

    correspondance = _MOTIF.match(texte)
    if correspondance is None:
        # Cas « Jude 5 » ou « Abdias 3 » où le livre n'a qu'un chapitre, mais
        # aussi « Philémon » seul.
        livre = trouver_livre(texte)
        if livre is not None and livre.chapitres == 1:
            return Reference(livre=livre, chapitre=1)
        return None

    livre = trouver_livre(correspondance.group("livre"))
    if livre is None:
        return None

    chapitre = int(correspondance.group("chapitre"))

    # Un livre d'un seul chapitre cité « Jude 5 » : le 5 est un verset, pas un
    # chapitre. On corrige, sinon on renverrait un chapitre inexistant.
    if livre.chapitres == 1 and chapitre > 1 and not correspondance.group("versets"):
        return Reference(livre=livre, chapitre=1, versets=((chapitre, chapitre),))

    if chapitre < 1 or chapitre > livre.chapitres:
        return None

    versets = _analyser_versets(correspondance.group("versets") or "")
    return Reference(livre=livre, chapitre=chapitre, versets=versets)


def _analyser_versets(brut: str) -> tuple[tuple[int, int], ...]:
    """« 1-5.17, 20-21 » → ((1, 5), (17, 17), (20, 21))."""
    tranches: list[tuple[int, int]] = []
    for morceau in re.split(r"[.,]", brut):
        morceau = morceau.strip()
        if not morceau:
            continue
        intervalle = re.fullmatch(r"(\d{1,3})\s*-\s*(\d{1,3})", morceau)
        if intervalle:
            debut, fin = int(intervalle.group(1)), int(intervalle.group(2))
            if debut <= fin:
                tranches.append((debut, fin))
            continue
        unique = re.fullmatch(r"(\d{1,3})[a-z]?", morceau)  # « 16a » → verset 16
        if unique:
            numero = int(unique.group(1))
            tranches.append((numero, numero))
    return tuple(tranches)


def extraire_toutes(texte: str) -> list[Reference]:
    """Repère toutes les références présentes dans un texte libre.

    Utile pour relier une lecture de la messe (« Rm 12, 1-5 ») au corpus, ou
    pour vérifier après coup que les références citées par le modèle existent.
    """
    resultats: list[Reference] = []
    motif_grossier = re.compile(
        r"\b(\d?\s*[A-ZÉÈÊÀÂÎÔÛÇ][\wÉÈÊàâäéèêëîïôöùûüç'’]*(?:\s+[a-zéèêà][\wéèêëàâîïôöùûüç'’]+){0,3})"
        r"\s+(\d{1,3})(?:\s*[,.:]\s*([\d\s,.\-–—]+))?"
    )
    for correspondance in motif_grossier.finditer(texte):
        candidat = correspondance.group(0)
        reference = analyser(candidat)
        if reference is not None:
            resultats.append(reference)
    return resultats
