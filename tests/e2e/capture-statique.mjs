// Captures de la page principale, avec les données réellement présentes dans
// site/donnees/ : node tests/e2e/capture-statique.mjs

import { createServer } from "node:http";
import { readFile } from "node:fs/promises";
import { extname, join, normalize } from "node:path";
import { chromium } from "playwright";

const RACINE = new URL("../../", import.meta.url).pathname;
const SORTIE = process.env.SORTIE_CAPTURES || "/tmp/claude-0";
const TYPES = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".json": "application/json; charset=utf-8",
};

const serveur = createServer(async (requete, reponse) => {
  const chemin = requete.url === "/" ? "/index.html" : requete.url.split("?")[0];
  try {
    const contenu = await readFile(
      join(RACINE, normalize(chemin).replace(/^(\.\.[/\\])+/, "")),
    );
    reponse.writeHead(200, { "content-type": TYPES[extname(chemin)] || "text/plain" });
    reponse.end(contenu);
  } catch {
    reponse.writeHead(404).end();
  }
});

await new Promise((r) => serveur.listen(0, "127.0.0.1", r));
const base = `http://127.0.0.1:${serveur.address().port}/`;

const navigateur = await chromium.launch({
  executablePath: process.env.CHEMIN_CHROMIUM || undefined,
});

const contexte = await navigateur.newContext({
  viewport: { width: 430, height: 1250 },
  deviceScaleFactor: 2,
});
const page = await contexte.newPage();
page.on("pageerror", (erreur) => console.error("ERREUR JS :", erreur.message));

// 1. Les lectures du jour
await page.goto(base);
await page.waitForSelector(".lecture, #messe-contenu .vide", { timeout: 15000 });
await page.waitForTimeout(300);
await page.screenshot({ path: `${SORTIE}/bible-messe.png` });

// 2. Une recherche thématique
await page.click('.onglet[data-vue="recherche"]');
await page.fill("#champ-recherche", "tromperie");
await page.check('input[name="testament"][value="nouveau"]');
await page.press("#champ-recherche", "Enter");
await page.waitForSelector(".resultat, .compte", { timeout: 30000 });
await page.waitForTimeout(300);
await page.screenshot({ path: `${SORTIE}/bible-recherche.png` });

// 3. La lecture suivie
await page.click('.onglet[data-vue="lire"]');
await page.waitForSelector(".verset-numerote", { timeout: 15000 });
await page.selectOption("#choix-livre", "Jon");
await page.waitForTimeout(500);
await page.screenshot({ path: `${SORTIE}/bible-lecture.png` });

console.log(await page.locator("#etat-corpus").innerText());

await contexte.close();
await navigateur.close();
serveur.close();
console.log(`Captures écrites dans ${SORTIE}/`);
