"""Les outils dont dispose le modèle — sa seule fenêtre sur le monde.

Chaque outil est une fonction Python qui ne parle qu'aux sources autorisées et
rend du JSON. Le modèle n'a aucun autre moyen d'obtenir un texte : c'est ce qui
rend la contrainte « une seule source » effective, et pas seulement déclarative.
"""

from __future__ import annotations

import json
from datetime import date as Date
from typing import Any

from ..config import Config, config
from ..corpus import recherche
from ..corpus.livres import LIVRES, trouver_livre
from ..corpus.recherche import CorpusVide
from ..corpus.references import Reference, analyser
from ..sources.aelf import ClientAelf, SourceIndisponible
from ..sources.sanctimaps import ClientSanctimaps

# ----------------------------------------------------------------------
# Déclarations envoyées à l'API (ordre stable : il conditionne le cache)
# ----------------------------------------------------------------------

DEFINITIONS: list[dict[str, Any]] = [
    {
        "name": "chercher_ecriture",
        "description": (
            "Cherche des versets dans le texte biblique publié par AELF. "
            "Utilise les mots du texte biblique, pas ceux de la question : pour "
            "« tromperie », essaie « mensonge », « tromper », « séduire », "
            "« hypocrisie », « ruse ». Relance plusieurs recherches avec des "
            "formulations différentes plutôt qu'une seule recherche large."
        ),
        "input_schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "requete": {
                    "type": "string",
                    "description": "Mots-clés ou expression à chercher, en français.",
                },
                "testament": {
                    "type": ["string", "null"],
                    "enum": ["ancien", "nouveau", None],
                    "description": "Restreint la recherche à un testament. null = les deux.",
                },
                "livres": {
                    "type": ["array", "null"],
                    "items": {"type": "string"},
                    "description": (
                        "Restreint à certains livres, par code ou par nom "
                        "(« Mt », « Matthieu », « Lettre aux Romains »). null = tous."
                    ),
                },
                "limite": {
                    "type": ["integer", "null"],
                    "description": "Nombre maximal de versets rendus (défaut 12, maximum 40).",
                },
            },
            "required": ["requete", "testament", "livres", "limite"],
        },
    },
    {
        "name": "lire_passage",
        "description": (
            "Lit un passage biblique chez AELF à partir de sa référence "
            "(« Jn 3, 16 », « Rm 12, 1-5 », « Genèse 22 », « 1 Co 13 »). "
            "Sans numéros de verset, rend le chapitre entier. À utiliser "
            "systématiquement avant de citer, pour lire le passage en contexte."
        ),
        "input_schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "reference": {
                    "type": "string",
                    "description": "Référence biblique en français, ex. « Jon 1, 1-16 ».",
                },
                "marge": {
                    "type": ["integer", "null"],
                    "description": (
                        "Nombre de versets à ajouter avant et après la tranche "
                        "demandée, pour le contexte (défaut 0, maximum 10)."
                    ),
                },
            },
            "required": ["reference", "marge"],
        },
    },
    {
        "name": "lire_messe_du_jour",
        "description": (
            "Lit les lectures de la messe d'un jour donné sur AELF : fête "
            "célébrée, première lecture, psaume, deuxième lecture et évangile, "
            "avec leurs références."
        ),
        "input_schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "date": {
                    "type": ["string", "null"],
                    "description": "Date au format AAAA-MM-JJ. null = aujourd'hui.",
                },
                "zone": {
                    "type": ["string", "null"],
                    "description": (
                        "Zone liturgique : romain, france, afrique, belgique, "
                        "luxembourg, suisse, canada. null = zone configurée."
                    ),
                },
            },
            "required": ["date", "zone"],
        },
    },
    {
        "name": "chercher_saint",
        "description": (
            "Cherche un saint sur sanctimaps.fr — l'unique source autorisée pour "
            "les questions d'hagiographie (vie, martyre, patronage, lieux, fête). "
            "Ne jamais répondre sur un saint sans passer par cet outil."
        ),
        "input_schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "nom": {
                    "type": "string",
                    "description": "Nom du saint, ex. « saint Martin de Tours ».",
                },
            },
            "required": ["nom"],
        },
    },
    {
        "name": "lister_livres",
        "description": (
            "Liste les livres bibliques disponibles chez AELF, avec leur code, "
            "leur nombre de chapitres et leur section. Utile pour situer un "
            "prophète ou vérifier l'orthographe d'un code avant `lire_passage`."
        ),
        "input_schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "testament": {
                    "type": ["string", "null"],
                    "enum": ["ancien", "nouveau", None],
                    "description": "Filtre par testament. null = tous.",
                },
                "section": {
                    "type": ["string", "null"],
                    "description": "Filtre par section, ex. « Prophètes », « Évangiles ».",
                },
            },
            "required": ["testament", "section"],
        },
    },
]


