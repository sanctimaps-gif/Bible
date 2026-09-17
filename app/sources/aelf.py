"""Client AELF — la seule porte d'entrée vers le texte biblique et liturgique.

Deux ressources sont exposées, toutes deux sur le domaine `aelf.org` :

1. **Les offices du jour** (dont la messe), via l'API publique
   `https://api.aelf.org/v1/{office}/{date}/{zone}`, qui sert exactement ce
   qu'affiche la page `https://www.aelf.org/{date}/{zone}/{office}` demandée
   dans le cahier des charges.
2. **Le navigateur biblique** `https://www.aelf.org/bible/{livre}/{chapitre}`,
   qui donne accès au texte intégral de la traduction liturgique.

Le HTML d'AELF n'est pas un contrat d'API : `_extraire_versets` essaie
plusieurs stratégies et signale honnêtement un échec plutôt que de rendre un
texte mutilé. Si AELF change sa mise en page, c'est ici — et seulement ici —
qu'il faut intervenir.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, asdict
from datetime import date as Date
from typing import Any, Iterable

import httpx
from bs4 import BeautifulSoup

from ..config import AELF_API, AELF_WEB, DOMAINE_AELF, Config, config
from .cache import CacheDisque


class SourceInterdite(RuntimeError):
    """Levée quand une URL sort des domaines autorisés."""


class SourceIndisponible(RuntimeError):
    """Levée quand AELF ne répond pas ou répond quelque chose d'inexploitable."""


def verifier_domaine(url: str, domaine: str) -> None:
    """Refuse toute URL qui n'appartient pas au domaine attendu.

    Contrôle sur l'hôte lui-même (et non sur une simple sous-chaîne) pour que
    `https://aelf.org.exemple.net/` soit bien rejeté.
    """
    hote = httpx.URL(url).host or ""
    if hote != domaine and not hote.endswith(f".{domaine}"):
        raise SourceInterdite(
            f"URL hors source autorisée : {url!r} (domaine attendu : {domaine})"
        )


@dataclass
class Lecture:
    """Une lecture de la messe, telle qu'AELF la publie."""

    type: str  # lecture_1, psaume, lecture_2, evangile, ...
    titre: str
    reference: str
    texte: str
    refrain: str = ""
    url: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Passage:
    """Un passage biblique lu dans le navigateur biblique d'AELF."""

    livre: str  # code AELF, ex. « Rm »
    nom_livre: str  # ex. « Lettre aux Romains »
    chapitre: int
    versets: list[tuple[int, str]]
    url: str

    @property
    def texte(self) -> str:
        return "\n".join(f"{numero}. {texte}" for numero, texte in self.versets)

    def to_dict(self) -> dict[str, Any]:
        return {
            "livre": self.livre,
            "nom_livre": self.nom_livre,
            "chapitre": self.chapitre,
            "versets": [{"numero": n, "texte": t} for n, t in self.versets],
            "url": self.url,
        }


def _nettoyer(html_ou_texte: str) -> str:
    """Convertit un fragment HTML AELF en texte lisible.

    AELF encode les retours à la ligne poétiques (psaumes) par des <br>, et
    entoure les paragraphes de <p>. On préserve ces ruptures, car elles portent
    le rythme du texte liturgique.
    """
    if not html_ou_texte:
        return ""
    soupe = BeautifulSoup(html_ou_texte, "lxml")
    for saut in soupe.find_all("br"):
        saut.replace_with("\n")
    for paragraphe in soupe.find_all("p"):
        paragraphe.append("\n\n")
    texte = soupe.get_text()
    texte = texte.replace("\xa0", " ")
    texte = re.sub(r"[ \t]+", " ", texte)
    texte = re.sub(r"\n{3,}", "\n\n", texte)
    return texte.strip()


