"""La boucle de dialogue, avec un client Anthropic simulé.

Aucun appel réseau : on vérifie l'enchaînement question → outils → réponse,
la remontée des erreurs et le format des événements diffusés à l'interface.
"""

import json
from types import SimpleNamespace

import anthropic
import httpx
import pytest

from app.config import Config
from app.corpus.recherche import index
from app.ia.agent import AssistantBiblique, Evenement, Image, _libelle_appel
from app.ia.outils import BoiteAOutils
from app.sources.aelf import ClientAelf
from app.sources.sanctimaps import ClientSanctimaps

CORPUS = {
    "code": "Ep",
    "nom": "Lettre aux Éphésiens",
    "chapitres": {
        "4": [{"n": 25, "t": "Ne dites plus de mensonge ; que chacun dise la vérité."}]
    },
}


@pytest.fixture
def cfg(tmp_path) -> Config:
    configuration = Config(donnees=tmp_path)
    configuration.preparer_repertoires()
    (configuration.racine_bible / "Ep.json").write_text(
        json.dumps(CORPUS, ensure_ascii=False), encoding="utf-8"
    )
    index.cache_clear()
    yield configuration
    index.cache_clear()


# ----------------------------------------------------------------------
# Client Anthropic simulé
# ----------------------------------------------------------------------


def bloc_texte(texte: str) -> SimpleNamespace:
    return SimpleNamespace(type="text", text=texte)


def bloc_outil(identifiant: str, nom: str, entree: dict) -> SimpleNamespace:
    return SimpleNamespace(type="tool_use", id=identifiant, name=nom, input=entree)


class FluxSimule:
    def __init__(self, tour: dict):
        self._tour = tour

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    @property
    def text_stream(self):
        for bloc in self._tour["contenu"]:
            if bloc.type == "text":
                # Diffusion par fragments, comme le vrai flux.
                for morceau in bloc.text.split(" "):
                    yield morceau + " "

    def get_final_message(self):
        return SimpleNamespace(
            content=self._tour["contenu"],
            stop_reason=self._tour.get("stop_reason", "end_turn"),
        )


class ClientSimule:
    """Rejoue une liste de tours préparés, et note les requêtes reçues."""

    def __init__(self, tours: list[dict], erreur: Exception | None = None):
        self.tours = list(tours)
        self.erreur = erreur
        self.requetes: list[dict] = []
        self.messages = SimpleNamespace(stream=self._stream)

    def _stream(self, **arguments):
        if self.erreur is not None:
            raise self.erreur
        # L'assistant réutilise la même liste d'historique d'un tour à l'autre :
        # on en fige une copie, sinon toutes les requêtes notées pointeraient
        # vers l'état final.
        self.requetes.append({**arguments, "messages": list(arguments["messages"])})
        if not self.tours:
            raise AssertionError("Le modèle a été appelé plus de fois que prévu.")
        return FluxSimule(self.tours.pop(0))


@pytest.fixture
def outils(cfg) -> BoiteAOutils:
    def refuser(_requete: httpx.Request) -> httpx.Response:
        raise AssertionError("Aucun accès réseau ne doit être nécessaire ici.")

    transport = httpx.MockTransport(refuser)
    boite = BoiteAOutils(
        cfg,
        client_aelf=ClientAelf(cfg, client_http=httpx.Client(transport=transport)),
        client_sanctimaps=ClientSanctimaps(cfg, client_http=httpx.Client(transport=transport)),
    )
    yield boite
    boite.fermer()


def assistant_simule(cfg, outils, tours, erreur=None) -> tuple[AssistantBiblique, ClientSimule]:
    client = ClientSimule(tours, erreur)
    return AssistantBiblique(cfg, client=client, outils=outils), client


# ----------------------------------------------------------------------


def test_dialogue_avec_appel_d_outil(cfg, outils):
    tours = [
        {
            "contenu": [bloc_outil("t1", "chercher_ecriture", {"requete": "mensonge"})],
            "stop_reason": "tool_use",
        },
        {
            "contenu": [bloc_texte("Le Nouveau Testament condamne le mensonge.")],
            "stop_reason": "end_turn",
        },
    ]
    assistant, client = assistant_simule(cfg, outils, tours)
    evenements = list(assistant.dialoguer("Que dit le NT sur la tromperie ?"))

    types = [evenement.type for evenement in evenements]
    assert types[0] == "outil"
    assert types[1] == "resultat"
    assert "texte" in types
    assert types[-1] == "fin"

    assert evenements[0].donnees["outil"] == "chercher_ecriture"
    assert "1 verset" in evenements[1].contenu

    finale = evenements[-1]
    assert "Le Nouveau Testament condamne le mensonge." in finale.contenu
    assert finale.donnees["journal"][0]["outil"] == "chercher_ecriture"

    # Deux allers-retours, et le résultat d'outil a bien été renvoyé au modèle.
    assert len(client.requetes) == 2
    dernier_message = client.requetes[1]["messages"][-1]
    assert dernier_message["role"] == "user"
    assert dernier_message["content"][0]["type"] == "tool_result"
    assert dernier_message["content"][0]["tool_use_id"] == "t1"


def test_reponse_directe_sans_outil(cfg, outils):
    tours = [{"contenu": [bloc_texte("Je ne peux pas répondre à cela.")]}]
    assistant, _ = assistant_simule(cfg, outils, tours)
    assert assistant.repondre("Quelle météo demain ?") == "Je ne peux pas répondre à cela."


