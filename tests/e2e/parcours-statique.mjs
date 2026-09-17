// Parcours de la page principale — celle qui ne dépend d'aucune IA.
//
// On sert un corpus de démonstration à la place de `site/donnees/`, puis on
// conduit la page dans un vrai navigateur : lectures du jour, recherche,
// lecture suivie, et comportement quand les données manquent.
//
//   node tests/e2e/parcours-statique.mjs

import assert from "node:assert/strict";
import { createServer } from "node:http";
import { readFile } from "node:fs/promises";
import { extname, join, normalize } from "node:path";
import { chromium } from "playwright";

const RACINE = new URL("../../", import.meta.url).pathname;
const TYPES = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".json": "application/json; charset=utf-8",
};

const AUJOURDHUI = new Date();
const decalage = AUJOURDHUI.getTimezoneOffset() * 60_000;
const DATE = new Date(AUJOURDHUI.getTime() - decalage).toISOString().slice(0, 10);

// ---------------------------------------------------------------------------
// Corpus de démonstration
// ---------------------------------------------------------------------------

const CATALOGUE = [
  {
    code: "Gn", nom: "Livre de la Genèse", chapitres: 50, testament: "ancien",
    section: "Pentateuque", alias: ["Genese"], disponibles: [3],
  },
  {
    code: "Jon", nom: "Livre de Jonas", chapitres: 4, testament: "ancien",
    section: "Prophètes", alias: ["Jonas"], disponibles: [1, 2],
  },
  {
    code: "Ep", nom: "Lettre aux Éphésiens", chapitres: 6, testament: "nouveau",
    section: "Lettres de saint Paul", alias: [], disponibles: [4],
  },
  {
    code: "Col", nom: "Lettre aux Colossiens", chapitres: 4, testament: "nouveau",
    section: "Lettres de saint Paul", alias: [], disponibles: [3],
  },
  {
    code: "Ap", nom: "Apocalypse de saint Jean", chapitres: 22, testament: "nouveau",
    section: "Apocalypse", alias: [], disponibles: [],
  },
];

const CORPUS = [
  ["Gn", 3, 13, "Le serpent m'a trompée, et j'ai mangé."],
  ["Jon", 1, 1, "Parole du Seigneur adressée à Jonas, fils d'Amittaï."],
  ["Jon", 1, 3, "Mais Jonas se leva pour s'enfuir à Tarsis, loin du Seigneur."],
  ["Jon", 2, 1, "Du ventre du poisson, Jonas pria le Seigneur son Dieu."],
  ["Ep", 4, 25, "Ne dites plus de mensonge ; que chacun dise la vérité à son prochain."],
  ["Col", 3, 9, "Ne mentez pas les uns aux autres, vous avez quitté le vieil homme."],
];

const LIVRES_JSON = {
  Jon: {
    code: "Jon",
    nom: "Livre de Jonas",
    chapitres: {
      1: [
        { n: 1, t: "Parole du Seigneur adressée à Jonas, fils d'Amittaï." },
        { n: 3, t: "Mais Jonas se leva pour s'enfuir à Tarsis, loin du Seigneur." },
      ],
      2: [{ n: 1, t: "Du ventre du poisson, Jonas pria le Seigneur son Dieu." }],
    },
  },
  Gn: {
    code: "Gn",
    nom: "Livre de la Genèse",
    chapitres: { 3: [{ n: 13, t: "Le serpent m'a trompée, et j'ai mangé." }] },
  },
  Ep: {
    code: "Ep",
    nom: "Lettre aux Éphésiens",
    chapitres: {
      4: [{ n: 25, t: "Ne dites plus de mensonge ; que chacun dise la vérité à son prochain." }],
    },
  },
  Col: {
    code: "Col",
    nom: "Lettre aux Colossiens",
    chapitres: {
      3: [{ n: 9, t: "Ne mentez pas les uns aux autres, vous avez quitté le vieil homme." }],
    },
  },
};

