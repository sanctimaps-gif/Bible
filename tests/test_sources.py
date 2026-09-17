"""Clients AELF et sanctimaps : garde-fou de domaine, extraction, normalisation.

Aucun test ne sort sur le réseau : les réponses HTTP sont simulées avec le
transport de test de httpx. C'est aussi la façon la plus sûre de vérifier que
le code n'appelle jamais un domaine non autorisé.
"""

import httpx
import pytest

from app.config import Config
from app.sources.aelf import (
    ClientAelf,
    SourceIndisponible,
    SourceInterdite,
    _extraire_versets,
    _nettoyer,
    verifier_domaine,
)
from app.sources.sanctimaps import ClientSanctimaps


@pytest.fixture
def cfg(tmp_path) -> Config:
    return Config(donnees=tmp_path)


# ----------------------------------------------------------------------
# Garde-fou de domaine
# ----------------------------------------------------------------------


def test_domaines_autorises():
    verifier_domaine("https://www.aelf.org/2026-09-17/romain/messe", "aelf.org")
    verifier_domaine("https://api.aelf.org/v1/messes/2026-09-17/romain", "aelf.org")
    verifier_domaine("https://aelf.org/bible/Jn/3", "aelf.org")


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com/bible",
        "https://aelf.org.pirate.net/bible/Jn/3",   # suffixe trompeur
        "https://notaelf.org/bible/Jn/3",
        "https://sanctimaps.fr/saint/martin",       # bon site, mauvais client
    ],
)
def test_domaines_refuses(url):
    with pytest.raises(SourceInterdite):
        verifier_domaine(url, "aelf.org")


def test_client_refuse_une_url_hors_source(cfg):
    client = ClientAelf(cfg)
    with pytest.raises(SourceInterdite):
        client._get("https://example.com/vole-du-texte", json_attendu=False)


# ----------------------------------------------------------------------
# Nettoyage du HTML liturgique
# ----------------------------------------------------------------------


def test_nettoyage_preserve_les_ruptures_de_vers():
    html = "<p>Le Seigneur est mon berger :<br>je ne manque de rien.</p>"
    assert _nettoyer(html) == "Le Seigneur est mon berger :\nje ne manque de rien."


def test_nettoyage_supprime_les_espaces_insecables():
    assert _nettoyer("<p>Jonas : prophète</p>") == "Jonas : prophète"


def test_nettoyage_d_une_chaine_vide():
    assert _nettoyer("") == ""


# ----------------------------------------------------------------------
# Extraction des versets — les trois stratégies
# ----------------------------------------------------------------------


def test_extraction_versets_balises():
    html = """
    <div class="bible-content">
      <div class="verse"><span class="verse_number">1</span>Au commencement, Dieu créa le ciel et la terre.</div>
      <div class="verse"><span class="verse_number">2</span>La terre était informe et vide.</div>
    </div>
    """
    assert _extraire_versets(html) == [
        (1, "Au commencement, Dieu créa le ciel et la terre."),
        (2, "La terre était informe et vide."),
    ]


def test_extraction_versets_numero_en_exposant():
    html = """
    <main>
      <p><sup>1</sup>Parole du Seigneur adressée à Jonas.</p>
      <p><sup>2</sup>Lève-toi, va à Ninive, la grande ville.</p>
    </main>
    """
    versets = _extraire_versets(html)
    assert versets[0] == (1, "Parole du Seigneur adressée à Jonas.")
    assert versets[1][0] == 2


def test_extraction_versets_numero_en_tete_de_paragraphe():
    html = """
    <article>
      <p>1. Heureux les pauvres de cœur.</p>
      <p>2. Heureux les doux.</p>
    </article>
    """
    assert _extraire_versets(html) == [
        (1, "Heureux les pauvres de cœur."),
        (2, "Heureux les doux."),
    ]


def test_extraction_echoue_proprement_sur_du_html_inattendu():
    assert _extraire_versets("<html><body><p>Page d'erreur</p></body></html>") == []


# ----------------------------------------------------------------------
# Messe du jour
# ----------------------------------------------------------------------

