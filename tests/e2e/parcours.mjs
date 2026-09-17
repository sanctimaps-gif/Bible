// Parcours de bout en bout de la page GitHub Pages, dans un vrai navigateur.
//
// L'API Anthropic est simulée : on intercepte les appels à /v1/messages et on
// rejoue un flux d'événements identique à celui de l'API. Cela vérifie ce qui
// est vérifiable sans clé — l'analyse du flux, la boucle d'outils, le renvoi
// des résultats, le rendu et les messages d'erreur.
//
//   node tests/e2e/parcours.mjs

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
};

// ---------------------------------------------------------------------------
// Serveur de fichiers (les modules ES ne se chargent pas depuis file://)
// ---------------------------------------------------------------------------

function servir() {
  const serveur = createServer(async (requete, reponse) => {
    const chemin = requete.url === "/" ? "/assistant-ia.html" : requete.url.split("?")[0];
    const fichier = join(RACINE, normalize(chemin).replace(/^(\.\.[/\\])+/, ""));
    try {
      const contenu = await readFile(fichier);
      reponse.writeHead(200, {
        "content-type": TYPES[extname(fichier)] || "application/octet-stream",
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
// Faux flux d'API
// ---------------------------------------------------------------------------

function sse(evenements) {
  return evenements
    .map((e) => `event: ${e.type}\ndata: ${JSON.stringify(e)}\n\n`)
    .join("");
}

/** Un tour qui demande l'URL d'un chapitre. */
function tourOutil() {
  return sse([
    { type: "message_start", message: { id: "msg_1", role: "assistant", content: [] } },
    {
      type: "content_block_start",
      index: 0,
      content_block: { type: "thinking", thinking: "", signature: "" },
    },
    {
      type: "content_block_delta",
      index: 0,
      delta: { type: "thinking_delta", thinking: "Jonas est un petit livre." },
    },
    {
      type: "content_block_delta",
      index: 0,
      delta: { type: "signature_delta", signature: "sig-abc" },
    },
    { type: "content_block_stop", index: 0 },
    {
      type: "content_block_start",
      index: 1,
      content_block: { type: "tool_use", id: "tu_1", name: "preparer_url", input: {} },
    },
    {
      type: "content_block_delta",
      index: 1,
      delta: { type: "input_json_delta", partial_json: '{"livre":"Jonas",' },
    },
    {
      type: "content_block_delta",
      index: 1,
      delta: {
        type: "input_json_delta",
        partial_json: '"chapitre":1,"date_messe":null,"zone":null}',
      },
    },
    { type: "content_block_stop", index: 1 },
    { type: "message_delta", delta: { stop_reason: "tool_use" } },
    { type: "message_stop" },
  ]);
}

/** Un tour final, qui rédige la réponse. */
function tourReponse() {
  const morceaux = [
    "Jonas est un prophète ",
    "qui fuit sa mission.\n\n",
    "## Références\n\n",
    "- Jon 1 — Livre de Jonas",
  ];
  return sse([
    { type: "message_start", message: { id: "msg_2", role: "assistant", content: [] } },
    { type: "content_block_start", index: 0, content_block: { type: "text", text: "" } },
    ...morceaux.map((texte) => ({
      type: "content_block_delta",
      index: 0,
      delta: { type: "text_delta", text: texte },
    })),
    { type: "content_block_stop", index: 0 },
    { type: "message_delta", delta: { stop_reason: "end_turn" } },
    { type: "message_stop" },
  ]);
}

// ---------------------------------------------------------------------------
// Scénarios
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
  const { serveur, port } = await servir();
  const base = `http://127.0.0.1:${port}/`;
  const navigateur = await chromium.launch({
    executablePath: process.env.CHEMIN_CHROMIUM || undefined,
  });

  const erreursConsole = [];

  async function nouvellePage(gestionnaireApi) {
    const contexte = await navigateur.newContext();
    const page = await contexte.newPage();
    page.on("pageerror", (erreur) => erreursConsole.push(erreur.message));
    page.on("console", (message) => {
      // Un 401 simulé fait journaliser le navigateur ; ce n'est pas une
      // exception JavaScript, et la page le traite déjà proprement.
      if (message.type() === "error" && !/Failed to load resource/.test(message.text())) {
        erreursConsole.push(message.text());
      }
    });
    if (gestionnaireApi) {
      await page.route("https://api.anthropic.com/**", gestionnaireApi);
    }
    await page.goto(base);
    return { contexte, page };
  }

  console.log("\nParcours de la page « assistant biblique »\n");

  // -- 1. La clé est demandée avant toute chose --------------------------
  await cas("la page demande la clé et masque l'assistant", async () => {
    const { contexte, page } = await nouvellePage();
    assert.equal(await page.locator("#acces-cle").isVisible(), true);
    assert.equal(await page.locator("#atelier").isVisible(), false);
    assert.match(await page.locator("#acces-cle").innerText(), /api\.anthropic\.com/);
    await contexte.close();
  });

  // -- 2. Une fois la clé saisie, l'assistant apparaît -------------------
  await cas("la clé saisie ouvre l'assistant et est mémorisée", async () => {
    const { contexte, page } = await nouvellePage();
    await page.fill("#champ-cle", "sk-ant-essai");
    await page.click("#formulaire-cle button");
    await page.waitForSelector("#atelier:visible");
    assert.equal(await page.locator("#acces-cle").isVisible(), false);

    const memorise = await page.evaluate(() =>
      localStorage.getItem("assistant-biblique.cle"),
    );
    assert.equal(memorise, "sk-ant-essai");

    // Elle survit à un rechargement.
    await page.reload();
    await page.waitForSelector("#atelier:visible");
    await contexte.close();
  });

  // -- 3. Le parcours complet : outil, puis réponse ----------------------
  await cas("la boucle d'outils va au bout et rend la réponse", async () => {
    const corps = [];
    const { contexte, page } = await nouvellePage(async (route) => {
      corps.push(JSON.parse(route.request().postData()));
      await route.fulfill({
        status: 200,
        headers: { "content-type": "text/event-stream" },
        body: corps.length === 1 ? tourOutil() : tourReponse(),
      });
    });

    await page.fill("#champ-cle", "sk-ant-essai");
    await page.click("#formulaire-cle button");
    await page.fill("#question", "Raconte-moi Jonas.");
    await page.click("#envoyer");

    await page.waitForSelector(".reponse:has-text('Jonas est un prophète')");

    // Deux allers-retours ont eu lieu.
    assert.equal(corps.length, 2, `attendu 2 appels, reçu ${corps.length}`);

    // Le premier porte bien les outils et les domaines autorisés.
    const outils = corps[0].tools;
    assert.equal(outils[0].name, "preparer_url");
    const recherche = outils.find((o) => o.name === "web_search");
    assert.deepEqual(recherche.allowed_domains, ["aelf.org", "sanctimaps.fr"]);
    const lecture = outils.find((o) => o.name === "web_fetch");
    assert.deepEqual(lecture.allowed_domains, ["aelf.org", "sanctimaps.fr"]);
    assert.equal(corps[0].model, "claude-opus-5");
    assert.match(corps[0].system[0].text, /aelf\.org/);
    assert.match(corps[0].system[0].text, /sanctimaps\.fr/);

    // Le second renvoie le résultat de l'outil, avec l'URL AELF calculée.
    const messages = corps[1].messages;
    const dernier = messages[messages.length - 1];
    assert.equal(dernier.role, "user");
    assert.equal(dernier.content[0].type, "tool_result");
    assert.equal(dernier.content[0].tool_use_id, "tu_1");
    const charge = JSON.parse(dernier.content[0].content);
    assert.equal(charge.url, "https://www.aelf.org/bible/Jon/1");

    // Le bloc de réflexion est renvoyé avec sa signature — sans quoi l'API
    // rejetterait le tour suivant.
    const assistant = messages.find((m) => m.role === "assistant");
    const reflexion = assistant.content.find((b) => b.type === "thinking");
    assert.equal(reflexion.signature, "sig-abc");
    assert.match(reflexion.thinking, /petit livre/);

    // L'interface montre la source consultée, et met en forme la réponse.
    const etapes = await page.locator(".etapes").innerText();
    assert.match(etapes, /aelf\.org\/bible\/Jon\/1/);
    assert.equal(await page.locator(".reponse h3").innerText(), "Références");
    assert.equal(await page.locator(".reponse li").count(), 1);

    await contexte.close();
  });

  // -- 4. Une clé refusée donne un message clair -------------------------
  await cas("une clé refusée est expliquée en français", async () => {
    const { contexte, page } = await nouvellePage(async (route) => {
      await route.fulfill({
        status: 401,
        contentType: "application/json",
        body: JSON.stringify({ error: { message: "invalid x-api-key" } }),
      });
    });

    await page.fill("#champ-cle", "sk-ant-faux");
    await page.click("#formulaire-cle button");
    await page.fill("#question", "Bonjour");
    await page.click("#envoyer");

    await page.waitForSelector(".erreur");
    assert.match(await page.locator(".erreur").innerText(), /Clé API refusée/);
    await contexte.close();
  });

  // -- 5. L'image est transmise avant la consigne ------------------------
  await cas("une image jointe part en premier dans le message", async () => {
    const corps = [];
    const { contexte, page } = await nouvellePage(async (route) => {
      corps.push(JSON.parse(route.request().postData()));
      await route.fulfill({
        status: 200,
        headers: { "content-type": "text/event-stream" },
        body: tourReponse(),
      });
    });

    await page.fill("#champ-cle", "sk-ant-essai");
    await page.click("#formulaire-cle button");
    await page.setInputFiles("#image", {
      name: "scene.png",
      mimeType: "image/png",
      buffer: Buffer.from("89504e470d0a1a0a", "hex"),
    });
    await page.fill("#question", "Quelle scène ?");
    await page.click("#envoyer");
    await page.waitForSelector(".reponse:has-text('Jonas')");

    const contenu = corps[0].messages[0].content;
    assert.equal(contenu[0].type, "image");
    assert.equal(contenu[0].source.media_type, "image/png");
    assert.equal(contenu[0].source.type, "base64");
    assert.equal(contenu[1].type, "text");
    assert.match(contenu[1].text, /Quelle scène \?/);
    assert.match(contenu[1].text, /indices visuels/);

    await contexte.close();
  });

  // -- 6. Les en-têtes attendus par l'API sont présents ------------------
  await cas("l'en-tête d'accès navigateur est envoyé", async () => {
    let entetes = null;
    const { contexte, page } = await nouvellePage(async (route) => {
      entetes = route.request().headers();
      await route.fulfill({
        status: 200,
        headers: { "content-type": "text/event-stream" },
        body: tourReponse(),
      });
    });

    await page.fill("#champ-cle", "sk-ant-essai");
    await page.click("#formulaire-cle button");
    await page.fill("#question", "Bonjour");
    await page.click("#envoyer");
    await page.waitForSelector(".reponse:has-text('Jonas')");

    assert.equal(entetes["anthropic-dangerous-direct-browser-access"], "true");
    assert.equal(entetes["anthropic-version"], "2023-06-01");
    assert.equal(entetes["x-api-key"], "sk-ant-essai");
    await contexte.close();
  });

  // -- 7. Aucune erreur JavaScript n'a été levée -------------------------
  await cas("aucune erreur JavaScript pendant tout le parcours", () => {
    assert.deepEqual(erreursConsole, []);
  });

  await navigateur.close();
  serveur.close();

  const echecs = resultats.filter(([ok]) => !ok);
  console.log(
    `\n${resultats.length - echecs.length} réussi(s), ${echecs.length} échec(s)\n`,
  );
  process.exit(echecs.length ? 1 : 0);
}

principal();
