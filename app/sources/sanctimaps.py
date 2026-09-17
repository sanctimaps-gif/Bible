"""Client sanctimaps.fr — source unique pour les questions sur les saints.

Le site n'expose pas d'API documentée : on interroge sa recherche interne puis
on lit les pages de résultat. Comme pour AELF, l'extraction est tolérante et
échoue franchement plutôt que de deviner.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote_plus, urljoin

import httpx
from bs4 import BeautifulSoup

from ..config import DOMAINE_SANCTIMAPS, SANCTIMAPS_WEB, Config, config
from .cache import CacheDisque
from .aelf import SourceIndisponible, verifier_domaine


@dataclass
class FicheSaint:
    titre: str
    url: str
    texte: str

    def to_dict(self) -> dict[str, Any]:
        return {"titre": self.titre, "url": self.url, "texte": self.texte}


class ClientSanctimaps:
    def __init__(self, cfg: Config | None = None, client_http: httpx.Client | None = None) -> None:
        self.cfg = cfg or config
        self.cache = CacheDisque(self.cfg.racine_cache, self.cfg.cache_ttl)
        self._http = client_http or httpx.Client(
            timeout=20.0,
            follow_redirects=True,
            headers={
                "User-Agent": "assistant-biblique-aelf/1.0 (hagiographie)",
                "Accept-Language": "fr",
            },
        )

    def fermer(self) -> None:
        self._http.close()

    def __enter__(self) -> "ClientSanctimaps":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.fermer()

    def _get(self, url: str) -> str:
        verifier_domaine(url, DOMAINE_SANCTIMAPS)
        cle = f"sanctimaps::{url}"
        en_cache = self.cache.lire(cle)
        if en_cache is not None:
            return en_cache
        try:
            reponse = self._http.get(url)
        except httpx.HTTPError as erreur:
            raise SourceIndisponible(f"sanctimaps.fr injoignable ({url}) : {erreur}") from erreur
        if reponse.status_code >= 400:
            raise SourceIndisponible(
                f"sanctimaps.fr a répondu {reponse.status_code} pour {url}"
            )
        self.cache.ecrire(cle, reponse.text)
        return reponse.text

    # ------------------------------------------------------------------

    def chercher(self, nom: str, limite: int = 3) -> list[FicheSaint]:
        """Cherche un saint et retourne les fiches correspondantes, texte inclus."""
        url_recherche = f"{SANCTIMAPS_WEB}/?s={quote_plus(nom)}"
        html = self._get(url_recherche)
        liens = _extraire_liens_resultats(html, url_recherche)

        fiches: list[FicheSaint] = []
        for lien in liens[:limite]:
            try:
                fiches.append(self.lire(lien))
            except SourceIndisponible:
                continue

        if not fiches:
            # La recherche interne n'a rien donné d'exploitable : on rend au
            # moins la page de résultats, pour que le modèle puisse dire
            # honnêtement ce qu'il a trouvé (ou pas).
            texte = _texte_principal(html)
            if texte:
                fiches.append(
                    FicheSaint(titre=f"Recherche « {nom} »", url=url_recherche, texte=texte)
                )
        return fiches

    def lire(self, url: str) -> FicheSaint:
        """Lit une page de sanctimaps.fr et en extrait le texte principal."""
        html = self._get(url)
        soupe = BeautifulSoup(html, "lxml")
        titre = ""
        for selecteur in ("h1", "meta[property='og:title']", "title"):
            noeud = soupe.select_one(selecteur)
            if noeud is not None:
                titre = (noeud.get("content") or noeud.get_text() or "").strip()
                if titre:
                    break
        texte = _texte_principal(html)
        if not texte:
            raise SourceIndisponible(f"Page sanctimaps.fr sans contenu exploitable : {url}")
        return FicheSaint(titre=titre or url, url=url, texte=texte)


def _extraire_liens_resultats(html: str, base: str) -> list[str]:
    soupe = BeautifulSoup(html, "lxml")
    liens: list[str] = []
    vus: set[str] = set()

    # On privilégie les liens situés dans une zone de résultats identifiable.
    zones = soupe.select("article, .search-results, .results, main, #content") or [soupe]
    for zone in zones:
        for ancre in zone.find_all("a", href=True):
            url = urljoin(base, ancre["href"]).split("#")[0]
            try:
                verifier_domaine(url, DOMAINE_SANCTIMAPS)
            except Exception:
                continue
            if url in vus or url.rstrip("/") == SANCTIMAPS_WEB.rstrip("/"):
                continue
            if re.search(r"\.(png|jpe?g|gif|svg|css|js|pdf)$", url, re.I):
                continue
            if "?s=" in url:
                continue
            vus.add(url)
            liens.append(url)
        if liens:
            break
    return liens


def _texte_principal(html: str) -> str:
    soupe = BeautifulSoup(html, "lxml")
    for indesirable in soupe.find_all(["script", "style", "nav", "header", "footer", "form"]):
        indesirable.decompose()
    zone = None
    for selecteur in ("article", "main", "#content", ".entry-content", ".post-content"):
        zone = soupe.select_one(selecteur)
        if zone is not None:
            break
    zone = zone or soupe.body or soupe
    texte = zone.get_text("\n")
    texte = texte.replace("\xa0", " ")
    texte = re.sub(r"[ \t]+", " ", texte)
    texte = re.sub(r"\n{3,}", "\n\n", texte)
    return texte.strip()