MESSE_SIMULEE = {
    "informations": {
        "date": "2026-09-17",
        "zone": "romain",
        "couleur": "vert",
        "fete": "Jeudi de la 24e semaine du Temps Ordinaire",
        "degre": "ferie",
    },
    "messes": [
        {
            "nom": "Messe du jour",
            "lectures": [
                {
                    "type": "lecture_1",
                    "titre": "« L'amour ne passera jamais »",
                    "ref": "1 Co 12, 31 – 13, 13",
                    "contenu": "<p>Frères,<br>recherchez les dons les plus grands.</p>",
                },
                {
                    "type": "psaume",
                    "titre": "Psaume 32",
                    "ref": "Ps 32 (33)",
                    "refrain_psalmique": "Heureux le peuple dont le Seigneur est le Dieu.",
                    "texte": "<p>Criez de joie pour le Seigneur.</p>",
                },
                {
                    "type": "evangile",
                    "titre": "« Ses péchés sont pardonnés »",
                    "ref": "Lc 7, 36-50",
                    "contenu": "<p>En ce temps-là, un pharisien invita Jésus.</p>",
                },
            ],
        }
    ],
}


def _client_simule(cfg, gestionnaire) -> ClientAelf:
    transport = httpx.MockTransport(gestionnaire)
    return ClientAelf(cfg, client_http=httpx.Client(transport=transport))


def test_messe_normalisee(cfg):
    def gestionnaire(requete: httpx.Request) -> httpx.Response:
        assert requete.url.host == "api.aelf.org"
        assert requete.url.path == "/v1/messes/2026-09-17/romain"
        return httpx.Response(200, json=MESSE_SIMULEE)

    with _client_simule(cfg, gestionnaire) as client:
        messe = client.messe("2026-09-17", "romain")

    assert messe["fete"].startswith("Jeudi")
    assert messe["url"] == "https://www.aelf.org/2026-09-17/romain/messe"
    assert len(messe["lectures"]) == 3

    premiere = messe["lectures"][0]
    assert premiere["reference"] == "1 Co 12, 31 – 13, 13"
    assert premiere["texte"] == "Frères,\nrecherchez les dons les plus grands."

    psaume = messe["lectures"][1]
    assert psaume["refrain"] == "Heureux le peuple dont le Seigneur est le Dieu."
    assert psaume["texte"] == "Criez de joie pour le Seigneur."  # lu depuis « texte »


def test_url_messe_correspond_au_format_du_site(cfg):
    client = ClientAelf(cfg)
    assert client.url_messe("2026-09-17", "romain") == (
        "https://www.aelf.org/2026-09-17/romain/messe"
    )


def test_date_mal_formee_refusee(cfg):
    client = ClientAelf(cfg)
    with pytest.raises(ValueError):
        client.messe("17/09/2026")


def test_messe_sans_lecture_signale_une_indisponibilite(cfg):
    def gestionnaire(_requete: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"informations": {}, "messes": []})

    with _client_simule(cfg, gestionnaire) as client:
        with pytest.raises(SourceIndisponible):
            client.messe("2026-09-17")


