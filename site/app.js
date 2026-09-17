// La Bible — application statique, sans serveur, sans compte, sans IA.
//
// Tout ce qu'elle affiche vient de fichiers déposés dans `site/donnees/` par le
// workflow « Corpus AELF », qui les télécharge depuis aelf.org. La page ne fait
// que lire ses propres fichiers : aucune requête vers un autre domaine, donc
// aucun blocage inter-domaines, aucune clé, aucune dépendance extérieure.

import { Index, souligner } from "./recherche.js";

const DONNEES = "site/donnees";
const AELF = "https://www.aelf.org";

const elements = {
  onglets: document.querySelectorAll(".onglet"),
  vues: {
    messe: document.getElementById("vue-messe"),
    recherche: document.getElementById("vue-recherche"),
    lire: document.getElementById("vue-lire"),
  },
  messeTitre: document.getElementById("messe-titre"),
  messeDate: document.getElementById("messe-date"),
  messeContenu: document.getElementById("messe-contenu"),
  jourPrecedent: document.getElementById("jour-precedent"),
  jourSuivant: document.getElementById("jour-suivant"),
  formulaireRecherche: document.getElementById("formulaire-recherche"),
  champRecherche: document.getElementById("champ-recherche"),
  resultats: document.getElementById("resultats"),
  suggestions: document.getElementById("suggestions"),
  choixLivre: document.getElementById("choix-livre"),
  choixChapitre: document.getElementById("choix-chapitre"),
  chapitreContenu: document.getElementById("chapitre-contenu"),
  etatCorpus: document.getElementById("etat-corpus"),
};

const etat = {
  catalogue: null,
  parCode: new Map(),
  index: null,
  chargementIndex: null,
  jour: new Date(),
  datesMesse: null,
};

// ---------------------------------------------------------------------------
// Outils
// ---------------------------------------------------------------------------

async function lireJson(chemin) {
  const reponse = await fetch(`${DONNEES}/${chemin}`, { cache: "no-cache" });
  if (!reponse.ok) throw new Error(`${chemin} : ${reponse.status}`);
  return reponse.json();
}

function iso(date) {
  // Date locale, sans décalage de fuseau : les lectures d'un jour sont celles
  // du jour tel que le lecteur le vit, pas celui de Greenwich.
  const decalage = date.getTimezoneOffset() * 60_000;
  return new Date(date.getTime() - decalage).toISOString().slice(0, 10);
}

function enFrancais(date) {
  return date.toLocaleDateString("fr-FR", {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
  });
}

