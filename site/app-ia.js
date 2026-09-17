// Interface de l'assistant biblique, version sans serveur.

import { dialoguer, ErreurApi, MODELE } from "./claude.js";

const CLE_STOCKAGE = "assistant-biblique.cle";

const elements = {
  accesCle: document.getElementById("acces-cle"),
  formulaireCle: document.getElementById("formulaire-cle"),
  champCle: document.getElementById("champ-cle"),
  oublierCle: document.getElementById("oublier-cle"),
  atelier: document.getElementById("atelier"),
  conversation: document.getElementById("conversation"),
  exemples: document.getElementById("exemples"),
  formulaire: document.getElementById("formulaire"),
  question: document.getElementById("question"),
  image: document.getElementById("image"),
  apercu: document.getElementById("apercu"),
  apercuImage: document.getElementById("apercu-image"),
  retirerImage: document.getElementById("retirer-image"),
  envoyer: document.getElementById("envoyer"),
  modele: document.getElementById("modele"),
};

let cle = null;
let enCours = false;
const historique = [];

// ---------------------------------------------------------------------------
// Clé d'accès
// ---------------------------------------------------------------------------

function chargerCle() {
  try {
    return localStorage.getItem(CLE_STOCKAGE);
  } catch {
    return null; // navigation privée, stockage bloqué
  }
}

function enregistrerCle(valeur) {
  try {
    localStorage.setItem(CLE_STOCKAGE, valeur);
  } catch {
    /* on continue sans mémoriser : la clé vaut pour cette session */
  }
}

function afficherEtat() {
  const connecte = Boolean(cle);
  elements.accesCle.hidden = connecte;
  elements.atelier.hidden = !connecte;
  elements.oublierCle.hidden = !connecte;
  if (connecte) elements.question.focus();
}

elements.formulaireCle.addEventListener("submit", (evenement) => {
  evenement.preventDefault();
  const valeur = elements.champCle.value.trim();
  if (!valeur) return;
  cle = valeur;
  enregistrerCle(valeur);
  elements.champCle.value = "";
  afficherEtat();
});

elements.oublierCle.addEventListener("click", () => {
  cle = null;
  try {
    localStorage.removeItem(CLE_STOCKAGE);
  } catch {
    /* rien à faire */
  }
  afficherEtat();
});

// ---------------------------------------------------------------------------
// Saisie
// ---------------------------------------------------------------------------

elements.question.addEventListener("input", () => {
  elements.question.style.height = "auto";
  elements.question.style.height = `${Math.min(elements.question.scrollHeight, 180)}px`;
});

elements.question.addEventListener("keydown", (evenement) => {
  if (evenement.key === "Enter" && !evenement.shiftKey) {
    evenement.preventDefault();
    elements.formulaire.requestSubmit();
  }
});

for (const bouton of document.querySelectorAll(".exemple")) {
  bouton.addEventListener("click", () => {
    elements.question.value = bouton.textContent.trim();
    elements.formulaire.requestSubmit();
  });
}

elements.image.addEventListener("change", () => {
  const fichier = elements.image.files[0];
  if (!fichier) return;
  elements.apercuImage.src = URL.createObjectURL(fichier);
  elements.apercu.hidden = false;
});

elements.retirerImage.addEventListener("click", () => {
  elements.image.value = "";
  elements.apercu.hidden = true;
});

async function lireImage(fichier) {
  const tampon = await fichier.arrayBuffer();
  let binaire = "";
  const octets = new Uint8Array(tampon);
  for (let i = 0; i < octets.length; i += 1) binaire += String.fromCharCode(octets[i]);
  return { type: fichier.type, donnees: btoa(binaire) };
}

// ---------------------------------------------------------------------------
// Rendu
// ---------------------------------------------------------------------------

