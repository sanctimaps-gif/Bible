// Appel de l'API Claude depuis le navigateur, avec boucle d'outils.
//
// Pourquoi c'est possible sans serveur : les deux outils qui touchent au réseau
// (`web_fetch` et `web_search`) s'exécutent sur les serveurs d'Anthropic, pas
// dans la page. C'est donc Anthropic qui va lire aelf.org, ce qui évite à la
// fois le blocage inter-domaines du navigateur et le besoin d'un serveur à
// nous. La restriction aux deux domaines autorisés est appliquée au même
// endroit, côté serveur : elle ne peut pas être contournée depuis la page.
//
// La clé API reste celle du visiteur, gardée dans son propre navigateur. Elle
// n'est jamais écrite dans le dépôt ni envoyée ailleurs qu'à api.anthropic.com.

import { LIVRES, trouverLivre } from "./livres.js";
import { systeme, CONSIGNE_IMAGE } from "./prompt.js";

const POINT_DE_TERMINAISON = "https://api.anthropic.com/v1/messages";
const MODELE = "claude-opus-5";
const DOMAINES = ["aelf.org", "sanctimaps.fr"];
const TOURS_MAX = 12;

const AELF_WEB = "https://www.aelf.org";

// ---------------------------------------------------------------------------
// Outils
// ---------------------------------------------------------------------------

const OUTILS = [
  {
    name: "preparer_url",
    description:
      "Construit l'adresse exacte d'une page d'AELF, après vérification que le " +
      "livre et le chapitre existent. À appeler avant `web_fetch` chaque fois " +
      "que tu sais déjà quoi lire. Donne soit un livre et un chapitre, soit une " +
      "date pour les lectures de la messe.",
    input_schema: {
      type: "object",
      additionalProperties: false,
      properties: {
        livre: {
          type: ["string", "null"],
          description:
            "Livre biblique, par code ou par nom (« Jon », « Jonas », " +
            "« Livre de Jonas »). null si tu demandes une messe.",
        },
        chapitre: {
          type: ["integer", "null"],
          description: "Numéro du chapitre. null si tu demandes une messe.",
        },
        date_messe: {
          type: ["string", "null"],
          description:
            "Date au format AAAA-MM-JJ pour obtenir la page des lectures de la " +
            "messe. null si tu demandes un chapitre biblique.",
        },
        zone: {
          type: ["string", "null"],
          description:
            "Zone liturgique : romain, france, afrique, belgique, luxembourg, " +
            "suisse, canada. null pour « romain ».",
        },
      },
      required: ["livre", "chapitre", "date_messe", "zone"],
    },
  },
  {
    type: "web_fetch_20260209",
    name: "web_fetch",
    allowed_domains: DOMAINES,
    max_uses: 14,
    citations: { enabled: true },
  },
  {
    type: "web_search_20260209",
    name: "web_search",
    allowed_domains: DOMAINES,
    max_uses: 8,
  },
];

/** Seul outil exécuté dans la page. Il ne touche pas au réseau. */
export function preparerUrl(entree) {
  const { livre, chapitre, date_messe: dateMesse, zone } = entree || {};

  if (dateMesse) {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(dateMesse)) {
      return {
        erreur: `Date attendue au format AAAA-MM-JJ, reçu : « ${dateMesse} ».`,
      };
    }
    return {
      url: `${AELF_WEB}/${dateMesse}/${zone || "romain"}/messe`,
      nature: "lectures de la messe",
      date: dateMesse,
    };
  }

  const code = trouverLivre(livre || "");
  if (!code) {
    return {
      erreur:
        `Livre inconnu : « ${livre} ». Emploie un code ou un nom de l'annexe ` +
        "du prompt (par exemple « Jon » ou « Livre de Jonas »).",
    };
  }

  const [nombreChapitres, nom] = LIVRES[code];
  const numero = Number(chapitre);
  if (!Number.isInteger(numero) || numero < 1 || numero > nombreChapitres) {
    return {
      erreur:
        `${nom} compte ${nombreChapitres} chapitre(s) ; ` +
        `« ${chapitre} » n'existe pas.`,
    };
  }

  return {
    url: `${AELF_WEB}/bible/${code}/${numero}`,
    nature: "chapitre biblique",
    livre: nom,
    code,
    chapitre: numero,
  };
}

