"""La boîte à outils : c'est elle qui garantit qu'aucune réponse ne sort d'ailleurs."""

import json

import httpx
import pytest

from app.config import Config
from app.corpus.livres import LIVRES, PAR_CODE, trouver_livre
from app.corpus.recherche import index
from app.ia.outils import DEFINITIONS, BoiteAOutils
from app.sources.aelf import ClientAelf
from app.sources.sanctimaps import ClientSanctimaps

CORPUS_JONAS = {
    "code": "Jon",
    "nom": "Livre de Jonas",
    "chapitres": {
        "1": [
            {"n": 1, "t": "Parole du Seigneur adressée à Jonas, fils d'Amittaï."},
            {"n": 2, "t": "Lève-toi, va à Ninive, la grande ville, et proclame contre elle."},
            {"n": 3, "t": "Mais Jonas se leva pour s'enfuir à Tarsis, loin du Seigneur."},
            {"n": 4, "t": "Le Seigneur lança sur la mer un vent violent."},
            {"n": 5, "t": "Les marins prirent peur et jetèrent la cargaison à la mer."},
        ]
    },
}

CORPUS_EPHESIENS = {
    "code": "Ep",
    "nom": "Lettre aux Éphésiens",
    "chapitres": {
        "4": [
            {"n": 25, "t": "Ne dites plus de mensonge ; que chacun dise la vérité à son prochain."},
        ]
    },
}


@pytest.fixture
def cfg(tmp_path) -> Config:
    configuration = Config(donnees=tmp_path)
    configuration.preparer_repertoires()
    for livre in (CORPUS_JONAS, CORPUS_EPHESIENS):
        (configuration.racine_bible / f"{livre['code']}.json").write_text(
            json.dumps(livre, ensure_ascii=False), encoding="utf-8"
        )
    index.cache_clear()  # l'index est mémorisé par processus
    yield configuration
    index.cache_clear()


@pytest.fixture
def outils(cfg) -> BoiteAOutils:
    def aelf(_requete: httpx.Request) -> httpx.Response:
        raise AssertionError("Le corpus local doit suffire pour ces cas.")

    boite = BoiteAOutils(
        cfg,
        client_aelf=ClientAelf(cfg, client_http=httpx.Client(transport=httpx.MockTransport(aelf))),
        client_sanctimaps=ClientSanctimaps(
            cfg, client_http=httpx.Client(transport=httpx.MockTransport(aelf))
        ),
    )
    yield boite
    boite.fermer()


def _appeler(outils: BoiteAOutils, nom: str, **arguments) -> dict:
    return json.loads(outils.executer(nom, arguments))


# ----------------------------------------------------------------------


def test_les_definitions_sont_coherentes():
    for definition in DEFINITIONS:
        schema = definition["input_schema"]
        assert definition["description"].strip()
        assert schema["additionalProperties"] is False
        # Tout paramètre déclaré doit être documenté et requis.
        assert set(schema["required"]) == set(schema["properties"])
        for propriete in schema["properties"].values():
            assert propriete.get("description"), definition["name"]


def test_recherche_dans_le_corpus(outils):
    resultat = _appeler(outils, "chercher_ecriture", requete="mensonge")
    assert resultat["trouve"] is True
    assert resultat["versets"][0]["reference"] == "Ep 4, 25"
    assert resultat["versets"][0]["url"].startswith("https://www.aelf.org/bible/Ep/4")


def test_recherche_filtree_par_testament(outils):
    resultat = _appeler(outils, "chercher_ecriture", requete="Seigneur", testament="ancien")
    assert resultat["trouve"] is True
    assert all(verset["testament"] == "ancien" for verset in resultat["versets"])


def test_recherche_filtree_par_livre_nomme_en_francais(outils):
    resultat = _appeler(outils, "chercher_ecriture", requete="Seigneur", livres=["Jonas"])
    assert all(verset["reference"].startswith("Jon") for verset in resultat["versets"])