const MESSE = {
  date: DATE,
  zone: "romain",
  url: `https://www.aelf.org/${DATE}/romain/messe`,
  fete: "Saint Robert Bellarmin",
  couleur: "blanc",
  degre: "memoire",
  lectures: [
    {
      type: "lecture_1",
      titre: "« L'amour ne passera jamais »",
      reference: "1 Co 12, 31 – 13, 13",
      texte: "Frères,\nrecherchez les dons les plus grands.",
      refrain: "",
      url: `https://www.aelf.org/${DATE}/romain/messe`,
    },
    {
      type: "psaume",
      titre: "Psaume 32",
      reference: "Ps 32 (33)",
      texte: "Criez de joie pour le Seigneur.",
      refrain: "Heureux le peuple dont le Seigneur est le Dieu.",
      url: `https://www.aelf.org/${DATE}/romain/messe`,
    },
    {
      type: "evangile",
      titre: "« Ses péchés sont pardonnés »",
      reference: "Lc 7, 36-50",
      texte: "En ce temps-là, un pharisien invita Jésus.",
      refrain: "",
      url: `https://www.aelf.org/${DATE}/romain/messe`,
    },
  ],
};

// ---------------------------------------------------------------------------
// Serveur : fichiers du dépôt + données simulées
// ---------------------------------------------------------------------------

function servir({ avecDonnees = true } = {}) {
  const fausses = new Map(
    avecDonnees
      ? [
          ["/site/donnees/catalogue.json", CATALOGUE],
          ["/site/donnees/corpus.json", CORPUS],
          ["/site/donnees/messe/index.json", [DATE]],
          [`/site/donnees/messe/${DATE}.json`, MESSE],
          ...Object.entries(LIVRES_JSON).map(([code, contenu]) => [
            `/site/donnees/livres/${code}.json`,
            contenu,
          ]),
        ]
      : [],
  );

  const serveur = createServer(async (requete, reponse) => {
    const chemin = requete.url === "/" ? "/index.html" : requete.url.split("?")[0];

    if (fausses.has(chemin)) {
      reponse.writeHead(200, { "content-type": TYPES[".json"] });
      reponse.end(JSON.stringify(fausses.get(chemin)));
      return;
    }
    if (chemin.startsWith("/site/donnees/")) {
      reponse.writeHead(404).end("absent");
      return;
    }

    try {
      const contenu = await readFile(
        join(RACINE, normalize(chemin).replace(/^(\.\.[/\\])+/, "")),
      );
      reponse.writeHead(200, {
        "content-type": TYPES[extname(chemin)] || "application/octet-stream",
      });
      reponse.end(contenu);
    } catch {
      reponse.writeHead(404).end("introuvable");
    }
  });

  return new Promise((resoudre) => {
    serveur.listen(0, "127.0.0.1", () =>
      resoudre({ serveur, port: serveur.address().port }),
    );
  });
}

// ---------------------------------------------------------------------------

const resultats = [];

async function cas(nom, execution) {
  try {
    await execution();
    resultats.push([true, nom]);
    console.log(`  ✓ ${nom}`);
  } catch (erreur) {
    resultats.push([false, nom]);
    console.log(`  ✗ ${nom}\n      ${erreur.message}`);
  }
}