// ---------------------------------------------------------------------------
// Transport
// ---------------------------------------------------------------------------

class ErreurApi extends Error {
  constructor(message, statut) {
    super(message);
    this.statut = statut;
  }
}

function messageErreur(statut, charge) {
  const detail = charge?.error?.message || "";
  switch (statut) {
    case 401:
      return "Clé API refusée. Vérifiez qu'elle est complète et toujours active.";
    case 403:
      return "Cette clé n'a pas l'autorisation d'appeler ce modèle.";
    case 429:
      return "Trop de requêtes, ou crédits épuisés. Réessayez dans un moment.";
    case 400:
      return `Requête refusée par l'API : ${detail}`;
    default:
      if (statut >= 500) return `L'API Anthropic a répondu ${statut}. Réessayez.`;
      return detail || `Erreur ${statut}.`;
  }
}

/**
 * Un aller-retour avec le modèle, en diffusion.
 * `surTexte` et `surReflexion` reçoivent les fragments au fil de l'eau.
 * Rend { blocs, stop_reason }.
 */
async function appeler(cle, messages, prompt, { surTexte, surReflexion, signal }) {
  const corps = {
    model: MODELE,
    max_tokens: 8000,
    stream: true,
    system: [{ type: "text", text: prompt, cache_control: { type: "ephemeral" } }],
    messages,
    tools: OUTILS,
    thinking: { type: "adaptive", display: "summarized" },
    output_config: { effort: "high" },
  };

  let reponse;
  try {
    reponse = await fetch(POINT_DE_TERMINAISON, {
      method: "POST",
      signal,
      headers: {
        "content-type": "application/json",
        "x-api-key": cle,
        "anthropic-version": "2023-06-01",
        // En-tête requis pour appeler l'API depuis une page web.
        "anthropic-dangerous-direct-browser-access": "true",
      },
      body: JSON.stringify(corps),
    });
  } catch (erreur) {
    throw new ErreurApi(
      "Impossible de joindre api.anthropic.com. Vérifiez votre connexion.",
      0,
    );
  }

  if (!reponse.ok) {
    let charge = null;
    try {
      charge = await reponse.json();
    } catch {
      /* corps non lisible : on s'en tient au statut */
    }
    throw new ErreurApi(messageErreur(reponse.status, charge), reponse.status);
  }

  return lireFlux(reponse, { surTexte, surReflexion });
}

/** Reconstitue les blocs de contenu à partir du flux d'événements. */
async function lireFlux(reponse, { surTexte, surReflexion }) {
  const lecteur = reponse.body.getReader();
  const decodeur = new TextDecoder();

  const blocs = [];
  const jsonPartiel = [];
  let stopReason = null;
  let tampon = "";

  while (true) {
    const { done, value } = await lecteur.read();
    if (done) break;
    tampon += decodeur.decode(value, { stream: true });

    const morceaux = tampon.split("\n\n");
    tampon = morceaux.pop() || "";

    for (const morceau of morceaux) {
      const ligne = morceau.split("\n").find((l) => l.startsWith("data:"));
      if (!ligne) continue;

      let evenement;
      try {
        evenement = JSON.parse(ligne.slice(5).trim());
      } catch {
        continue;
      }

      switch (evenement.type) {
        case "content_block_start": {
          blocs[evenement.index] = structuredClone(evenement.content_block);
          jsonPartiel[evenement.index] = "";
          break;
        }
        case "content_block_delta": {
          const bloc = blocs[evenement.index];
          if (!bloc) break;
          const delta = evenement.delta;
          if (delta.type === "text_delta") {
            bloc.text = (bloc.text || "") + delta.text;
            surTexte?.(delta.text);
          } else if (delta.type === "thinking_delta") {
            bloc.thinking = (bloc.thinking || "") + delta.thinking;
            surReflexion?.(delta.thinking);
          } else if (delta.type === "signature_delta") {
            // Indispensable : un bloc de réflexion renvoyé sans sa signature
            // est rejeté au tour suivant.
            bloc.signature = delta.signature;
          } else if (delta.type === "input_json_delta") {
            jsonPartiel[evenement.index] += delta.partial_json;
          } else if (delta.type === "citations_delta") {
            bloc.citations = [...(bloc.citations || []), delta.citation];
          }
          break;
        }
        case "content_block_stop": {
          const bloc = blocs[evenement.index];
          const brut = jsonPartiel[evenement.index];
          if (bloc && brut) {
            try {
              bloc.input = JSON.parse(brut);
            } catch {
              bloc.input = {};
            }
          }
          break;
        }
        case "message_delta":
          stopReason = evenement.delta?.stop_reason ?? stopReason;
          break;
        case "error":
          throw new ErreurApi(
            evenement.error?.message || "Erreur pendant la génération.",
            0,
          );
        default:
          break;
      }
    }
  }

  return { blocs: blocs.filter(Boolean), stop_reason: stopReason };
}