def test_recherche_sans_resultat_le_dit(outils):
    resultat = _appeler(outils, "chercher_ecriture", requete="photosynthèse")
    assert resultat["trouve"] is False
    assert "message" in resultat


def test_recherche_livre_inconnu(outils):
    resultat = _appeler(outils, "chercher_ecriture", requete="Seigneur", livres=["Silmarillion"])
    assert resultat["trouve"] is False
    assert "erreur" in resultat


def test_lecture_d_un_passage(outils):
    resultat = _appeler(outils, "lire_passage", reference="Jon 1, 3")
    assert resultat["trouve"] is True
    assert resultat["reference"] == "Jon 1, 3"
    assert [verset["numero"] for verset in resultat["versets"]] == [3]
    assert "Tarsis" in resultat["versets"][0]["texte"]


def test_lecture_avec_marge_de_contexte(outils):
    resultat = _appeler(outils, "lire_passage", reference="Jon 1, 3", marge=1)
    assert [verset["numero"] for verset in resultat["versets"]] == [2, 3, 4]


def test_lecture_d_un_chapitre_entier(outils):
    resultat = _appeler(outils, "lire_passage", reference="Jon 1")
    assert len(resultat["versets"]) == 5


def test_reference_incomprise(outils):
    resultat = _appeler(outils, "lire_passage", reference="quelque part vers la fin")
    assert resultat["trouve"] is False
    assert "erreur" in resultat


def test_liste_des_livres(outils):
    resultat = _appeler(outils, "lister_livres", testament="nouveau")
    assert resultat["nombre"] == 27
    resultat = _appeler(outils, "lister_livres", section="Prophètes")
    codes = {livre["code"] for livre in resultat["livres"]}
    assert {"Is", "Jr", "Ez", "Dn", "Jon"} <= codes


def test_outil_inconnu(outils):
    assert "erreur" in _appeler(outils, "chercher_sur_internet", requete="x")


def test_le_journal_retrace_les_appels(outils):
    _appeler(outils, "chercher_ecriture", requete="mensonge")
    _appeler(outils, "lire_passage", reference="Jon 1, 3")
    assert [entree["outil"] for entree in outils.journal] == [
        "chercher_ecriture",
        "lire_passage",
    ]
    assert all("resultat_court" in entree for entree in outils.journal)


def test_corpus_absent_signale_sans_planter(tmp_path):
    vide = Config(donnees=tmp_path / "vide")
    index.cache_clear()
    boite = BoiteAOutils(vide)
    try:
        resultat = json.loads(boite.executer("chercher_ecriture", {"requete": "mensonge"}))
    finally:
        boite.fermer()
        index.cache_clear()
    assert resultat["trouve"] is False
    assert "ingerer_bible" in resultat["erreur"]


def test_passage_absent_du_corpus_est_telecharge(cfg):
    """Un chapitre non ingéré doit être lu chez AELF, pas inventé."""
    html = """
    <div class="bible-content">
      <div class="verse"><span class="verse_number">16</span>Dieu a tant aimé le monde.</div>
      <div class="verse"><span class="verse_number">17</span>Car Dieu a envoyé son Fils.</div>
    </div>
    """
    appels: list[str] = []

    def gestionnaire(requete: httpx.Request) -> httpx.Response:
        appels.append(str(requete.url))
        return httpx.Response(200, html=html)

    boite = BoiteAOutils(
        cfg,
        client_aelf=ClientAelf(cfg, client_http=httpx.Client(transport=httpx.MockTransport(gestionnaire))),
    )
    try:
        resultat = json.loads(boite.executer("lire_passage", {"reference": "Jn 3, 16"}))
    finally:
        boite.fermer()

    assert resultat["trouve"] is True
    assert resultat["versets"] == [{"numero": 16, "texte": "Dieu a tant aimé le monde."}]
    assert appels == ["https://www.aelf.org/bible/Jn/3"]


