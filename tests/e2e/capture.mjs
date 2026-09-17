// Capture d'écran de la page, avec une réponse simulée.
// Sert à relire le rendu sans clé API : node tests/e2e/capture.mjs

import { createServer } from "node:http";
import { readFile } from "node:fs/promises";
import { extname, join, normalize } from "node:path";
import { chromium } from "playwright";

const RACINE = new URL("../../", import.meta.url).pathname;
const TYPES = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
};

const REPONSE = [
  "Jonas est le prophète qui refuse sa mission, et dont le refus devient ",
  "l'histoire.\n\n",
  "Dieu l'envoie à Ninive, la grande ville ennemie, pour l'avertir. Jonas ",
  "part dans la direction opposée : il embarque pour Tarsis, à l'autre bout ",
  "du monde connu. Une tempête se lève. Les marins tirent au sort, le sort ",
  "tombe sur lui, et il leur demande lui-même de le jeter à la mer.\n\n",
  "Un grand poisson l'engloutit. Il y reste trois jours, et il prie. Rendu à ",
  "la terre ferme, il va enfin à Ninive et annonce sa ruine. La ville se ",
  "convertit, et Dieu renonce à la détruire.\n\n",
  "C'est alors que le livre se retourne : Jonas est furieux. Il préférait ",
  "avoir raison plutôt que voir la ville sauvée.\n\n",
  "## Références\n\n",
  "- Jon 1 — Livre de Jonas, la fuite et la tempête\n",
  "- Jon 3 — la prédication à Ninive\n",
  "- Jon 4 — la colère de Jonas",
];

function sse(evenements) {
  return evenements.map((e) => `event: ${e.type}\ndata: ${JSON.stringify(e)}\n\n`).join("");
}

const TOUR_OUTIL = sse([
  { type: "message_start", message: { id: "m1", role: "assistant", content: [] } },
  {
    type: "content_block_start",
    index: 0,
    content_block: { type: "tool_use", id: "tu_1", name: "preparer_url", input: {} },
  },
  {
    type: "content_block_delta",
    index: 0,
    delta: {
      type: "input_json_delta",
      partial_json: '{"livre":"Jonas","chapitre":1,"date_messe":null,"zone":null}',
    },
  },
  { type: "content_block_stop", index: 0 },
  { type: "message_delta", delta: { stop_reason: "tool_use" } },
  { type: "message_stop" },
]);

const TOUR_REPONSE = sse([
  { type: "message_start", message: { id: "m2", role: "assistant", content: [] } },
  { type: "content_block_start", index: 0, content_block: { type: "text", text: "" } },
  ...REPONSE.map((texte) => ({
    type: "content_block_delta",
    index: 0,
    delta: { type: "text_delta", text: texte },
  })),
  { type: "content_block_stop", index: 0 },
  { type: "message_delta", delta: { stop_reason: "end_turn" } },
  { type: "message_stop" },
]);

const serveur = createServer(async (requete, reponse) => {
  const chemin = requete.url === "/" ? "/index.html" : requete.url.split("?")[0];
  try {
    const contenu = await readFile(join(RACINE, normalize(chemin).replace(/^(\.\.[/\\])+/, "")));
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

for (const theme of ["light", "dark"]) {
  const contexte = await navigateur.newContext({
    viewport: { width: 430, height: 1200 },
    deviceScaleFactor: 2,
    colorScheme: theme,
  });
  const page = await contexte.newPage();

  let appels = 0;
  await page.route("https://api.anthropic.com/**", async (route) => {
    appels += 1;
    await route.fulfill({
      status: 200,
      headers: { "content-type": "text/event-stream" },
      body: appels === 1 ? TOUR_OUTIL : TOUR_REPONSE,
    });
  });

  await page.goto(base);
  if (theme === "light") {
    await page.screenshot({ path: "/tmp/claude-0/capture-cle.png", fullPage: false });
  }

  await page.fill("#champ-cle", "sk-ant-demonstration");
  await page.click("#formulaire-cle button");
  await page.fill("#question", "Raconte-moi l'histoire du prophète Jonas.");
  await page.click("#envoyer");
  await page.waitForSelector(".reponse h3");
  await page.waitForTimeout(400);

  await page.screenshot({ path: `/tmp/claude-0/capture-${theme}.png`, fullPage: false });
  await contexte.close();
}

await navigateur.close();
serveur.close();
console.log("Captures écrites dans /tmp/claude-0/");