def test_plusieurs_outils_dans_un_meme_tour(cfg, outils):
    tours = [
        {
            "contenu": [
                bloc_outil("a", "chercher_ecriture", {"requete": "mensonge"}),
                bloc_outil("b", "lire_passage", {"reference": "Ep 4, 25"}),
            ],
            "stop_reason": "tool_use",
        },
        {"contenu": [bloc_texte("Voici.")]},
    ]
    assistant, client = assistant_simule(cfg, outils, tours)
    evenements = list(assistant.dialoguer("Le mensonge ?"))

    appels = [e for e in evenements if e.type == "outil"]
    assert [e.donnees["outil"] for e in appels] == ["chercher_ecriture", "lire_passage"]

    # Les deux résultats repartent dans un seul message utilisateur.
    resultats = client.requetes[1]["messages"][-1]["content"]
    assert len(resultats) == 2
    assert {r["tool_use_id"] for r in resultats} == {"a", "b"}


def test_parametres_de_la_requete(cfg, outils):
    assistant, client = assistant_simule(cfg, outils, [{"contenu": [bloc_texte("Bien.")]}])
    list(assistant.dialoguer("Bonjour"))

    requete = client.requetes[0]
    assert requete["model"] == cfg.modele
    assert requete["thinking"] == {"type": "adaptive"}
    assert requete["output_config"] == {"effort": cfg.effort}
    assert [outil["name"] for outil in requete["tools"]][0] == "chercher_ecriture"
    # Le prompt système est mis en cache sur son premier bloc.
    assert requete["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert "aelf.org" in requete["system"][0]["text"]
    assert "sanctimaps.fr" in requete["system"][0]["text"]


def test_image_placee_avant_la_consigne(cfg, outils):
    assistant, client = assistant_simule(cfg, outils, [{"contenu": [bloc_texte("Scène.")]}])
    image = Image(donnees=b"\x89PNG\r\n\x1a\n", type_mime="image/png")
    list(assistant.dialoguer("Quelle scène ?", image))

    contenu = client.requetes[0]["messages"][0]["content"]
    assert contenu[0]["type"] == "image"
    assert contenu[0]["source"]["media_type"] == "image/png"
    assert contenu[1]["type"] == "text"
    assert "Quelle scène ?" in contenu[1]["text"]
    assert "indices visuels" in contenu[1]["text"]


def test_boucle_bornee(cfg, outils):
    petite = Config(donnees=cfg.donnees, tours_max=3)
    tours = [
        {"contenu": [bloc_outil(f"t{n}", "chercher_ecriture", {"requete": "mensonge"})],
         "stop_reason": "tool_use"}
        for n in range(5)
    ]
    assistant, _ = assistant_simule(petite, outils, tours)
    evenements = list(assistant.dialoguer("Question sans fin"))
    assert evenements[-1].type == "erreur"
    assert "3 tours" in evenements[-1].contenu


def test_refus_du_modele_remonte(cfg, outils):
    tours = [{"contenu": [bloc_texte("")], "stop_reason": "refusal"}]
    assistant, _ = assistant_simule(cfg, outils, tours)
    evenements = list(assistant.dialoguer("…"))
    assert evenements[-1].type == "erreur"


def test_reponse_tronquee_signalee(cfg, outils):
    tours = [{"contenu": [bloc_texte("Début")], "stop_reason": "max_tokens"}]
    assistant, _ = assistant_simule(cfg, outils, tours)
    evenements = list(assistant.dialoguer("…"))
    assert evenements[-1].type == "erreur"
    assert "longueur" in evenements[-1].contenu


def test_cle_api_manquante_message_clair(cfg, outils):
    erreur = anthropic.AuthenticationError(
        "clé invalide",
        response=httpx.Response(401, request=httpx.Request("POST", "https://api.anthropic.com")),
        body=None,
    )
    assistant, _ = assistant_simule(cfg, outils, [], erreur)
    evenements = list(assistant.dialoguer("Bonjour"))
    assert evenements[-1].type == "erreur"
    assert "ANTHROPIC_API_KEY" in evenements[-1].contenu


def test_panne_reseau_message_clair(cfg, outils):
    erreur = anthropic.APIConnectionError(
        request=httpx.Request("POST", "https://api.anthropic.com")
    )
    assistant, _ = assistant_simule(cfg, outils, [], erreur)
    evenements = list(assistant.dialoguer("Bonjour"))
    assert evenements[-1].type == "erreur"
    assert "réseau" in evenements[-1].contenu


# ----------------------------------------------------------------------


def test_image_refuse_les_formats_non_pris_en_charge(tmp_path):
    fichier = tmp_path / "scene.bmp"
    fichier.write_bytes(b"BM")
    with pytest.raises(ValueError):
        Image.depuis_fichier(fichier)


def test_image_lue_depuis_un_fichier(tmp_path):
    fichier = tmp_path / "scene.png"
    fichier.write_bytes(b"\x89PNG\r\n\x1a\n")
    image = Image.depuis_fichier(fichier)
    assert image.type_mime == "image/png"
    assert image.bloc()["source"]["type"] == "base64"


@pytest.mark.parametrize(
    "nom,arguments,attendu",
    [
        ("chercher_ecriture", {"requete": "mensonge"}, "Recherche « mensonge » chez AELF"),
        ("chercher_ecriture", {"requete": "ruse", "testament": "nouveau"},
         "Recherche « ruse » dans le Nouveau Testament chez AELF"),
        ("lire_passage", {"reference": "Jon 1"}, "Lecture de Jon 1 chez AELF"),
        ("chercher_saint", {"nom": "Martin"}, "Recherche de « Martin » sur sanctimaps.fr"),
    ],
)
def test_libelles_lisibles(nom, arguments, attendu):
    assert _libelle_appel(nom, arguments) == attendu


def test_evenement_par_defaut():
    evenement = Evenement("texte", "bonjour")
    assert evenement.donnees == {}
