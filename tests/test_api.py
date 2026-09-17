"""Routes HTTP : état du service, messe du jour, diffusion en SSE."""

import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app import api
from app.config import Config
from app.corpus.recherche import index
from app.ia.agent import Evenement


@pytest.fixture
def client(tmp_path, monkeypatch) -> TestClient:
    # `Config` est figée : on remplace l'objet entier plutôt qu'un de ses champs.
    monkeypatch.setattr(api, "config", Config(donnees=tmp_path))
    index.cache_clear()
    yield TestClient(api.application)
    index.cache_clear()


class AssistantSimule:
    """Remplace l'assistant réel : aucune clé API, aucun appel réseau."""

    dernier_appel: dict = {}

    def __init__(self, *_args, **_kwargs):
        pass

    def dialoguer(self, question, image=None):
        AssistantSimule.dernier_appel = {"question": question, "image": image}
        yield Evenement("outil", "Recherche « mensonge » chez AELF", {"outil": "chercher_ecriture"})
        yield Evenement("texte", "Le mensonge est condamné.")
        yield Evenement("fin", "Le mensonge est condamné.", {"journal": []})

    def fermer(self):
        pass


def _evenements(reponse) -> list[dict]:
    charges = []
    for bloc in reponse.text.split("\n\n"):
        ligne = next((l for l in bloc.split("\n") if l.startswith("data: ")), None)
        if ligne:
            charges.append(json.loads(ligne[6:]))
    return charges


def test_etat(client):
    donnees = client.get("/api/etat").json()
    assert donnees["sources"] == ["aelf.org", "sanctimaps.fr"]
    assert donnees["livres_connus"] == 73


def test_page_d_accueil_servie(client):
    reponse = client.get("/")
    assert reponse.status_code == 200
    assert "Assistant biblique" in reponse.text


def test_question_diffusee_en_sse(client, monkeypatch):
    monkeypatch.setattr(api, "AssistantBiblique", AssistantSimule)
    reponse = client.post("/api/question", data={"texte": "Et la tromperie ?"})

    assert reponse.status_code == 200
    assert reponse.headers["content-type"].startswith("text/event-stream")

    evenements = _evenements(reponse)
    assert [e["type"] for e in evenements] == ["outil", "texte", "fin", "terminé"]
    assert evenements[1]["contenu"] == "Le mensonge est condamné."
    assert AssistantSimule.dernier_appel["question"] == "Et la tromperie ?"
    assert AssistantSimule.dernier_appel["image"] is None


def test_question_avec_image(client, monkeypatch):
    monkeypatch.setattr(api, "AssistantBiblique", AssistantSimule)
    reponse = client.post(
        "/api/question",
        data={"texte": "Quelle scène ?"},
        files={"image": ("scene.png", b"\x89PNG\r\n\x1a\n", "image/png")},
    )
    assert reponse.status_code == 200
    image = AssistantSimule.dernier_appel["image"]
    assert image is not None
    assert image.type_mime == "image/png"


def test_image_de_format_refuse(client, monkeypatch):
    monkeypatch.setattr(api, "AssistantBiblique", AssistantSimule)
    reponse = client.post(
        "/api/question",
        data={"texte": "Et ceci ?"},
        files={"image": ("scene.bmp", b"BM", "image/bmp")},
    )
    evenements = _evenements(reponse)
    assert evenements[0]["type"] == "erreur"
    assert "image/bmp" in evenements[0]["contenu"]


def test_erreur_interne_signalee_au_client(client, monkeypatch):
    class AssistantQuiPlante(AssistantSimule):
        def dialoguer(self, question, image=None):
            yield Evenement("texte", "Début")
            raise RuntimeError("panne inattendue")

    monkeypatch.setattr(api, "AssistantBiblique", AssistantQuiPlante)
    evenements = _evenements(client.post("/api/question", data={"texte": "…"}))
    assert evenements[-2]["type"] == "erreur"
    assert "panne inattendue" in evenements[-2]["contenu"]


def test_messe_du_jour(client, monkeypatch):
    charge = {
        "informations": {"fete": "Saint Robert Bellarmin"},
        "messes": [
            {
                "nom": "Messe du jour",
                "lectures": [
                    {"type": "evangile", "titre": "", "ref": "Lc 7, 36-50",
                     "contenu": "<p>Un pharisien invita Jésus.</p>"}
                ],
            }
        ],
    }

    def gestionnaire(requete: httpx.Request) -> httpx.Response:
        assert requete.url.host == "api.aelf.org"
        return httpx.Response(200, json=charge)

    class ClientAelfSimule(api.ClientAelf):
        def __init__(self, cfg):
            super().__init__(cfg, client_http=httpx.Client(transport=httpx.MockTransport(gestionnaire)))

    monkeypatch.setattr(api, "ClientAelf", ClientAelfSimule)
    donnees = client.get("/api/messe?date=2026-09-17").json()
    assert donnees["fete"] == "Saint Robert Bellarmin"
    assert donnees["url"] == "https://www.aelf.org/2026-09-17/romain/messe"


def test_messe_date_invalide(client, monkeypatch):
    donnees = client.get("/api/messe?date=17-09-2026").json()
    assert "erreur" in donnees