class BoiteAOutils:
    """Exécute les appels d'outils du modèle contre les sources autorisées."""

    def __init__(
        self,
        cfg: Config | None = None,
        client_aelf: ClientAelf | None = None,
        client_sanctimaps: ClientSanctimaps | None = None,
    ) -> None:
        self.cfg = cfg or config
        self.aelf = client_aelf or ClientAelf(self.cfg)
        self.sanctimaps = client_sanctimaps or ClientSanctimaps(self.cfg)
        self.journal: list[dict[str, Any]] = []

    def fermer(self) -> None:
        self.aelf.fermer()
        self.sanctimaps.fermer()

    # ------------------------------------------------------------------

    def executer(self, nom: str, arguments: dict[str, Any]) -> str:
        """Point d'entrée unique. Rend toujours du JSON, même en cas d'erreur."""
        methodes = {
            "chercher_ecriture": self._chercher_ecriture,
            "lire_passage": self._lire_passage,
            "lire_messe_du_jour": self._lire_messe_du_jour,
            "chercher_saint": self._chercher_saint,
            "lister_livres": self._lister_livres,
        }
        methode = methodes.get(nom)
        if methode is None:
            return _json({"erreur": f"Outil inconnu : {nom}"})

        self.journal.append({"outil": nom, "arguments": arguments})
        try:
            resultat = methode(arguments)
        except (SourceIndisponible, CorpusVide) as erreur:
            resultat = {"erreur": str(erreur), "trouve": False}
        except ValueError as erreur:
            resultat = {"erreur": str(erreur), "trouve": False}
        self.journal[-1]["resultat_court"] = _resume(resultat)
        return _json(resultat)

    # ------------------------------------------------------------------
    # Implémentations
    # ------------------------------------------------------------------

    def _chercher_ecriture(self, arguments: dict[str, Any]) -> dict[str, Any]:
        requete = (arguments.get("requete") or "").strip()
        if not requete:
            return {"erreur": "Requête vide.", "trouve": False}

        if not recherche.index_disponible(self.cfg):
            return {
                "erreur": (
                    "Le corpus biblique local n'a pas encore été téléchargé depuis "
                    "AELF. La recherche plein texte est indisponible ; `lire_passage` "
                    "reste utilisable si tu connais la référence. "
                    "(Administrateur : lancer `python scripts/ingerer_bible.py`.)"
                ),
                "trouve": False,
            }

        limite = arguments.get("limite") or 12
        limite = max(1, min(int(limite), 40))

        codes: list[str] | None = None
        if arguments.get("livres"):
            codes = []
            for nom in arguments["livres"]:
                livre = trouver_livre(nom)
                if livre is not None:
                    codes.append(livre.code)
            if not codes:
                return {
                    "erreur": f"Aucun livre reconnu parmi : {arguments['livres']}",
                    "trouve": False,
                }

        index = recherche.index(self.cfg)
        resultats = index.chercher(
            requete,
            limite=limite,
            testament=arguments.get("testament"),
            codes_livres=codes,
        )

        if not resultats:
            return {
                "trouve": False,
                "requete": requete,
                "message": (
                    "Aucun verset ne correspond. Essaie d'autres mots : le "
                    "vocabulaire de la traduction liturgique diffère souvent de "
                    "celui de la question."
                ),
            }

        return {
            "trouve": True,
            "requete": requete,
            "nombre": len(resultats),
            "versets": [
                {**verset.to_dict(), "score": round(score, 2)} for verset, score in resultats
            ],
        }

    def _lire_passage(self, arguments: dict[str, Any]) -> dict[str, Any]:
        brut = (arguments.get("reference") or "").strip()
        reference = analyser(brut)
        if reference is None:
            return {
                "erreur": (
                    f"Référence incomprise : {brut!r}. Format attendu : "
                    "« Jn 3, 16 », « Rm 12, 1-5 » ou « Genèse 22 »."
                ),
                "trouve": False,
            }

        marge = max(0, min(int(arguments.get("marge") or 0), 10))
        versets = self._versets_du_passage(reference, marge)
        if not versets:
            return {
                "trouve": False,
                "reference": str(reference),
                "message": f"AELF ne publie pas de texte pour {reference}.",
            }

        return {
            "trouve": True,
            "reference": str(reference),
            "libelle": reference.libelle(),
            "livre": reference.livre.nom,
            "testament": reference.livre.testament,
            "url": self.aelf.url_chapitre(reference.livre.code, reference.chapitre),
            "versets": versets,
        }

    def _versets_du_passage(self, reference: Reference, marge: int) -> list[dict[str, Any]]:
        """Sert le passage depuis le corpus local, sinon le télécharge chez AELF."""
        code = reference.livre.code

        if recherche.index_disponible(self.cfg):
            try:
                index = recherche.index(self.cfg)
                trouves = index.passage(code, reference.chapitre)
                if trouves:
                    return _filtrer(
                        [{"numero": v.numero, "texte": v.texte} for v in trouves],
                        reference,
                        marge,
                    )
            except CorpusVide:
                pass

        passage = self.aelf.chapitre(code, reference.chapitre, reference.livre.nom)
        return _filtrer(
            [{"numero": n, "texte": t} for n, t in passage.versets], reference, marge
        )

    def _lire_messe_du_jour(self, arguments: dict[str, Any]) -> dict[str, Any]:
        jour = arguments.get("date") or Date.today().isoformat()
        messe = self.aelf.messe(jour, arguments.get("zone"))
        return {"trouve": True, **messe}

    def _chercher_saint(self, arguments: dict[str, Any]) -> dict[str, Any]:
        nom = (arguments.get("nom") or "").strip()
        if not nom:
            return {"erreur": "Nom vide.", "trouve": False}
        fiches = self.sanctimaps.chercher(nom)
        if not fiches:
            return {
                "trouve": False,
                "nom": nom,
                "message": f"sanctimaps.fr ne donne aucun résultat pour « {nom} ».",
            }
        return {
            "trouve": True,
            "nom": nom,
            "source": "sanctimaps.fr",
            "fiches": [fiche.to_dict() for fiche in fiches],
        }

    def _lister_livres(self, arguments: dict[str, Any]) -> dict[str, Any]:
        testament = arguments.get("testament")
        section = (arguments.get("section") or "").strip().lower()
        livres = [
            {
                "code": livre.code,
                "nom": livre.nom,
                "chapitres": livre.chapitres,
                "testament": livre.testament,
                "section": livre.section,
            }
            for livre in LIVRES
            if (not testament or livre.testament == testament)
            and (not section or section in livre.section.lower())
        ]
        return {"trouve": bool(livres), "nombre": len(livres), "livres": livres}