def test_messe_du_jour(cfg):
    charge = {
        "informations": {"fete": "Saint Robert Bellarmin", "couleur": "blanc"},
        "messes": [
            {
                "nom": "Messe du jour",
                "lectures": [
                    {"type": "evangile", "titre": "L'évangile", "ref": "Lc 7, 36-50",
                     "contenu": "<p>Un pharisien invita Jésus.</p>"}
                ],
            }
        ],
    }

    def gestionnaire(requete: httpx.Request) -> httpx.Response:
        assert requete.url.host == "api.aelf.org"
        return httpx.Response(200, json=charge)

    boite = BoiteAOutils(
        cfg,
        client_aelf=ClientAelf(cfg, client_http=httpx.Client(transport=httpx.MockTransport(gestionnaire))),
    )
    try:
        resultat = json.loads(boite.executer("lire_messe_du_jour", {"date": "2026-09-17"}))
    finally:
        boite.fermer()

    assert resultat["fete"] == "Saint Robert Bellarmin"
    assert resultat["url"] == "https://www.aelf.org/2026-09-17/romain/messe"
    assert resultat["lectures"][0]["texte"] == "Un pharisien invita Jésus."


def test_recherche_de_saint_passe_par_sanctimaps(cfg):
    def gestionnaire(requete: httpx.Request) -> httpx.Response:
        assert requete.url.host == "sanctimaps.fr"
        if requete.url.path == "/saints/jeanne-d-arc":
            return httpx.Response(
                200, html="<article><h1>Sainte Jeanne d'Arc</h1><p>Née à Domrémy.</p></article>"
            )
        return httpx.Response(
            200, html='<main><article><a href="/saints/jeanne-d-arc">Jeanne d\'Arc</a></article></main>'
        )

    boite = BoiteAOutils(
        cfg,
        client_sanctimaps=ClientSanctimaps(
            cfg, client_http=httpx.Client(transport=httpx.MockTransport(gestionnaire))
        ),
    )
    try:
        resultat = json.loads(boite.executer("chercher_saint", {"nom": "Jeanne d'Arc"}))
    finally:
        boite.fermer()

    assert resultat["trouve"] is True
    assert resultat["source"] == "sanctimaps.fr"
    assert "Domrémy" in resultat["fiches"][0]["texte"]


# ----------------------------------------------------------------------
# Table des livres
# ----------------------------------------------------------------------


def test_le_canon_est_complet():
    assert len(LIVRES) == 73
    assert len([livre for livre in LIVRES if livre.testament == "nouveau"]) == 27
    assert len([livre for livre in LIVRES if livre.testament == "ancien"]) == 46


def test_codes_uniques():
    codes = [livre.code for livre in LIVRES]
    assert len(codes) == len(set(codes))
    assert set(PAR_CODE) == set(codes)


@pytest.mark.parametrize(
    "graphie,attendu",
    [
        ("Rm", "Rm"),
        ("romains", "Rm"),
        ("Lettre aux Romains", "Rm"),
        ("Isaïe", "Is"),
        ("isaie", "Is"),
        ("Ecclésiaste", "Qo"),
        ("Siracide", "Si"),
        ("Ecclésiastique", "Si"),
        ("1 Corinthiens", "1Co"),
        ("Apocalypse", "Ap"),
        ("Cantique des cantiques", "Ct"),
        ("Maccabées", None),  # ambigu sans numéro : on ne devine pas
    ],
)
def test_resolution_des_noms_de_livres(graphie, attendu):
    livre = trouver_livre(graphie)
    assert (livre.code if livre else None) == attendu


def test_table_js_a_jour():
    """`site/livres.js` doit rester en phase avec `app/corpus/livres.py`.

    Les deux versions — serveur et navigateur — partagent la même table ; on
    l'engendre plutôt que de la tenir à jour deux fois.
    """
    import subprocess
    import sys
    from pathlib import Path

    racine = Path(__file__).resolve().parent.parent
    resultat = subprocess.run(
        [sys.executable, "scripts/exporter_livres.py", "--verifier"],
        cwd=racine,
        capture_output=True,
        text=True,
    )
    assert resultat.returncode == 0, resultat.stderr or resultat.stdout