async function principal() {
  const navigateur = await chromium.launch({
    executablePath: process.env.CHEMIN_CHROMIUM || undefined,
  });
  const erreurs = [];

  const { serveur, port } = await servir();
  const base = `http://127.0.0.1:${port}/`;

  async function page(url = base) {
    const contexte = await navigateur.newContext({ viewport: { width: 430, height: 900 } });
    const onglet = await contexte.newPage();
    onglet.on("pageerror", (erreur) => erreurs.push(erreur.message));
    onglet.on("console", (m) => {
      if (m.type() === "error" && !/Failed to load resource/.test(m.text())) {
        erreurs.push(m.text());
      }
    });
    await onglet.goto(url);
    return { contexte, onglet };
  }

  console.log("\nParcours de la page « La Bible » (sans IA)\n");

  // -- 1. Aucune requête ne sort du site --------------------------------
  await cas("la page ne contacte aucun domaine extérieur", async () => {
    const { contexte, onglet } = await page();
    const sorties = [];
    onglet.on("request", (requete) => {
      const hote = new URL(requete.url()).host;
      if (hote !== `127.0.0.1:${port}`) sorties.push(requete.url());
    });

    await onglet.click('.onglet[data-vue="recherche"]');
    await onglet.fill("#champ-recherche", "mensonge");
    await onglet.press("#champ-recherche", "Enter");
    await onglet.waitForSelector(".resultat");
    await onglet.click('.onglet[data-vue="lire"]');
    await onglet.waitForSelector(".verset-numerote");

    assert.deepEqual(sorties, [], `requêtes sortantes : ${sorties.join(", ")}`);
    await contexte.close();
  });

  // -- 2. Les lectures du jour s'affichent -------------------------------
  await cas("les lectures du jour s'affichent sans rien demander", async () => {
    const { contexte, onglet } = await page();
    await onglet.waitForSelector(".lecture");

    assert.equal(await onglet.locator("#messe-titre").innerText(), "Saint Robert Bellarmin");
    assert.equal(await onglet.locator(".lecture").count(), 3);

    const premiere = onglet.locator(".lecture").first();
    // innerText rend le texte tel qu'il s'affiche, donc en capitales ici.
    assert.match(await premiere.locator("h3").innerText(), /première lecture/i);
    assert.match(await premiere.innerText(), /1 Co 12, 31 – 13, 13/);
    assert.match(await premiere.innerText(), /recherchez les dons les plus grands/);

    // Le refrain du psaume est mis en valeur.
    assert.match(
      await onglet.locator(".lecture .refrain").innerText(),
      /Heureux le peuple/,
    );

    // Et le lien vers la source est présent.
    const source = onglet.locator("#messe-contenu a.source");
    assert.match(await source.getAttribute("href"), /aelf\.org/);
    await contexte.close();
  });

  // -- 3. Navigation d'un jour à l'autre ---------------------------------
  await cas("on peut passer au jour suivant, qui renvoie vers AELF", async () => {
    const { contexte, onglet } = await page();
    await onglet.waitForSelector(".lecture");
    await onglet.click("#jour-suivant");
    await onglet.waitForSelector("#messe-contenu .vide");

    const texte = await onglet.locator("#messe-contenu").innerText();
    assert.match(texte, /pas encore disponibles/);
    assert.match(await onglet.locator("#messe-contenu a.source").innerText(), /aelf\.org/);
    await contexte.close();
  });

  // -- 4. La recherche trouve, classe et met en évidence -----------------
  await cas("la recherche trouve les versets et souligne les mots", async () => {
    const { contexte, onglet } = await page();
    await onglet.click('.onglet[data-vue="recherche"]');
    await onglet.fill("#champ-recherche", "mensonge");
    await onglet.press("#champ-recherche", "Enter");
    await onglet.waitForSelector(".resultat");

    const premier = onglet.locator(".resultat").first();
    assert.equal(await premier.locator(".reference").innerText(), "Ep 4, 25");
    assert.equal(await premier.locator(".nom-livre").innerText(), "Lettre aux Éphésiens");
    assert.equal(await premier.locator("mark").first().innerText(), "mensonge");

    const lien = await premier.locator(".reference").getAttribute("href");
    assert.equal(lien, "https://www.aelf.org/bible/Ep/4");
    await contexte.close();
  });

  // -- 5. Les familles de mots ------------------------------------------
  await cas("« tromperie » retrouve « trompée »", async () => {
    const { contexte, onglet } = await page();
    await onglet.click('.onglet[data-vue="recherche"]');
    await onglet.fill("#champ-recherche", "tromperie");
    await onglet.press("#champ-recherche", "Enter");
    await onglet.waitForSelector(".resultat");

    assert.match(await onglet.locator("#resultats").innerText(), /Gn 3, 13/);
    await contexte.close();
  });

  // -- 6. Le filtre par testament ---------------------------------------
  await cas("le filtre Nouveau Testament écarte l'Ancien", async () => {
    const { contexte, onglet } = await page();
    await onglet.click('.onglet[data-vue="recherche"]');
    await onglet.fill("#champ-recherche", "Seigneur");
    await onglet.press("#champ-recherche", "Enter");
    await onglet.waitForSelector(".resultat");
    assert.match(await onglet.locator("#resultats").innerText(), /Jon/);

    await onglet.check('input[name="testament"][value="nouveau"]');
    await onglet.waitForFunction(
      () => !document.getElementById("resultats").innerText.includes("Jon "),
    );

    const texte = await onglet.locator("#resultats").innerText();
    assert.doesNotMatch(texte, /Jon \d/);
    await contexte.close();
  });

  // -- 7. Une recherche sans résultat le dit clairement ------------------
  await cas("une recherche sans résultat propose de reformuler", async () => {
    const { contexte, onglet } = await page();
    await onglet.click('.onglet[data-vue="recherche"]');
    await onglet.fill("#champ-recherche", "photosynthèse");
    await onglet.press("#champ-recherche", "Enter");
    await onglet.waitForSelector(".compte");

    assert.match(await onglet.locator(".compte").innerText(), /Aucun passage/);
    assert.equal(await onglet.locator(".resultat").count(), 0);
    await contexte.close();
  });

  // -- 8. Lecture suivie -------------------------------------------------
  await cas("la lecture suivie n'offre que les chapitres présents", async () => {
    const { contexte, onglet } = await page();
    await onglet.click('.onglet[data-vue="lire"]');
    await onglet.waitForSelector(".verset-numerote");

    // Les livres sans chapitre téléchargé ne sont pas proposés.
    const codes = await onglet.locator("#choix-livre option").evaluateAll((options) =>
      options.map((option) => option.value),
    );
    assert.deepEqual(codes.sort(), ["Col", "Ep", "Gn", "Jon"]);

    await onglet.selectOption("#choix-livre", "Jon");
    const chapitres = await onglet.locator("#choix-chapitre option").evaluateAll((o) =>
      o.map((option) => option.value),
    );
    assert.deepEqual(chapitres, ["1", "2"]);

    assert.match(await onglet.locator("#chapitre-contenu h2").innerText(), /Jonas — chapitre 1/);
    assert.equal(await onglet.locator(".verset-numerote").count(), 2);
    assert.equal(await onglet.locator(".numero").first().innerText(), "1");
    await contexte.close();
  });

  // -- 9. Du résultat de recherche au chapitre ---------------------------
  await cas("« lire le chapitre » ouvre le passage au bon verset", async () => {
    const { contexte, onglet } = await page();
    await onglet.click('.onglet[data-vue="recherche"]');
    await onglet.fill("#champ-recherche", "Tarsis");
    await onglet.press("#champ-recherche", "Enter");
    await onglet.waitForSelector(".resultat");
    await onglet.click(".resultat .lien-bouton");

    await onglet.waitForSelector("#vue-lire:visible");
    assert.match(await onglet.locator("#chapitre-contenu h2").innerText(), /Jonas — chapitre 1/);
    assert.equal(await onglet.locator(".verset-numerote.vise").count(), 1);
    assert.match(await onglet.locator(".verset-numerote.vise").innerText(), /Tarsis/);
    await contexte.close();
  });

  // -- 10. L'état du corpus est annoncé ----------------------------------
  await cas("le pied de page annonce ce qui est disponible", async () => {
    const { contexte, onglet } = await page();
    await onglet.waitForSelector(".lecture");
    const etat = await onglet.locator("#etat-corpus").innerText();
    assert.match(etat, /4 livres et 5 chapitres/);
    assert.match(etat, /1 jour\(s\) de lectures/);
    await contexte.close();
  });

  serveur.close();

  // -- 11. Sans données, la page reste utilisable ------------------------
  const vide = await servir({ avecDonnees: false });
  await cas("sans corpus, la page l'explique au lieu de planter", async () => {
    const contexte = await navigateur.newContext();
    const onglet = await contexte.newPage();
    onglet.on("pageerror", (erreur) => erreurs.push(erreur.message));
    await onglet.goto(`http://127.0.0.1:${vide.port}/`);

    await onglet.waitForSelector("#messe-contenu .vide");
    assert.match(await onglet.locator("#etat-corpus").innerText(), /en cours de téléchargement/);

    await onglet.click('.onglet[data-vue="recherche"]');
    await onglet.fill("#champ-recherche", "mensonge");
    await onglet.press("#champ-recherche", "Enter");
    await onglet.waitForSelector("#resultats .vide");
    assert.match(await onglet.locator("#resultats").innerText(), /pas encore été téléchargé/);

    await contexte.close();
  });
  vide.serveur.close();

  await cas("aucune erreur JavaScript pendant tout le parcours", () => {
    assert.deepEqual(erreurs, []);
  });

  await navigateur.close();

  const echecs = resultats.filter(([ok]) => !ok);
  console.log(`\n${resultats.length - echecs.length} réussi(s), ${echecs.length} échec(s)\n`);
  process.exit(echecs.length ? 1 : 0);
}

principal();
