"""Table des livres bibliques, selon le canon catholique servi par AELF.

Chaque entrée donne le code employé dans les URL AELF (`/bible/<code>/<chapitre>`),
le nom français complet, le nombre de chapitres, le testament et la section.
Les alias couvrent les graphies courantes (« Ecclésiaste » pour Qohélet,
« Ecclésiastique » pour le Siracide, « Apocalypse » pour Ap, etc.) afin qu'une
question posée en langage naturel trouve toujours son livre.

Les codes suivent les abréviations liturgiques françaises usuelles. Si AELF
devait employer une graphie différente pour un livre, il suffit de corriger le
champ `code` ici : tout le reste du programme en dépend.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Livre:
    code: str
    nom: str
    chapitres: int
    testament: str  # « ancien » ou « nouveau »
    section: str
    alias: tuple[str, ...] = field(default=())


LIVRES: tuple[Livre, ...] = (
    # ---------------- Ancien Testament — Pentateuque ----------------
    Livre("Gn", "Livre de la Genèse", 50, "ancien", "Pentateuque", ("Genese",)),
    Livre("Ex", "Livre de l'Exode", 40, "ancien", "Pentateuque", ("Exode",)),
    Livre("Lv", "Livre des Lévites", 27, "ancien", "Pentateuque", ("Lévitique", "Levitique")),
    Livre("Nb", "Livre des Nombres", 36, "ancien", "Pentateuque", ("Nombres",)),
    Livre("Dt", "Livre du Deutéronome", 34, "ancien", "Pentateuque", ("Deutéronome",)),
    # ---------------- Ancien Testament — Livres historiques ----------------
    Livre("Jos", "Livre de Josué", 24, "ancien", "Livres historiques", ("Josué",)),
    Livre("Jg", "Livre des Juges", 21, "ancien", "Livres historiques", ("Juges",)),
    Livre("Rt", "Livre de Ruth", 4, "ancien", "Livres historiques", ("Ruth",)),
    Livre("1S", "Premier livre de Samuel", 31, "ancien", "Livres historiques", ("1 Samuel", "I Samuel")),
    Livre("2S", "Deuxième livre de Samuel", 24, "ancien", "Livres historiques", ("2 Samuel", "II Samuel")),
    Livre("1R", "Premier livre des Rois", 22, "ancien", "Livres historiques", ("1 Rois", "I Rois")),
    Livre("2R", "Deuxième livre des Rois", 25, "ancien", "Livres historiques", ("2 Rois", "II Rois")),
    Livre("1Ch", "Premier livre des Chroniques", 29, "ancien", "Livres historiques", ("1 Chroniques",)),
    Livre("2Ch", "Deuxième livre des Chroniques", 36, "ancien", "Livres historiques", ("2 Chroniques",)),
    Livre("Esd", "Livre d'Esdras", 10, "ancien", "Livres historiques", ("Esdras",)),
    Livre("Ne", "Livre de Néhémie", 13, "ancien", "Livres historiques", ("Néhémie",)),
    Livre("Tb", "Livre de Tobie", 14, "ancien", "Livres historiques", ("Tobie",)),
    Livre("Jdt", "Livre de Judith", 16, "ancien", "Livres historiques", ("Judith",)),
    Livre("Est", "Livre d'Esther", 10, "ancien", "Livres historiques", ("Esther",)),
    Livre("1M", "Premier livre des Martyrs d'Israël", 16, "ancien", "Livres historiques", ("1 Maccabées", "1 Macchabées")),
    Livre("2M", "Deuxième livre des Martyrs d'Israël", 15, "ancien", "Livres historiques", ("2 Maccabées", "2 Macchabées")),
    # ---------------- Ancien Testament — Livres poétiques et sapientiaux ----------------
    Livre("Jb", "Livre de Job", 42, "ancien", "Livres sapientiaux", ("Job",)),
    Livre("Ps", "Livre des Psaumes", 150, "ancien", "Livres sapientiaux", ("Psaume", "Psaumes")),
    Livre("Pr", "Livre des Proverbes", 31, "ancien", "Livres sapientiaux", ("Proverbes",)),
    Livre("Qo", "Livre de Qohélet", 12, "ancien", "Livres sapientiaux", ("Qohélet", "Ecclésiaste", "Ecclesiaste")),
    Livre("Ct", "Cantique des cantiques", 8, "ancien", "Livres sapientiaux", ("Cantique",)),
    Livre("Sg", "Livre de la Sagesse", 19, "ancien", "Livres sapientiaux", ("Sagesse",)),
    Livre("Si", "Livre de Ben Sira le Sage", 51, "ancien", "Livres sapientiaux", ("Siracide", "Ecclésiastique", "Ben Sira")),
    # ---------------- Ancien Testament — Prophètes ----------------
    Livre("Is", "Livre d'Isaïe", 66, "ancien", "Prophètes", ("Isaïe", "Isaie")),
    Livre("Jr", "Livre de Jérémie", 52, "ancien", "Prophètes", ("Jérémie", "Jeremie")),
    Livre("Lm", "Livre des Lamentations", 5, "ancien", "Prophètes", ("Lamentations",)),
    Livre("Ba", "Livre de Baruch", 6, "ancien", "Prophètes", ("Baruch",)),
    Livre("Ez", "Livre d'Ézékiel", 48, "ancien", "Prophètes", ("Ézéchiel", "Ezechiel", "Ézékiel")),
    Livre("Dn", "Livre de Daniel", 14, "ancien", "Prophètes", ("Daniel",)),
    Livre("Os", "Livre d'Osée", 14, "ancien", "Prophètes", ("Osée", "Osee")),
    Livre("Jl", "Livre de Joël", 4, "ancien", "Prophètes", ("Joël", "Joel")),
    Livre("Am", "Livre d'Amos", 9, "ancien", "Prophètes", ("Amos",)),
    Livre("Ab", "Livre d'Abdias", 1, "ancien", "Prophètes", ("Abdias",)),
    Livre("Jon", "Livre de Jonas", 4, "ancien", "Prophètes", ("Jonas",)),
    Livre("Mi", "Livre de Michée", 7, "ancien", "Prophètes", ("Michée", "Michee")),
    Livre("Na", "Livre de Nahoum", 3, "ancien", "Prophètes", ("Nahoum", "Nahum")),
    Livre("Ha", "Livre d'Habacuc", 3, "ancien", "Prophètes", ("Habacuc", "Habaquq")),
    Livre("So", "Livre de Sophonie", 3, "ancien", "Prophètes", ("Sophonie",)),
    Livre("Ag", "Livre d'Aggée", 2, "ancien", "Prophètes", ("Aggée", "Aggee")),
    Livre("Za", "Livre de Zacharie", 14, "ancien", "Prophètes", ("Zacharie",)),
    Livre("Ml", "Livre de Malachie", 3, "ancien", "Prophètes", ("Malachie",)),
    # ---------------- Nouveau Testament — Évangiles et Actes ----------------
    Livre("Mt", "Évangile selon saint Matthieu", 28, "nouveau", "Évangiles", ("Matthieu",)),
    Livre("Mc", "Évangile selon saint Marc", 16, "nouveau", "Évangiles", ("Marc",)),
    Livre("Lc", "Évangile selon saint Luc", 24, "nouveau", "Évangiles", ("Luc",)),
    Livre("Jn", "Évangile selon saint Jean", 21, "nouveau", "Évangiles", ("Jean",)),
    Livre("Ac", "Actes des Apôtres", 28, "nouveau", "Actes", ("Actes",)),
    # ---------------- Nouveau Testament — Lettres ----------------
    Livre("Rm", "Lettre aux Romains", 16, "nouveau", "Lettres de saint Paul", ("Romains",)),
    Livre("1Co", "Première lettre aux Corinthiens", 16, "nouveau", "Lettres de saint Paul", ("1 Corinthiens",)),
    Livre("2Co", "Deuxième lettre aux Corinthiens", 13, "nouveau", "Lettres de saint Paul", ("2 Corinthiens",)),
    Livre("Ga", "Lettre aux Galates", 6, "nouveau", "Lettres de saint Paul", ("Galates",)),
    Livre("Ep", "Lettre aux Éphésiens", 6, "nouveau", "Lettres de saint Paul", ("Éphésiens", "Ephesiens")),
    Livre("Ph", "Lettre aux Philippiens", 4, "nouveau", "Lettres de saint Paul", ("Philippiens",)),
    Livre("Col", "Lettre aux Colossiens", 4, "nouveau", "Lettres de saint Paul", ("Colossiens",)),
    Livre("1Th", "Première lettre aux Thessaloniciens", 5, "nouveau", "Lettres de saint Paul", ("1 Thessaloniciens",)),
    Livre("2Th", "Deuxième lettre aux Thessaloniciens", 3, "nouveau", "Lettres de saint Paul", ("2 Thessaloniciens",)),
    Livre("1Tm", "Première lettre à Timothée", 6, "nouveau", "Lettres de saint Paul", ("1 Timothée",)),
    Livre("2Tm", "Deuxième lettre à Timothée", 4, "nouveau", "Lettres de saint Paul", ("2 Timothée",)),
    Livre("Tt", "Lettre à Tite", 3, "nouveau", "Lettres de saint Paul", ("Tite",)),
    Livre("Phm", "Lettre à Philémon", 1, "nouveau", "Lettres de saint Paul", ("Philémon", "Philemon")),
    Livre("He", "Lettre aux Hébreux", 13, "nouveau", "Lettres de saint Paul", ("Hébreux", "Hebreux")),
    Livre("Jc", "Lettre de saint Jacques", 5, "nouveau", "Lettres catholiques", ("Jacques",)),
    Livre("1P", "Première lettre de saint Pierre", 5, "nouveau", "Lettres catholiques", ("1 Pierre",)),
    Livre("2P", "Deuxième lettre de saint Pierre", 3, "nouveau", "Lettres catholiques", ("2 Pierre",)),
    Livre("1Jn", "Première lettre de saint Jean", 5, "nouveau", "Lettres catholiques", ("1 Jean",)),
    Livre("2Jn", "Deuxième lettre de saint Jean", 1, "nouveau", "Lettres catholiques", ("2 Jean",)),
    Livre("3Jn", "Troisième lettre de saint Jean", 1, "nouveau", "Lettres catholiques", ("3 Jean",)),
    Livre("Jude", "Lettre de saint Jude", 1, "nouveau", "Lettres catholiques", ("Jude",)),
    Livre("Ap", "Apocalypse de saint Jean", 22, "nouveau", "Apocalypse", ("Apocalypse",)),
)


def sans_accents(texte: str) -> str:
    """Repli casse/accents, pour comparer « Isaïe », « isaie » et « ISAIE »."""
    decompose = unicodedata.normalize("NFD", texte)
    return "".join(c for c in decompose if unicodedata.category(c) != "Mn").lower()


def _clef(texte: str) -> str:
    """Clef de recherche : sans accents, sans espaces ni ponctuation."""
    return "".join(c for c in sans_accents(texte) if c.isalnum())


_PAR_CLEF: dict[str, Livre] = {}
for _livre in LIVRES:
    _PAR_CLEF[_clef(_livre.code)] = _livre
    _PAR_CLEF[_clef(_livre.nom)] = _livre
    for _alias in _livre.alias:
        _PAR_CLEF[_clef(_alias)] = _livre
    # « Genèse » doit marcher autant que « Livre de la Genèse ».
    _nom_court = _livre.nom
    for _prefixe in ("Livre de la ", "Livre des ", "Livre du ", "Livre d'", "Livre de "):
        if _nom_court.startswith(_prefixe):
            _PAR_CLEF.setdefault(_clef(_nom_court[len(_prefixe):]), _livre)
            break

PAR_CODE: dict[str, Livre] = {livre.code: livre for livre in LIVRES}


def trouver_livre(nom_ou_code: str) -> Livre | None:
    """Résout « Rm », « romains », « Lettre aux Romains » vers le même livre."""
    if not nom_ou_code:
        return None
    return _PAR_CLEF.get(_clef(nom_ou_code))


def livres_par_testament(testament: str) -> list[Livre]:
    return [livre for livre in LIVRES if livre.testament == testament]


NOMBRE_DE_CHAPITRES = sum(livre.chapitres for livre in LIVRES)
