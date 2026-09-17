"""Cache disque pour les réponses HTTP.

AELF est une source bénévole : on ne la sollicite qu'une fois par ressource et
par période de validité. Le cache sert aussi de garantie de reproductibilité —
deux questions posées le même jour lisent exactement le même texte.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any


class CacheDisque:
    def __init__(self, racine: Path, ttl: int) -> None:
        self.racine = racine
        self.ttl = ttl
        self.racine.mkdir(parents=True, exist_ok=True)

    def _fichier(self, cle: str) -> Path:
        empreinte = hashlib.sha256(cle.encode("utf-8")).hexdigest()[:32]
        return self.racine / f"{empreinte}.json"

    def lire(self, cle: str) -> Any | None:
        fichier = self._fichier(cle)
        if not fichier.exists():
            return None
        try:
            enveloppe = json.loads(fichier.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
        if self.ttl > 0 and time.time() - enveloppe.get("horodatage", 0) > self.ttl:
            return None
        return enveloppe.get("contenu")

    def ecrire(self, cle: str, contenu: Any) -> None:
        enveloppe = {"cle": cle, "horodatage": time.time(), "contenu": contenu}
        fichier = self._fichier(cle)
        # Écriture atomique : un cache à moitié écrit est pire que pas de cache.
        provisoire = fichier.with_suffix(".tmp")
        provisoire.write_text(
            json.dumps(enveloppe, ensure_ascii=False), encoding="utf-8"
        )
        provisoire.replace(fichier)

    def vider(self) -> int:
        supprimes = 0
        for fichier in self.racine.glob("*.json"):
            fichier.unlink()
            supprimes += 1
        return supprimes