// ---------------------------------------------------------------------------
// Boucle de dialogue
// ---------------------------------------------------------------------------

function libelle(nom, entree) {
  if (nom === "preparer_url") {
    if (entree?.date_messe) return `Repérage des lectures du ${entree.date_messe}`;
    return `Repérage de ${entree?.livre ?? ""} ${entree?.chapitre ?? ""} chez AELF`;
  }
  if (nom === "web_fetch") return "Lecture de la page chez AELF";
  if (nom === "web_search") return "Recherche dans les sources autorisées";
  return `Appel de ${nom}`;
}

/**
 * Traite une question et rend la réponse rédigée.
 * `journal` est l'historique, conservé d'un tour à l'autre par l'appelant.
 */
export async function dialoguer({
  cle,
  question,
  image,
  historique,
  surEtape,
  surTexte,
  surReflexion,
  signal,
}) {
  const aujourdhui = new Date().toISOString().slice(0, 10);
  const prompt = systeme(aujourdhui);

  const contenu = image
    ? [
        {
          type: "image",
          source: { type: "base64", media_type: image.type, data: image.donnees },
        },
        { type: "text", text: `${question}\n\n${CONSIGNE_IMAGE}` },
      ]
    : question;

  historique.push({ role: "user", content: contenu });

  for (let tour = 0; tour < TOURS_MAX; tour += 1) {
    const { blocs, stop_reason: stopReason } = await appeler(
      cle,
      historique,
      prompt,
      { surTexte, surReflexion, signal },
    );

    historique.push({ role: "assistant", content: blocs });

    // Les outils serveur (web_fetch, web_search) sont déjà exécutés : on
    // signale seulement ce qu'ils ont fait, pour que l'utilisateur puisse
    // vérifier les sources consultées.
    for (const bloc of blocs) {
      if (bloc.type === "server_tool_use") surEtape?.(libelle(bloc.name, bloc.input));
      if (bloc.type === "web_fetch_tool_result") {
        const url = bloc.content?.url || bloc.content?.document?.source?.url;
        if (url) surEtape?.(`  lu : ${url}`, url);
      }
    }

    if (stopReason === "pause_turn") continue; // tour long : on relance tel quel

    const appels = blocs.filter(
      (bloc) => bloc.type === "tool_use" && bloc.name === "preparer_url",
    );
    if (!appels.length) {
      if (stopReason === "refusal") {
        throw new ErreurApi("La demande a été déclinée par le modèle.", 0);
      }
      if (stopReason === "max_tokens") {
        throw new ErreurApi(
          "Réponse interrompue : limite de longueur atteinte. Posez une question plus ciblée.",
          0,
        );
      }
      return; // fin normale
    }

    const resultats = appels.map((appel) => {
      surEtape?.(libelle(appel.name, appel.input));
      const resultat = preparerUrl(appel.input);
      if (resultat.url) surEtape?.(`  ${resultat.url}`, resultat.url);
      return {
        type: "tool_result",
        tool_use_id: appel.id,
        content: JSON.stringify(resultat),
      };
    });

    historique.push({ role: "user", content: resultats });
  }

  throw new ErreurApi(
    `Recherche interrompue après ${TOURS_MAX} tours sans conclusion. ` +
      "La question est peut-être trop large : essayez de la découper.",
    0,
  );
}

export { ErreurApi, OUTILS, MODELE, DOMAINES };
