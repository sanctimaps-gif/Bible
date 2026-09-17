"""Index de recherche : découpage, pertinence et filtres."""

import pytest

from app.corpus.recherche import CorpusVide, IndexBiblique, Verset, decouper

CORPUS = [
    Verset("Ep", 4, 25, "Ne dites plus de mensonge ; que chacun dise la vérité à son prochain."),
    Verset("Col", 3, 9, "Ne mentez pas les uns aux autres, car vous vous êtes dépouillés du vieil homme."),
    Verset("Gn", 3, 13, "Le serpent m'a trompée, et j'ai mangé."),
    Verset("Jon", 1, 3, "Mais Jonas se leva pour s'enfuir à Tarsis, loin du Seigneur."),
    Verset("Jon", 1, 4, "Le Seigneur lança sur la mer un vent violent."),
    Verset("Jon", 1, 5, "Les marins prirent peur et crièrent chacun vers son dieu."),
    Verset("Ps", 23, 1, "Le Seigneur est mon berger : je ne manque de rien."),
]


@pytest.fixture(scope="module")
def index() -> IndexBiblique:
    return IndexBiblique(CORPUS)


def test_decoupage_supprime_les_mots_vides_et_les_accents():
    jetons = decouper("Le Seigneur est mon berger")
    assert "seigne" in jetons          # « Seigneur » réduit à son radical
    assert "berger" in jetons
    assert "le" not in jetons
    assert "est" not in jetons


def test_radical_commun_aux_mots_de_meme_famille():
    # C'est ce qui permet à « tromperie » de trouver « trompée ».
    assert decouper("tromperie") == decouper("trompeur") == decouper("tromper")


def test_recherche_trouve_le_verset_attendu():
    index = IndexBiblique(CORPUS)
    resultats = index.chercher("mensonge")
    assert resultats
    assert resultats[0][0].reference == "Ep 4, 25"


def test_recherche_par_famille_de_mots(index):
    resultats = index.chercher("tromperie")
    references = [verset.reference for verset, _ in resultats]
    assert "Gn 3, 13" in references


def test_filtre_par_testament(index):
    resultats = index.chercher("mensonge", testament="ancien")
    for verset, _ in resultats:
        assert verset.livre.testament == "ancien"


def test_filtre_par_livre(index):
    resultats = index.chercher("Seigneur", codes_livres=["Jon"])
    assert resultats
    assert all(verset.code_livre == "Jon" for verset, _ in resultats)


def test_limite_respectee(index):
    assert len(index.chercher("Seigneur", limite=1)) <= 1


def test_requete_sans_correspondance(index):
    assert index.chercher("astrophysique quantique") == []


def test_requete_vide(index):
    assert index.chercher("   ") == []


def test_passage_par_tranche(index):
    versets = index.passage("Jon", 1, debut=3, fin=4)
    assert [verset.numero for verset in versets] == [3, 4]


def test_contexte_autour_d_un_verset(index):
    verset = CORPUS[4]  # Jon 1, 4
    voisins = [v.numero for v in index.contexte(verset, marge=1)]
    assert voisins == [3, 4, 5]


def test_corpus_vide_refuse():
    with pytest.raises(CorpusVide):
        IndexBiblique([])


def test_conversion_en_dictionnaire(index):
    donnees = CORPUS[0].to_dict()
    assert donnees["reference"] == "Ep 4, 25"
    assert donnees["testament"] == "nouveau"
    assert donnees["url"].startswith("https://www.aelf.org/bible/Ep/4")