function echapper(texte) {
  return texte.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function vider(noeud) {
  while (noeud.firstChild) noeud.removeChild(noeud.firstChild);
}

function message(noeud, texte, classe = "patiente") {
  vider(noeud);
  const paragraphe = document.createElement("p");
  paragraphe.className = classe;
  paragraphe.textContent = texte;
  noeud.appendChild(paragraphe);
}

/** Lien vers la page d'origine, chez AELF. */
function lienAelf(url, libelle) {
  const ancre = document.createElement("a");
  ancre.href = url;
  ancre.target = "_blank";
  ancre.rel = "noopener";
  ancre.className = "source";
  ancre.textContent = libelle;
  return ancre;
}

// ---------------------------------------------------------------------------
// Onglets
// ---------------------------------------------------------------------------

function montrer(nom) {
  for (const [cle, vue] of Object.entries(elements.vues)) vue.hidden = cle !== nom;
  for (const onglet of elements.onglets) {
    onglet.classList.toggle("actif", onglet.dataset.vue === nom);
  }
  if (nom === "recherche") elements.champRecherche.focus();
  if (nom === "lire" && !elements.choixLivre.options.length) remplirLivres();
  history.replaceState(null, "", `#${nom}`);
}

for (const onglet of elements.onglets) {
  onglet.addEventListener("click", () => montrer(onglet.dataset.vue));
}

// ---------------------------------------------------------------------------
// Lectures de la messe
// ---------------------------------------------------------------------------

const TITRES_LECTURE = {
  lecture_1: "Première lecture",
  lecture_2: "Deuxième lecture",
  psaume: "Psaume",
  evangile: "Évangile",
  cantique: "Cantique",
  sequence: "Séquence",
};

async function afficherMesse() {
  const date = iso(etat.jour);
  elements.messeDate.textContent = enFrancais(etat.jour);
  message(elements.messeContenu, "Chargement…");

  let messe;
  try {
    messe = await lireJson(`messe/${date}.json`);
  } catch {
    elements.messeTitre.textContent = "Lectures du jour";
    vider(elements.messeContenu);

    const explication = document.createElement("p");
    explication.className = "vide";
    explication.textContent = etat.datesMesse?.length
      ? "Les lectures de ce jour ne sont pas encore disponibles ici."
      : "Les lectures n'ont pas encore été téléchargées.";
    elements.messeContenu.appendChild(explication);
    elements.messeContenu.appendChild(
      lienAelf(`${AELF}/${date}/romain/messe`, "Les lire sur aelf.org"),
    );
    return;
  }

  elements.messeTitre.textContent = messe.fete || "Messe du jour";
  vider(elements.messeContenu);

  if (messe.couleur) {
    const couleur = document.createElement("p");
    couleur.className = "fine couleur";
    couleur.textContent = `Couleur liturgique : ${messe.couleur}`;
    elements.messeContenu.appendChild(couleur);
  }

  for (const lecture of messe.lectures) {
    const article = document.createElement("article");
    article.className = "lecture";

    const entete = document.createElement("h3");
    entete.textContent = TITRES_LECTURE[lecture.type] || lecture.type;
    article.appendChild(entete);

    if (lecture.reference) {
      const reference = document.createElement("p");
      reference.className = "reference";
      reference.textContent = lecture.reference;
      article.appendChild(reference);
    }

    if (lecture.titre) {
      const titre = document.createElement("p");
      titre.className = "titre-lecture";
      titre.textContent = lecture.titre;
      article.appendChild(titre);
    }

    if (lecture.refrain) {
      const refrain = document.createElement("p");
      refrain.className = "refrain";
      refrain.textContent = lecture.refrain;
      article.appendChild(refrain);
    }

    const corps = document.createElement("div");
    corps.className = "texte-lecture";
    corps.textContent = lecture.texte;
    article.appendChild(corps);

    elements.messeContenu.appendChild(article);
  }

  elements.messeContenu.appendChild(
    lienAelf(messe.url || `${AELF}/${date}/romain/messe`, "Voir sur aelf.org"),
  );
}

function decalerJour(jours) {
  etat.jour = new Date(etat.jour.getTime() + jours * 86_400_000);
  afficherMesse();
}

elements.jourPrecedent.addEventListener("click", () => decalerJour(-1));
elements.jourSuivant.addEventListener("click", () => decalerJour(1));

// ---------------------------------------------------------------------------
// Recherche
// ---------------------------------------------------------------------------

/** Charge le corpus et construit l'index — une seule fois, à la demande. */
function chargerIndex() {
  if (etat.index) return Promise.resolve(etat.index);
  if (etat.chargementIndex) return etat.chargementIndex;

  etat.chargementIndex = lireJson("corpus.json")
    .then((versets) => {
      etat.index = new Index(versets);
      return etat.index;
    })
    .catch((erreur) => {
      etat.chargementIndex = null;
      throw erreur;
    });
  return etat.chargementIndex;
}

elements.formulaireRecherche.addEventListener("submit", async (evenement) => {
  evenement.preventDefault();
  await lancerRecherche(elements.champRecherche.value.trim());
});

for (const pastille of document.querySelectorAll(".pastille")) {
  pastille.addEventListener("click", () => {
    elements.champRecherche.value = pastille.dataset.recherche;
    lancerRecherche(pastille.dataset.recherche);
  });
}

for (const bouton of document.querySelectorAll('input[name="testament"]')) {
  bouton.addEventListener("change", () => {
    const requete = elements.champRecherche.value.trim();
    if (requete) lancerRecherche(requete);
  });
}

async function lancerRecherche(requete) {
  if (!requete) return;
  elements.suggestions.hidden = true;
  message(elements.resultats, "Recherche…");

  let index;
  try {
    index = await chargerIndex();
  } catch {
    vider(elements.resultats);
    const erreur = document.createElement("p");
    erreur.className = "vide";
    erreur.textContent =
      "Le texte biblique n'a pas encore été téléchargé. La recherche sera " +
      "disponible dès que ce sera fait.";
    elements.resultats.appendChild(erreur);
    return;
  }

  const testament =
    document.querySelector('input[name="testament"]:checked').value || null;

  const trouves = index.chercher(requete, { testament, livres: etat.parCode });
  afficherResultats(requete, trouves);
}

function afficherResultats(requete, trouves) {
  vider(elements.resultats);

  const entete = document.createElement("p");
  entete.className = "compte";
  entete.textContent = trouves.length
    ? `${trouves.length} passage${trouves.length > 1 ? "s" : ""} pour « ${requete} »`
    : `Aucun passage ne contient « ${requete} ».`;
  elements.resultats.appendChild(entete);

  if (!trouves.length) {
    const piste = document.createElement("p");
    piste.className = "astuce";
    piste.textContent =
      "Essayez un autre mot : la traduction liturgique emploie souvent un " +
      "vocabulaire différent de celui de la question.";
    elements.resultats.appendChild(piste);
    return;
  }

  for (const resultat of trouves) {
    const livre = etat.parCode.get(resultat.code);
    const article = document.createElement("article");
    article.className = "resultat";

    const reference = document.createElement("a");
    reference.className = "reference";
    reference.href = `${AELF}/bible/${resultat.code}/${resultat.chapitre}`;
    reference.target = "_blank";
    reference.rel = "noopener";
    reference.textContent = `${resultat.code} ${resultat.chapitre}, ${resultat.numero}`;
    article.appendChild(reference);

    const nom = document.createElement("span");
    nom.className = "nom-livre";
    nom.textContent = livre ? livre.nom : resultat.code;
    article.appendChild(nom);

    const texte = document.createElement("p");
    texte.className = "verset";
    texte.innerHTML = souligner(resultat.texte, requete);
    article.appendChild(texte);

    const lire = document.createElement("button");
    lire.type = "button";
    lire.className = "lien-bouton";
    lire.textContent = "lire le chapitre";
    lire.addEventListener("click", () => {
      montrer("lire");
      ouvrirChapitre(resultat.code, resultat.chapitre, resultat.numero);
    });
    article.appendChild(lire);

    elements.resultats.appendChild(article);
  }
}

// ---------------------------------------------------------------------------
// Lecture suivie
// ---------------------------------------------------------------------------

function remplirLivres() {
  if (!etat.catalogue) return;
  vider(elements.choixLivre);

  let sectionCourante = null;
  let groupe = null;

  for (const livre of etat.catalogue) {
    if (!livre.disponibles.length) continue;
    if (livre.section !== sectionCourante) {
      sectionCourante = livre.section;
      groupe = document.createElement("optgroup");
      groupe.label = sectionCourante;
      elements.choixLivre.appendChild(groupe);
    }
    const option = document.createElement("option");
    option.value = livre.code;
    option.textContent = livre.nom;
    groupe.appendChild(option);
  }

  if (!elements.choixLivre.options.length) {
    message(
      elements.chapitreContenu,
      "Le texte biblique n'a pas encore été téléchargé.",
      "vide",
    );
    return;
  }

  elements.choixLivre.addEventListener("change", () => {
    remplirChapitres(elements.choixLivre.value);
    ouvrirChapitre(elements.choixLivre.value, Number(elements.choixChapitre.value));
  });
  elements.choixChapitre.addEventListener("change", () => {
    ouvrirChapitre(elements.choixLivre.value, Number(elements.choixChapitre.value));
  });

  remplirChapitres(elements.choixLivre.value);
  ouvrirChapitre(elements.choixLivre.value, Number(elements.choixChapitre.value));
}

function remplirChapitres(code) {
  const livre = etat.parCode.get(code);
  vider(elements.choixChapitre);
  for (const numero of livre?.disponibles || []) {
    const option = document.createElement("option");
    option.value = String(numero);
    option.textContent = `Chapitre ${numero}`;
    elements.choixChapitre.appendChild(option);
  }
}

async function ouvrirChapitre(code, chapitre, versetVise = null) {
  const livre = etat.parCode.get(code);
  if (!livre) return;

  elements.choixLivre.value = code;
  if (elements.choixChapitre.value !== String(chapitre)) {
    remplirChapitres(code);
    elements.choixChapitre.value = String(chapitre);
  }

  message(elements.chapitreContenu, "Chargement…");

  let donnees;
  try {
    donnees = await lireJson(`livres/${code}.json`);
  } catch {
    message(elements.chapitreContenu, "Ce livre n'est pas encore disponible.", "vide");
    return;
  }

  const versets = donnees.chapitres[String(chapitre)] || [];
  vider(elements.chapitreContenu);

  const titre = document.createElement("h2");
  titre.textContent = `${livre.nom} — chapitre ${chapitre}`;
  elements.chapitreContenu.appendChild(titre);

  const corps = document.createElement("div");
  corps.className = "chapitre";
  for (const verset of versets) {
    const ligne = document.createElement("p");
    ligne.className = "verset-numerote";
    ligne.id = `v${verset.n}`;
    if (versetVise === verset.n) ligne.classList.add("vise");
    ligne.innerHTML =
      `<span class="numero">${verset.n}</span>${echapper(verset.t)}`;
    corps.appendChild(ligne);
  }
  elements.chapitreContenu.appendChild(corps);
  elements.chapitreContenu.appendChild(
    lienAelf(`${AELF}/bible/${code}/${chapitre}`, "Voir sur aelf.org"),
  );

  if (versetVise) {
    document.getElementById(`v${versetVise}`)?.scrollIntoView({
      behavior: "smooth",
      block: "center",
    });
  }
}

// ---------------------------------------------------------------------------
// Démarrage
// ---------------------------------------------------------------------------

async function demarrer() {
  try {
    etat.catalogue = await lireJson("catalogue.json");
    for (const livre of etat.catalogue) etat.parCode.set(livre.code, livre);
  } catch {
    etat.catalogue = [];
  }

  try {
    etat.datesMesse = await lireJson("messe/index.json");
  } catch {
    etat.datesMesse = [];
  }

  const livresPrets = etat.catalogue.filter((livre) => livre.disponibles.length).length;
  const chapitresPrets = etat.catalogue.reduce(
    (total, livre) => total + livre.disponibles.length,
    0,
  );

  elements.etatCorpus.textContent = livresPrets
    ? `${livresPrets} livres et ${chapitresPrets} chapitres disponibles hors ligne, ` +
      `${etat.datesMesse.length} jour(s) de lectures.`
    : "Le texte est en cours de téléchargement depuis aelf.org ; " +
      "la page se remplira toute seule.";

  const vue = location.hash.slice(1);
  montrer(["messe", "recherche", "lire"].includes(vue) ? vue : "messe");
  afficherMesse();
}

demarrer();