class ClientAelf:
    """Accès en lecture à AELF, avec cache et garde-fou de domaine."""

    def __init__(self, cfg: Config | None = None, client_http: httpx.Client | None = None) -> None:
        self.cfg = cfg or config
        self.cache = CacheDisque(self.cfg.racine_cache, self.cfg.cache_ttl)
        self._http = client_http or httpx.Client(
            timeout=20.0,
            follow_redirects=True,
            headers={
                "User-Agent": "assistant-biblique-aelf/1.0 (lecture liturgique)",
                "Accept-Language": "fr",
            },
        )

    def fermer(self) -> None:
        self._http.close()

    def __enter__(self) -> "ClientAelf":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.fermer()

    # ------------------------------------------------------------------
    # Transport
    # ------------------------------------------------------------------

    def _get(self, url: str, *, json_attendu: bool) -> Any:
        verifier_domaine(url, DOMAINE_AELF)

        cle = f"aelf::{url}"
        en_cache = self.cache.lire(cle)
        if en_cache is not None:
            return en_cache

        try:
            reponse = self._http.get(url)
        except httpx.HTTPError as erreur:
            raise SourceIndisponible(f"AELF injoignable ({url}) : {erreur}") from erreur

        if reponse.status_code == 404:
            raise SourceIndisponible(f"Ressource absente chez AELF : {url}")
        if reponse.status_code >= 400:
            raise SourceIndisponible(
                f"AELF a répondu {reponse.status_code} pour {url}"
            )

        contenu: Any
        if json_attendu:
            try:
                contenu = reponse.json()
            except ValueError as erreur:
                raise SourceIndisponible(
                    f"Réponse AELF illisible (JSON attendu) : {url}"
                ) from erreur
        else:
            contenu = reponse.text

        self.cache.ecrire(cle, contenu)
        return contenu

    # ------------------------------------------------------------------
    # Offices du jour
    # ------------------------------------------------------------------

    def url_messe(self, jour: Date | str, zone: str | None = None) -> str:
        """URL publique de la messe, au format demandé dans le cahier des charges."""
        jour = self._normaliser_date(jour)
        return f"{AELF_WEB}/{jour}/{zone or self.cfg.zone}/messe"

    def messe(self, jour: Date | str | None = None, zone: str | None = None) -> dict[str, Any]:
        """Lectures de la messe d'un jour donné.

        Retourne les informations liturgiques (fête, couleur, degré) et la liste
        des lectures normalisées.
        """
        jour = self._normaliser_date(jour or Date.today())
        zone = zone or self.cfg.zone
        brut = self._get(f"{AELF_API}/messes/{jour}/{zone}", json_attendu=True)

        informations = brut.get("informations") or {}
        url_publique = self.url_messe(jour, zone)

        lectures: list[Lecture] = []
        for messe in brut.get("messes") or []:
            nom_messe = messe.get("nom") or ""
            for entree in messe.get("lectures") or []:
                lectures.append(self._normaliser_lecture(entree, nom_messe, url_publique))

        if not lectures:
            raise SourceIndisponible(
                f"AELF n'a publié aucune lecture pour le {jour} (zone {zone})."
            )

        return {
            "date": jour,
            "zone": zone,
            "url": url_publique,
            "fete": informations.get("fete") or informations.get("ligne1") or "",
            "couleur": informations.get("couleur") or "",
            "degre": informations.get("degre") or "",
            "lectures": [lecture.to_dict() for lecture in lectures],
        }

    def _normaliser_lecture(
        self, entree: dict[str, Any], nom_messe: str, url: str
    ) -> Lecture:
        # Selon le type de lecture, AELF place le texte dans « contenu »
        # (lectures, évangile) ou dans « texte » (psaume).
        texte = _nettoyer(entree.get("contenu") or entree.get("texte") or "")
        refrain = _nettoyer(entree.get("refrain_psalmique") or "")
        titre = entree.get("titre") or ""
        if nom_messe and nom_messe.lower() not in titre.lower():
            titre = f"{titre} ({nom_messe})" if titre else nom_messe
        return Lecture(
            type=entree.get("type") or "lecture",
            titre=_nettoyer(titre),
            reference=entree.get("ref") or "",
            texte=texte,
            refrain=refrain,
            url=url,
        )

    @staticmethod
    def _normaliser_date(jour: Date | str) -> str:
        if isinstance(jour, Date):
            return jour.isoformat()
        jour = jour.strip()
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", jour):
            raise ValueError(f"Date attendue au format AAAA-MM-JJ, reçu : {jour!r}")
        return jour

    # ------------------------------------------------------------------
    # Navigateur biblique
    # ------------------------------------------------------------------

    def url_chapitre(self, code_livre: str, chapitre: int) -> str:
        return f"{AELF_WEB}/bible/{code_livre}/{chapitre}"

    def chapitre(self, code_livre: str, chapitre: int, nom_livre: str = "") -> Passage:
        """Texte intégral d'un chapitre, versets numérotés."""
        url = self.url_chapitre(code_livre, chapitre)
        html = self._get(url, json_attendu=False)
        versets = _extraire_versets(html)
        if not versets:
            raise SourceIndisponible(
                f"Aucun verset extrait de {url}. La mise en page d'AELF a "
                "probablement changé : adapter `_extraire_versets`."
            )
        return Passage(
            livre=code_livre,
            nom_livre=nom_livre or code_livre,
            chapitre=chapitre,
            versets=versets,
            url=url,
        )


# ----------------------------------------------------------------------
# Extraction du texte biblique depuis le HTML AELF
# ----------------------------------------------------------------------

_MOTIF_NUMERO = re.compile(r"^\s*(\d{1,3})\s*[.)]?\s*")


