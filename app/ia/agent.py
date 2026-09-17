"""La boucle de dialogue : question → recherches → réponse rédigée.

On écrit la boucle d'outils à la main plutôt que d'utiliser le `tool_runner` du
SDK, pour deux raisons : on veut diffuser en direct ce que l'assistant est en
train de chercher (l'interface affiche « lecture de Jonas 1… »), et on veut
garder la main sur le nombre de tours.
"""

from __future__ import annotations

import base64
import mimetypes
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

import anthropic

from ..config import Config, config
from .outils import DEFINITIONS, BoiteAOutils
from .prompts import prompt_systeme

TYPES_IMAGE_ACCEPTES = {"image/jpeg", "image/png", "image/gif", "image/webp"}


@dataclass
class Image:
    """Une image de scène biblique soumise par l'utilisateur."""

    donnees: bytes
    type_mime: str

    @classmethod
    def depuis_fichier(cls, chemin: str | Path) -> "Image":
        chemin = Path(chemin)
        type_mime, _ = mimetypes.guess_type(chemin.name)
        if type_mime == "image/jpg":
            type_mime = "image/jpeg"
        if type_mime not in TYPES_IMAGE_ACCEPTES:
            raise ValueError(
                f"Format d'image non pris en charge : {type_mime or 'inconnu'}. "
                f"Formats acceptés : {', '.join(sorted(TYPES_IMAGE_ACCEPTES))}."
            )
        return cls(donnees=chemin.read_bytes(), type_mime=type_mime)

    def bloc(self) -> dict[str, Any]:
        return {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": self.type_mime,
                "data": base64.standard_b64encode(self.donnees).decode("ascii"),
            },
        }


@dataclass
class Evenement:
    """Ce que la boucle émet au fil de l'eau, pour l'interface."""

    type: str  # « outil », « resultat », « texte », « fin », « erreur »
    contenu: str = ""
    donnees: dict[str, Any] = field(default_factory=dict)


CONSIGNE_IMAGE = (
    "L'utilisateur joint une image. Identifie la scène biblique qu'elle "
    "représente en suivant la méthode prévue : relève les indices visuels, "
    "formule des hypothèses, puis vérifie chacune dans le texte d'AELF avant de "
    "conclure."
)