def test_erreur_http_remontee(cfg):
    def gestionnaire(_requete: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    with _client_simule(cfg, gestionnaire) as client:
        with pytest.raises(SourceIndisponible):
            client.messe("2026-09-17")


def test_reponse_mise_en_cache(cfg):
    appels = {"nombre": 0}

    def gestionnaire(_requete: httpx.Request) -> httpx.Response:
        appels["nombre"] += 1
        return httpx.Response(200, json=MESSE_SIMULEE)

    with _client_simule(cfg, gestionnaire) as client:
        client.messe("2026-09-17")
        client.messe("2026-09-17")

    assert appels["nombre"] == 1  # la seconde lecture vient du cache


def test_chapitre_biblique(cfg):
    html = """
    <div class="bible-content">
      <div class="verse"><span class="verse_number">1</span>Parole du Seigneur adressée à Jonas.</div>
      <div class="verse"><span class="verse_number">2</span>Lève-toi, va à Ninive.</div>
    </div>
    """

    def gestionnaire(requete: httpx.Request) -> httpx.Response:
        assert requete.url.path == "/bible/Jon/1"
        return httpx.Response(200, html=html)

    with _client_simule(cfg, gestionnaire) as client:
        passage = client.chapitre("Jon", 1, "Livre de Jonas")

    assert passage.versets[0][1] == "Parole du Seigneur adressée à Jonas."
    assert passage.url == "https://www.aelf.org/bible/Jon/1"
    assert passage.texte.startswith("1. Parole du Seigneur")


def test_chapitre_illisible_signale(cfg):
    def gestionnaire(_requete: httpx.Request) -> httpx.Response:
        return httpx.Response(200, html="<html><body>Maintenance</body></html>")

    with _client_simule(cfg, gestionnaire) as client:
        with pytest.raises(SourceIndisponible):
            client.chapitre("Jon", 1)


# ----------------------------------------------------------------------
# sanctimaps.fr
# ----------------------------------------------------------------------


def test_recherche_de_saint(cfg):
    resultats_html = """
    <main>
      <article><a href="/saints/martin-de-tours">Saint Martin de Tours</a></article>
    </main>
    """
    fiche_html = """
    <article>
      <h1>Saint Martin de Tours</h1>
      <p>Soldat romain devenu évêque de Tours, il partage son manteau avec un pauvre.</p>
    </article>
    """

    def gestionnaire(requete: httpx.Request) -> httpx.Response:
        assert requete.url.host == "sanctimaps.fr"
        if requete.url.path == "/saints/martin-de-tours":
            return httpx.Response(200, html=fiche_html)
        return httpx.Response(200, html=resultats_html)

    client = ClientSanctimaps(cfg, client_http=httpx.Client(transport=httpx.MockTransport(gestionnaire)))
    with client:
        fiches = client.chercher("Martin de Tours")

    assert len(fiches) == 1
    assert fiches[0].titre == "Saint Martin de Tours"
    assert "évêque de Tours" in fiches[0].texte
    assert fiches[0].url == "https://sanctimaps.fr/saints/martin-de-tours"


def test_sanctimaps_refuse_les_liens_sortants(cfg):
    resultats_html = """
    <main>
      <article>
        <a href="https://fr.wikipedia.org/wiki/Martin_de_Tours">Wikipédia</a>
        <a href="/saints/martin">Fiche interne</a>
      </article>
    </main>
    """

    vus: list[str] = []

    def gestionnaire(requete: httpx.Request) -> httpx.Response:
        vus.append(str(requete.url))
        if requete.url.path == "/saints/martin":
            return httpx.Response(200, html="<article><h1>Martin</h1><p>Sa vie.</p></article>")
        return httpx.Response(200, html=resultats_html)

    client = ClientSanctimaps(cfg, client_http=httpx.Client(transport=httpx.MockTransport(gestionnaire)))
    with client:
        client.chercher("Martin")

    assert all("wikipedia" not in url for url in vus)


def test_le_sommaire_des_chapitres_n_est_pas_pris_pour_un_verset():
    """Régression : AELF place un sommaire « chapitre 1, 2, 3… » à côté du texte.

    Il était absorbé comme un verset, numéroté d'après le chapitre courant, et
    écrasait alors le vrai verset de ce numéro.
    """
    html = """
    <body class="front_bible_chapter">
      <div id="content" class="container">
        <div class="row">
          <div class="col-md-3 col-sm-9">
            <div class="block-summary">
              <a href="/bible/Jon/1" class="active">chapitre 1</a>
              <a href="/bible/Jon/2">chapitre 2</a>
              <a href="/bible/Jon/3">chapitre 3</a>
              <a href="/bible/Jon/4">chapitre 4</a>
            </div>
          </div>
          <div class="col-md-7 col-sm-9 container-reading">
            <div id="right-col" class="block-single-reading">
              <p><sup>1</sup>Parole du Seigneur adressée à Jonas.</p>
              <p><sup>2</sup>Lève-toi, va à Ninive, la grande ville.</p>
              <p><sup>3</sup>Jonas se leva, mais pour s'enfuir à Tarsis.</p>
            </div>
          </div>
        </div>
      </div>
    </body>
    """
    versets = _extraire_versets(html)

    assert [numero for numero, _ in versets] == [1, 2, 3]
    assert versets[0][1] == "Parole du Seigneur adressée à Jonas."
    assert all("chapitre" not in texte for _, texte in versets)


def test_les_menus_ne_polluent_pas_le_texte():
    html = """
    <body>
      <header><a href="/">L'AELF</a><a href="/abonner">S'abonner</a></header>
      <nav><a href="/calendrier">Calendrier</a></nav>
      <div id="right-col" class="block-single-reading">
        <p><sup>1</sup>Au commencement, Dieu créa le ciel et la terre.</p>
        <p><sup>2</sup>La terre était informe et vide.</p>
      </div>
      <footer><a href="/contact">Contact</a></footer>
    </body>
    """
    versets = _extraire_versets(html)
    assert versets == [
        (1, "Au commencement, Dieu créa le ciel et la terre."),
        (2, "La terre était informe et vide."),
    ]