def _extraire_versets(html: str) -> list[tuple[int, str]]:
    """Extrait les couples (numéro, texte) d'une page de chapitre AELF.

    Trois stratégies, de la plus structurée à la plus tolérante. La première qui
    donne un résultat crédible gagne.
    """
    for strategie in (_versets_par_classe, _versets_par_numero_en_tete, _versets_par_paragraphe):
        # Chaque stratégie repart d'une analyse neuve : elles retirent des
        # nœuds au passage, et travailler sur un arbre déjà entamé fausserait
        # la suivante.
        versets = strategie(BeautifulSoup(html, "lxml"))
        if len(versets) >= 2:
            return versets
    return []


# Zones à écarter avant toute extraction. La première est la plus importante :
# `block-summary` est le sommaire des chapitres d'AELF (« chapitre 1 »,
# « chapitre 2 »…). Sans cette exclusion, il est pris pour un verset, dont le
# numéro est celui du chapitre courant — et il écrase alors le vrai verset.
_ZONES_HORS_TEXTE = (
    ".block-summary",
    "nav",
    "header",
    "footer",
    ".menu-secondary-mobile",
    ".social",
    ".links",
    "script",
    "style",
)

# Zones de contenu, de la plus précise à la plus large. Les deux premières sont
# celles qu'AELF emploie réellement pour le texte biblique.
_ZONES_DE_TEXTE = (
    "div#right-col.block-single-reading",
    "div.block-single-reading",
    "div.container-reading",
    "div.bible-content",
    "div#contenu",
    "article",
    "main",
    "div#content",
    "div.content",
)


def _conteneur_principal(soupe: BeautifulSoup):
    """Isole la zone du texte, débarrassée du sommaire et des menus."""
    for selecteur in _ZONES_HORS_TEXTE:
        for indesirable in soupe.select(selecteur):
            indesirable.decompose()

    for selecteur in _ZONES_DE_TEXTE:
        zone = soupe.select_one(selecteur)
        if zone is not None and zone.get_text(strip=True):
            return zone
    return soupe


def _versets_par_classe(soupe: BeautifulSoup) -> list[tuple[int, str]]:
    """Cas nominal : chaque verset porte une classe dédiée et un numéro balisé."""
    versets: list[tuple[int, str]] = []
    zone = _conteneur_principal(soupe)
    noeuds = zone.select("[class*=verse], [class*=verset]")
    for noeud in noeuds:
        classes = " ".join(noeud.get("class") or [])
        # On saute les nœuds qui ne portent QUE le numéro : ils sont lus depuis
        # le verset parent.
        if re.search(r"(number|numero|num)\b", classes):
            continue
        balise_numero = noeud.select_one("[class*=number], [class*=numero], sup, .v")
        numero = _lire_numero(balise_numero.get_text() if balise_numero else "")
        if balise_numero is not None:
            balise_numero.extract()
        texte = _nettoyer(str(noeud))
        if numero is None:
            numero, texte = _detacher_numero(texte)
        if numero is not None and texte:
            versets.append((numero, texte))
    return _dedupliquer(versets)


def _versets_par_numero_en_tete(soupe: BeautifulSoup) -> list[tuple[int, str]]:
    """Variante : les numéros sont des <sup>/<b> en tête de chaque verset."""
    versets: list[tuple[int, str]] = []
    zone = _conteneur_principal(soupe)
    for paragraphe in zone.find_all(["p", "div"], recursive=True):
        if paragraphe.find(["p", "div"]):
            continue  # on ne garde que les feuilles
        marqueur = paragraphe.find(["sup", "b", "strong", "span"])
        if marqueur is None:
            continue
        numero = _lire_numero(marqueur.get_text())
        if numero is None:
            continue
        marqueur.extract()
        texte = _nettoyer(str(paragraphe))
        if texte:
            versets.append((numero, texte))
    return _dedupliquer(versets)


def _versets_par_paragraphe(soupe: BeautifulSoup) -> list[tuple[int, str]]:
    """Dernier recours : le numéro est simplement le premier mot du paragraphe."""
    versets: list[tuple[int, str]] = []
    zone = _conteneur_principal(soupe)
    for paragraphe in zone.find_all("p"):
        numero, texte = _detacher_numero(_nettoyer(str(paragraphe)))
        if numero is not None and texte:
            versets.append((numero, texte))
    return _dedupliquer(versets)


def _lire_numero(brut: str) -> int | None:
    correspondance = re.search(r"\d{1,3}", brut or "")
    return int(correspondance.group()) if correspondance else None


def _detacher_numero(texte: str) -> tuple[int | None, str]:
    correspondance = _MOTIF_NUMERO.match(texte)
    if not correspondance:
        return None, texte
    return int(correspondance.group(1)), texte[correspondance.end():].strip()


def _dedupliquer(versets: Iterable[tuple[int, str]]) -> list[tuple[int, str]]:
    """Garde le premier texte rencontré pour chaque numéro, dans l'ordre de lecture."""
    vus: dict[int, str] = {}
    for numero, texte in versets:
        if numero not in vus:
            vus[numero] = texte
    return sorted(vus.items())