class AssistantBiblique:
    """Assistant de questions-réponses adossé à AELF et sanctimaps.fr."""

    def __init__(
        self,
        cfg: Config | None = None,
        client: anthropic.Anthropic | None = None,
        outils: BoiteAOutils | None = None,
    ) -> None:
        self.cfg = cfg or config
        self.client = client or anthropic.Anthropic()
        self.outils = outils or BoiteAOutils(self.cfg)
        self.historique: list[dict[str, Any]] = []

    def fermer(self) -> None:
        self.outils.fermer()

    def __enter__(self) -> "AssistantBiblique":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.fermer()

    # ------------------------------------------------------------------

    def repondre(self, question: str, image: Image | None = None) -> str:
        """Version simple : rend la réponse complète, sans diffusion."""
        morceaux: list[str] = []
        for evenement in self.dialoguer(question, image):
            if evenement.type == "texte":
                morceaux.append(evenement.contenu)
            elif evenement.type == "erreur":
                raise RuntimeError(evenement.contenu)
        return "".join(morceaux).strip()

    def dialoguer(self, question: str, image: Image | None = None) -> Iterator[Evenement]:
        """Traite une question et émet les étapes au fur et à mesure."""
        self.historique.append({"role": "user", "content": self._message_utilisateur(question, image)})

        reponse_texte: list[str] = []
        tours = 0

        while tours < self.cfg.tours_max:
            tours += 1
            try:
                message = yield from self._tour(reponse_texte)
            except anthropic.APIStatusError as erreur:
                yield Evenement("erreur", _message_erreur(erreur))
                return
            except anthropic.APIConnectionError:
                yield Evenement(
                    "erreur",
                    "Impossible de joindre l'API Anthropic. Vérifiez la connexion réseau.",
                )
                return

            if message.stop_reason == "refusal":
                yield Evenement(
                    "erreur",
                    "La requête a été déclinée par le modèle pour des raisons de sécurité.",
                )
                return

            if message.stop_reason == "max_tokens":
                yield Evenement(
                    "erreur",
                    "Réponse interrompue : limite de longueur atteinte. "
                    "Reformulez la question de façon plus ciblée.",
                )
                return

            self.historique.append({"role": "assistant", "content": message.content})

            appels = [bloc for bloc in message.content if bloc.type == "tool_use"]
            if not appels:
                yield Evenement(
                    "fin",
                    "".join(reponse_texte).strip(),
                    {"journal": list(self.outils.journal)},
                )
                return

            resultats = []
            for appel in appels:
                yield Evenement("outil", _libelle_appel(appel.name, appel.input),
                                {"outil": appel.name, "arguments": appel.input})
                brut = self.outils.executer(appel.name, dict(appel.input))
                resume = self.outils.journal[-1].get("resultat_court", "")
                yield Evenement("resultat", resume, {"outil": appel.name})
                resultats.append(
                    {"type": "tool_result", "tool_use_id": appel.id, "content": brut}
                )

            self.historique.append({"role": "user", "content": resultats})

        yield Evenement(
            "erreur",
            f"Recherche interrompue après {self.cfg.tours_max} tours sans conclusion. "
            "La question est peut-être trop large : essayez de la découper.",
        )

    # ------------------------------------------------------------------

    def _tour(self, reponse_texte: list[str]):
        """Un aller-retour avec le modèle, texte diffusé au fil de l'eau."""
        with self.client.messages.stream(
            model=self.cfg.modele,
            max_tokens=self.cfg.jetons_max,
            system=prompt_systeme(),
            messages=self.historique,
            tools=DEFINITIONS,
            thinking={"type": "adaptive"},
            output_config={"effort": self.cfg.effort},
        ) as flux:
            for fragment in flux.text_stream:
                reponse_texte.append(fragment)
                yield Evenement("texte", fragment)
            return flux.get_final_message()

    def _message_utilisateur(self, question: str, image: Image | None) -> Any:
        if image is None:
            return question
        # L'image d'abord : le modèle la regarde avant de lire la consigne.
        return [image.bloc(), {"type": "text", "text": f"{question}\n\n{CONSIGNE_IMAGE}"}]


def _libelle_appel(nom: str, arguments: dict[str, Any]) -> str:
    """Phrase lisible décrivant ce que l'assistant est en train de faire."""
    if nom == "chercher_ecriture":
        cible = arguments.get("testament")
        precision = f" dans le {cible.capitalize()} Testament" if cible else ""
        return f"Recherche « {arguments.get('requete', '')} »{precision} chez AELF"
    if nom == "lire_passage":
        return f"Lecture de {arguments.get('reference', '')} chez AELF"
    if nom == "lire_messe_du_jour":
        return f"Lecture de la messe du {arguments.get('date') or 'jour'} chez AELF"
    if nom == "chercher_saint":
        return f"Recherche de « {arguments.get('nom', '')} » sur sanctimaps.fr"
    if nom == "lister_livres":
        return "Consultation de la liste des livres bibliques"
    return f"Appel de {nom}"


def _message_erreur(erreur: anthropic.APIStatusError) -> str:
    if isinstance(erreur, anthropic.AuthenticationError):
        return (
            "Clé API Anthropic absente ou invalide. Renseignez ANTHROPIC_API_KEY "
            "(voir .env.example)."
        )
    if isinstance(erreur, anthropic.RateLimitError):
        return "Limite de débit atteinte auprès de l'API Anthropic. Réessayez dans un instant."
    if erreur.status_code >= 500:
        return f"L'API Anthropic a répondu {erreur.status_code}. Réessayez dans un instant."
    return f"Erreur de l'API Anthropic ({erreur.status_code}) : {erreur.message}"
