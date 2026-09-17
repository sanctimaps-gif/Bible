// Recherche plein texte dans le corpus AELF, exécutée dans le navigateur.
//
// C'est le portage fidèle de `app/corpus/recherche.py` : même découpage, mêmes
// mots vides, même BM25, mêmes constantes. Deux implémentations, un seul
// comportement — un test compare les deux listes de mots vides pour qu'elles ne
// divergent pas en silence.

export const MOTS_VIDES = new Set(
  `a au aux avec ce ces dans de des du elle en et eux il ils je la le les leur
   lui ma mais me meme mes moi mon ne nos notre nous on ou par pas pour qu que
   qui sa se ses son sur ta te tes toi ton tu un une vos votre vous y d l j n s
   c m t est sont etait etaient ete suis es sommes etes fut furent sera seront
   ai as avons avez ont avait avaient eu cette cet celui celle ceux celles
   dont donc car or ni si comme quand lors alors tout tous toute toutes plus
   moins tres bien deja encore aussi ainsi apres avant entre vers chez sans
   sous jusqu afin`.split(/\s+/),
);

const LONGUEUR_RADICAL = 6;
const K1 = 1.5;
const B = 0.75;

export function sansAccents(texte) {
  return texte.normalize("NFD").replace(/[̀-ͯ]/g, "");
}

/** Texte → liste de radicaux indexables. */
export function decouper(texte) {
  const normalise = sansAccents(texte.toLowerCase())
    .replace(/[’']/g, " ");
  return normalise
    .split(/[^0-9a-z]+/)
    .filter((jeton) => jeton.length > 1 && !MOTS_VIDES.has(jeton))
    .map((jeton) => jeton.slice(0, LONGUEUR_RADICAL));
}

export class Index {
  /** `versets` : tableau de [code, chapitre, numero, texte]. */
  constructor(versets) {
    this.versets = versets;
    this.frequences = new Array(versets.length);
    this.longueurs = new Int32Array(versets.length);
    this.postings = new Map();

    for (let position = 0; position < versets.length; position += 1) {
      const jetons = decouper(versets[position][3]);
      const compte = new Map();
      for (const jeton of jetons) compte.set(jeton, (compte.get(jeton) || 0) + 1);

      this.frequences[position] = compte;
      this.longueurs[position] = jetons.length;

      for (const jeton of compte.keys()) {
        let liste = this.postings.get(jeton);
        if (!liste) {
          liste = [];
          this.postings.set(jeton, liste);
        }
        liste.push(position);
      }
    }

    const total = versets.length || 1;
    let somme = 0;
    for (let i = 0; i < this.longueurs.length; i += 1) somme += this.longueurs[i];
    this.longueurMoyenne = somme / total || 1;
    this.total = versets.length;
  }

  /**
   * Cherche et rend [{ code, chapitre, numero, texte, score }], du plus
   * pertinent au moins pertinent.
   */
  chercher(requete, { limite = 40, testament = null, codes = null, livres = null } = {}) {
    const jetons = decouper(requete);
    if (!jetons.length) return [];

    const filtreCodes = codes && codes.length ? new Set(codes) : null;
    const scores = new Map();

    for (const jeton of new Set(jetons)) {
      const postings = this.postings.get(jeton);
      if (!postings) continue;

      const idf = Math.log(
        1 + (this.total - postings.length + 0.5) / (postings.length + 0.5),
      );

      for (const position of postings) {
        const [code] = this.versets[position];
        if (filtreCodes && !filtreCodes.has(code)) continue;
        if (testament && livres && livres.get(code)?.testament !== testament) continue;

        const frequence = this.frequences[position].get(jeton);
        const longueur = this.longueurs[position] || 1;
        const numerateur = frequence * (K1 + 1);
        const denominateur =
          frequence + K1 * (1 - B + (B * longueur) / this.longueurMoyenne);
        scores.set(position, (scores.get(position) || 0) + (idf * numerateur) / denominateur);
      }
    }

    if (!scores.size) return [];

    // Une citation exacte doit primer sur une simple cooccurrence de mots.
    const expression = sansAccents(requete.toLowerCase()).trim();
    if (expression.length > 8) {
      for (const [position, score] of scores) {
        if (sansAccents(this.versets[position][3].toLowerCase()).includes(expression)) {
          scores.set(position, score * 1.5);
        }
      }
    }

    return [...scores.entries()]
      .sort((a, b) => b[1] - a[1])
      .slice(0, limite)
      .map(([position, score]) => {
        const [code, chapitre, numero, texte] = this.versets[position];
        return { code, chapitre, numero, texte, score };
      });
  }
}

/** Met en évidence les mots cherchés dans un verset (rend du HTML échappé). */
export function souligner(texte, requete) {
  const radicaux = new Set(decouper(requete));
  if (!radicaux.size) return echapper(texte);

  // On découpe en conservant les séparateurs, pour rendre le texte intact.
  return texte
    .split(/(\s+)/)
    .map((morceau) => {
      if (/^\s+$/.test(morceau)) return morceau;
      const nu = sansAccents(morceau.toLowerCase()).replace(/[^0-9a-z]/g, "");
      const radical = nu.slice(0, LONGUEUR_RADICAL);
      const marque = nu.length > 1 && radicaux.has(radical);
      return marque ? `<mark>${echapper(morceau)}</mark>` : echapper(morceau);
    })
    .join("");
}

function echapper(texte) {
  return texte.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