function echapper(texte) {
  return texte
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

/** Rendu Markdown minimal : titres, gras, italique, listes, liens. */
function enrichir(texte) {
  const lignes = echapper(texte).split("\n");
  const sortie = [];
  let dansListe = false;

  const enligne = (ligne) =>
    ligne
      .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
      .replace(/(^|[^*])\*([^*\n]+)\*/g, "$1<em>$2</em>")
      .replace(/`([^`]+)`/g, "<code>$1</code>")
      .replace(
        /(https?:\/\/[^\s<)]+)/g,
        '<a href="$1" target="_blank" rel="noopener">$1</a>',
      );

  for (const ligne of lignes) {
    const titre = ligne.match(/^(#{1,4})\s+(.*)$/);
    const puce = ligne.match(/^\s*[-*•]\s+(.*)$/);

    if (puce) {
      if (!dansListe) {
        sortie.push("<ul>");
        dansListe = true;
      }
      sortie.push(`<li>${enligne(puce[1])}</li>`);
      continue;
    }
    if (dansListe) {
      sortie.push("</ul>");
      dansListe = false;
    }
    if (titre) {
      // Le titre de la page occupe déjà h1 et les libellés de section h2 :
      // les titres d'une réponse commencent donc à h3.
      const niveau = Math.min(Math.max(titre[1].length + 1, 3), 5);
      sortie.push(`<h${niveau}>${enligne(titre[2])}</h${niveau}>`);
    } else if (ligne.trim() === "") {
      sortie.push("");
    } else {
      sortie.push(`<p>${enligne(ligne)}</p>`);
    }
  }
  if (dansListe) sortie.push("</ul>");
  return sortie.join("\n");
}

function creerEchange(texte, fichier) {
  elements.exemples?.remove();

  const echange = document.createElement("article");
  echange.className = "echange";

  const bulle = document.createElement("div");
  bulle.className = "question";
  bulle.textContent = texte;
  if (fichier) {
    const vignette = document.createElement("img");
    vignette.src = URL.createObjectURL(fichier);
    vignette.alt = "Image jointe à la question";
    bulle.appendChild(vignette);
  }

  const etapes = document.createElement("div");
  etapes.className = "etapes";
  etapes.innerHTML = "<div>Recherche dans les sources…</div>";

  const reponse = document.createElement("div");
  reponse.className = "reponse curseur";

  echange.append(bulle, etapes, reponse);
  elements.conversation.appendChild(echange);
  echange.scrollIntoView({ behavior: "smooth", block: "start" });

  return { echange, etapes, reponse, vierge: true, texte: "" };
}

function ajouterEtape(vue, message, url) {
  if (vue.vierge) {
    vue.etapes.innerHTML = "";
    vue.vierge = false;
  }
  const ligne = document.createElement("div");
  if (url) {
    ligne.className = "lien";
    const ancre = document.createElement("a");
    ancre.href = url;
    ancre.target = "_blank";
    ancre.rel = "noopener";
    ancre.textContent = url;
    ligne.append("↳ ", ancre);
  } else {
    ligne.textContent = `→ ${message}`;
  }
  vue.etapes.appendChild(ligne);
}

function afficherErreur(vue, message) {
  vue.reponse.classList.remove("curseur");
  const bloc = document.createElement("p");
  bloc.className = "erreur";
  bloc.textContent = message;
  vue.echange.appendChild(bloc);
}

// ---------------------------------------------------------------------------
// Envoi
// ---------------------------------------------------------------------------

elements.formulaire.addEventListener("submit", async (evenement) => {
  evenement.preventDefault();
  if (enCours || !cle) return;

  const texte = elements.question.value.trim();
  if (!texte) return;

  const fichier = elements.image.files[0] || null;
  const vue = creerEchange(texte, fichier);

  elements.question.value = "";
  elements.question.style.height = "auto";
  elements.image.value = "";
  elements.apercu.hidden = true;
  basculer(true);

  try {
    const image = fichier ? await lireImage(fichier) : null;
    await dialoguer({
      cle,
      question: texte,
      image,
      historique,
      surEtape: (message, url) => ajouterEtape(vue, message, url),
      surTexte: (fragment) => {
        if (vue.vierge) {
          vue.etapes.remove();
          vue.vierge = false;
        }
        vue.texte += fragment;
        vue.reponse.innerHTML = enrichir(vue.texte);
      },
    });
    vue.reponse.classList.remove("curseur");
  } catch (erreur) {
    afficherErreur(
      vue,
      erreur instanceof ErreurApi ? erreur.message : String(erreur?.message || erreur),
    );
    // Une erreur laisse l'historique dans un état incohérent : on repart net.
    historique.length = 0;
  } finally {
    basculer(false);
  }
});

function basculer(actif) {
  enCours = actif;
  elements.envoyer.disabled = actif;
  elements.envoyer.textContent = actif ? "…" : "Envoyer";
}

// ---------------------------------------------------------------------------

elements.modele.textContent = MODELE;
cle = chargerCle();
afficherEtat();
