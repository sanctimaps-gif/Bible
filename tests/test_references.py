"""Analyse des références bibliques."""

from app.corpus.references import analyser, extraire_toutes


def test_reference_simple():
    reference = analyser("Jn 3, 16")
    assert reference is not None
    assert reference.livre.code == "Jn"
    assert reference.chapitre == 3
    assert reference.versets == ((16, 16),)
    assert str(reference) == "Jn 3, 16"


def test_intervalle_de_versets():
    reference = analyser("Rm 12, 1-5")
    assert reference.livre.code == "Rm"
    assert reference.versets == ((1, 5),)
    assert reference.contient(3)
    assert not reference.contient(6)


def test_tranches_multiples():
    reference = analyser("Mt 5, 3-12.17")
    assert reference.versets == ((3, 12), (17, 17))
    assert reference.contient(17)
    assert not reference.contient(15)


def test_chapitre_entier():
    reference = analyser("1 Co 13")
    assert reference.livre.code == "1Co"
    assert reference.chapitre == 13
    assert reference.chapitre_entier
    assert reference.contient(999)


def test_nom_complet_et_accents():
    for graphie in ("Genèse 22, 1-19", "genese 22, 1-19", "Livre de la Genèse 22, 1-19"):
        reference = analyser(graphie)
        assert reference is not None, graphie
        assert reference.livre.code == "Gn"
        assert reference.versets == ((1, 19),)


def test_psaume_a_double_numerotation():
    reference = analyser("Ps 22 (23)")
    assert reference.livre.code == "Ps"
    assert reference.chapitre == 22


def test_livre_a_chapitre_unique():
    # « Jude 5 » désigne le verset 5, pas un cinquième chapitre inexistant.
    reference = analyser("Jude 5")
    assert reference.chapitre == 1
    assert reference.versets == ((5, 5),)


def test_verset_avec_lettre():
    reference = analyser("Jn 3, 16a")
    assert reference.versets == ((16, 16),)


def test_chapitre_hors_limites_rejete():
    assert analyser("Jn 99") is None


def test_livre_inconnu_rejete():
    assert analyser("Hobbit 1, 1") is None
    assert analyser("") is None


def test_libelle_en_toutes_lettres():
    assert analyser("Jon 1").libelle() == "Livre de Jonas, chapitre 1"


def test_extraction_dans_un_texte_libre():
    texte = (
        "La deuxième lecture est tirée de Rm 12, 1-5, et l'évangile de "
        "Mt 5, 1-12. On lira aussi le Ps 23."
    )
    trouvees = {str(reference) for reference in extraire_toutes(texte)}
    assert "Rm 12, 1-5" in trouvees
    assert "Mt 5, 1-12" in trouvees
