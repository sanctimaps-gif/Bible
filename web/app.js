// Interface de l'assistant biblique.
// Le serveur diffuse la réponse en Server-Sent Events : chaque événement dit
// soit ce que l'assistant est en train de chercher, soit un fragment de texte.

const formulaire = document.getElementById("formulaire");
const champQuestion = document.getElementById("question");
const champImage = document.getElementById("image");
const apercu = document.getElementById("apercu");
const apercuImage = document.getElementById("apercu-image");
const boutonRetirer = document.getElementById("retirer-image");
const boutonEnvoyer = document.getElementById("envoyer");
const conversation = document.getElementById("conversation");
const zoneEtat = document.getElementById("etat");

// --- État du service -------------------------------------------------------

fetch("/api/etat")
  .then((r) => r.json())
  .then((etat) => {
    if (etat.corpus_pret) {
      zoneEtat.textContent =
        `${etat.versets_indexes.toLocaleString("fr-FR")} versets indexés depuis aelf.org · modèle ${etat.modele}`;
    } else {
      zoneEtat.classList.add("alerte");
      zoneEtat.textContent =
        "Corpus biblique absent : la recherche par thème est indisponible. " +
        "Lancez « python scripts/ingerer_bible.py » pour l'installer.";
    }
  })
  .catch(() => {
    zoneEtat.classList.add("alerte");
    zoneEtat.textContent = "Service injoignable.";
  });

// --- Champ de saisie -------------------------------------------------------

champQuestion.addEventListener("input", () => {
  champQuestion.style.height = "auto";
  champQuestion.style.height = Math.min(champQuestion.scrollHeight, 180) + "px";
});

champQuestion.addEventListener("keydown", (evenement) => {
  if (evenement.key === "Enter" && !evenement.shiftKey) {
    evenement.preventDefault();
    formulaire.requestSubmit();
  }
});

document.querySelectorAll(".exemple").forEach((bouton) => {
  bouton.addEventListener("click", () => {
    champQuestion.value = bouton.textContent.trim();
    champQuestion.focus();
    formulaire.requestSubmit();
  });
});

champImage.addEventListener("change", () => {
  const fichier = champImage.files[0];
  if (!fichier) return;
  apercuImage.src = URL.createObjectURL(fichier);
  apercu.hidden = false;
});

boutonRetirer.addEventListener("click", () => {
  champImage.value = "";
  apercu.hidden = true;
});

// --- Envoi et diffusion ----------------------------------------------------

let enCours = false;

formulaire.addEventListener("submit", async (evenement) => {
  evenement.preventDefault();
  if (enCours) return;

  const texte = champQuestion.value.trim();
  if (!texte) return;

  const fichier = champImage.files[0] || null;
  const echange = afficherQuestion(texte, fichier);

  champQuestion.value = "";
  champQuestion.style.height = "auto";
  champImage.value = "";
  apercu.hidden = true;
  basculerEnvoi(true);

  const donnees = new FormData();
  donnees.append("texte", texte);
  if (fichier) donnees.append("image", fichier);

  try {
    const reponse = await fetch("/api/question", { method: "POST", body: donnees });
    if (!reponse.ok) throw new Error(`Le serveur a répondu ${reponse.status}`);
    await lireFlux(reponse.body, echange);
  } catch (erreur) {
    afficherErreur(echange, erreur.message);
  } finally {
    basculerEnvoi(false);
  }
});

function basculerEnvoi(actif) {
  enCours = actif;
  boutonEnvoyer.disabled = actif;
  boutonEnvoyer.textContent = actif ? "…" : "Envoyer";
}

function afficherQuestion(texte, fichier) {
  document.getElementById("exemples")?.remove();

  const echange = document.createElement("article");
  echange.className = "echange";

  const bulle = document.createElement("div");
  bulle.className = "question";
  bulle.textContent = texte;
  if (fichier) {
    const image = document.createElement("img");
    image.src = URL.createObjectURL(fichier);
    image.alt = "Image jointe à la question";
    bulle.appendChild(image);
  }

  const etapes = document.createElement("div");
  etapes.className = "etapes";
  etapes.textContent = "Recherche dans les sources…";

  const reponse = document.createElement("div");
  reponse.className = "reponse curseur";

  echange.append(bulle, etapes, reponse);
  conversation.appendChild(echange);
  echange.scrollIntoView({ behavior: "smooth", block: "start" });

  return { echange, etapes, reponse, premiereEtape: true };
}

async function lireFlux(corps, echange) {
  const lecteur = corps.getReader();
  const decodeur = new TextDecoder();
  let tampon = "";

  while (true) {
    const { done, value } = await lecteur.read();
    if (done) break;
    tampon += decodeur.decode(value, { stream: true });

    const blocs = tampon.split("\n\n");
    tampon = blocs.pop() || "";
    for (const bloc of blocs) {
      const ligne = bloc.split("\n").find((l) => l.startsWith("data: "));
      if (!ligne) continue;
      let evenement;
      try {
        evenement = JSON.parse(ligne.slice(6));
      } catch {
        continue;
      }
      traiter(evenement, echange);
    }
  }
  echange.reponse.classList.remove("curseur");
}

function traiter(evenement, echange) {
  switch (evenement.type) {
    case "outil": {
      if (echange.premiereEtape) {
        echange.etapes.textContent = "";
        echange.premiereEtape = false;
      }
      const ligne = document.createElement("div");
      ligne.textContent = `→ ${evenement.contenu}`;
      echange.etapes.appendChild(ligne);
      break;
    }
    case "resultat": {
      if (!evenement.contenu) break;
      const ligne = document.createElement("div");
      ligne.className = "resultat";
      ligne.textContent = evenement.contenu;
      echange.etapes.appendChild(ligne);
      break;
    }
    case "texte":
      if (echange.premiereEtape) {
        echange.etapes.remove();
        echange.premiereEtape = false;
      }
      echange.reponse.textContent += evenement.contenu;
      break;
    case "erreur":
      afficherErreur(echange, evenement.contenu);
      break;
    case "fin":
    case "terminé":
      echange.reponse.classList.remove("curseur");
      break;
  }
}

function afficherErreur(echange, message) {
  echange.reponse.classList.remove("curseur");
  const bloc = document.createElement("p");
  bloc.className = "erreur";
  bloc.textContent = message;
  echange.echange.appendChild(bloc);
}