# ----------------------------------------------------------------------


def _filtrer(
    versets: list[dict[str, Any]], reference: Reference, marge: int
) -> list[dict[str, Any]]:
    """Restreint aux versets demandés, en ajoutant la marge de contexte."""
    if reference.chapitre_entier:
        return versets
    bornes: list[tuple[int, int]] = [
        (max(1, debut - marge), fin + marge) for debut, fin in reference.versets
    ]
    return [
        verset
        for verset in versets
        if any(debut <= verset["numero"] <= fin for debut, fin in bornes)
    ]


def _json(donnees: Any) -> str:
    return json.dumps(donnees, ensure_ascii=False)


def _resume(resultat: Any) -> str:
    """Résumé d'une ligne pour le journal (affiché dans l'interface)."""
    if not isinstance(resultat, dict):
        return ""
    if resultat.get("erreur"):
        return f"erreur : {resultat['erreur'][:120]}"
    if "versets" in resultat and isinstance(resultat["versets"], list):
        return f"{len(resultat['versets'])} verset(s)"
    if "lectures" in resultat:
        return f"{len(resultat['lectures'])} lecture(s) — {resultat.get('fete', '')}"
    if "fiches" in resultat:
        return f"{len(resultat['fiches'])} fiche(s) sanctimaps"
    if "livres" in resultat:
        return f"{resultat.get('nombre', 0)} livre(s)"
    return "sans résultat" if resultat.get("trouve") is False else "ok"
