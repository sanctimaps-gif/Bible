"""Configuration globale, pilotée par variables d'environnement.

Le principe directeur de tout le projet : **aucune connaissance ne peut entrer
dans une réponse si elle ne vient pas d'un des domaines autorisés ci-dessous.**
C'est `DOMAINES_AUTORISES` qui fait foi, et chaque client HTTP vérifie l'URL
avant d'émettre la moindre requête.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

# Source unique pour tout ce qui touche à l'Écriture et à la liturgie.
DOMAINE_AELF = "aelf.org"

# Source unique pour tout ce qui touche aux saints.
DOMAINE_SANCTIMAPS = "sanctimaps.fr"

DOMAINES_AUTORISES: tuple[str, ...] = (DOMAINE_AELF, DOMAINE_SANCTIMAPS)

# Point d'entrée canonique demandé dans le cahier des charges :
# https://www.aelf.org/2026-09-17/romain/messe
# Les autres URL utilisées sont toutes sur le même domaine (API des offices et
# navigateur biblique) — voir README.md, section « Portée de la source ».
AELF_WEB = "https://www.aelf.org"
AELF_API = "https://api.aelf.org/v1"
SANCTIMAPS_WEB = "https://sanctimaps.fr"


def _chemin(nom: str, defaut: str) -> Path:
    return Path(os.environ.get(nom, defaut)).expanduser()


def _entier(nom: str, defaut: int) -> int:
    brut = os.environ.get(nom)
    if not brut:
        return defaut
    try:
        return int(brut)
    except ValueError:
        return defaut


def _flottant(nom: str, defaut: float) -> float:
    brut = os.environ.get(nom)
    if not brut:
        return defaut
    try:
        return float(brut)
    except ValueError:
        return defaut


@dataclass(frozen=True)
class Config:
    """Paramètres de l'application, résolus une fois au démarrage."""

    modele: str = field(default_factory=lambda: os.environ.get("BIBLE_MODELE", "claude-opus-5"))
    effort: str = field(default_factory=lambda: os.environ.get("BIBLE_EFFORT", "high"))
    zone: str = field(default_factory=lambda: os.environ.get("BIBLE_ZONE", "romain"))

    donnees: Path = field(default_factory=lambda: _chemin("BIBLE_DONNEES", "./data"))
    cache_ttl: int = field(default_factory=lambda: _entier("BIBLE_CACHE_TTL", 7 * 24 * 3600))
    delai_ingestion: float = field(default_factory=lambda: _flottant("BIBLE_DELAI_INGESTION", 0.5))

    # Garde-fous de la boucle d'outils : évite qu'une question mal posée ne
    # parte en boucle infinie de recherches.
    tours_max: int = field(default_factory=lambda: _entier("BIBLE_TOURS_MAX", 12))
    jetons_max: int = field(default_factory=lambda: _entier("BIBLE_JETONS_MAX", 16000))

    @property
    def racine_bible(self) -> Path:
        """Corpus biblique ingéré depuis AELF, un fichier JSON par livre."""
        return self.donnees / "bible"

    @property
    def racine_cache(self) -> Path:
        """Cache des réponses HTTP brutes."""
        return self.donnees / "cache"

    @property
    def racine_index(self) -> Path:
        """Index de recherche plein texte construit à partir du corpus."""
        return self.donnees / "index"

    def preparer_repertoires(self) -> None:
        for chemin in (self.racine_bible, self.racine_cache, self.racine_index):
            chemin.mkdir(parents=True, exist_ok=True)


config = Config()
