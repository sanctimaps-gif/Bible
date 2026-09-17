// Table des livres bibliques — engendrée depuis app/corpus/livres.py.
// Ne pas modifier à la main : régénérer avec `python scripts/exporter_livres.py`.
// Format : code AELF → [nombre de chapitres, nom complet, graphies acceptées]

export const LIVRES = {
  "Gn": [50, "Livre de la Genèse", ["Genese"]],
  "Ex": [40, "Livre de l'Exode", ["Exode"]],
  "Lv": [27, "Livre des Lévites", ["Lévitique", "Levitique"]],
  "Nb": [36, "Livre des Nombres", ["Nombres"]],
  "Dt": [34, "Livre du Deutéronome", ["Deutéronome"]],
  "Jos": [24, "Livre de Josué", ["Josué"]],
  "Jg": [21, "Livre des Juges", ["Juges"]],
  "Rt": [4, "Livre de Ruth", ["Ruth"]],
  "1S": [31, "Premier livre de Samuel", ["1 Samuel", "I Samuel"]],
  "2S": [24, "Deuxième livre de Samuel", ["2 Samuel", "II Samuel"]],
  "1R": [22, "Premier livre des Rois", ["1 Rois", "I Rois"]],
  "2R": [25, "Deuxième livre des Rois", ["2 Rois", "II Rois"]],
  "1Ch": [29, "Premier livre des Chroniques", ["1 Chroniques"]],
  "2Ch": [36, "Deuxième livre des Chroniques", ["2 Chroniques"]],
  "Esd": [10, "Livre d'Esdras", ["Esdras"]],
  "Ne": [13, "Livre de Néhémie", ["Néhémie"]],
  "Tb": [14, "Livre de Tobie", ["Tobie"]],
  "Jdt": [16, "Livre de Judith", ["Judith"]],
  "Est": [10, "Livre d'Esther", ["Esther"]],
  "1M": [16, "Premier livre des Martyrs d'Israël", ["1 Maccabées", "1 Macchabées"]],
  "2M": [15, "Deuxième livre des Martyrs d'Israël", ["2 Maccabées", "2 Macchabées"]],
  "Jb": [42, "Livre de Job", ["Job"]],
  "Ps": [150, "Livre des Psaumes", ["Psaume", "Psaumes"]],
  "Pr": [31, "Livre des Proverbes", ["Proverbes"]],
  "Qo": [12, "Livre de Qohélet", ["Qohélet", "Ecclésiaste", "Ecclesiaste"]],
  "Ct": [8, "Cantique des cantiques", ["Cantique"]],
  "Sg": [19, "Livre de la Sagesse", ["Sagesse"]],
  "Si": [51, "Livre de Ben Sira le Sage", ["Siracide", "Ecclésiastique", "Ben Sira"]],
  "Is": [66, "Livre d'Isaïe", ["Isaïe", "Isaie"]],
  "Jr": [52, "Livre de Jérémie", ["Jérémie", "Jeremie"]],
  "Lm": [5, "Livre des Lamentations", ["Lamentations"]],
  "Ba": [6, "Livre de Baruch", ["Baruch"]],
  "Ez": [48, "Livre d'Ézékiel", ["Ézéchiel", "Ezechiel", "Ézékiel"]],
  "Dn": [14, "Livre de Daniel", ["Daniel"]],
  "Os": [14, "Livre d'Osée", ["Osée", "Osee"]],
  "Jl": [4, "Livre de Joël", ["Joël", "Joel"]],
  "Am": [9, "Livre d'Amos", ["Amos"]],
  "Ab": [1, "Livre d'Abdias", ["Abdias"]],
  "Jon": [4, "Livre de Jonas", ["Jonas"]],
  "Mi": [7, "Livre de Michée", ["Michée", "Michee"]],
  "Na": [3, "Livre de Nahoum", ["Nahoum", "Nahum"]],
  "Ha": [3, "Livre d'Habacuc", ["Habacuc", "Habaquq"]],
  "So": [3, "Livre de Sophonie", ["Sophonie"]],
  "Ag": [2, "Livre d'Aggée", ["Aggée", "Aggee"]],
  "Za": [14, "Livre de Zacharie", ["Zacharie"]],
  "Ml": [3, "Livre de Malachie", ["Malachie"]],
  "Mt": [28, "Évangile selon saint Matthieu", ["Matthieu"]],
  "Mc": [16, "Évangile selon saint Marc", ["Marc"]],
  "Lc": [24, "Évangile selon saint Luc", ["Luc"]],
  "Jn": [21, "Évangile selon saint Jean", ["Jean"]],
  "Ac": [28, "Actes des Apôtres", ["Actes"]],
  "Rm": [16, "Lettre aux Romains", ["Romains"]],
  "1Co": [16, "Première lettre aux Corinthiens", ["1 Corinthiens"]],
  "2Co": [13, "Deuxième lettre aux Corinthiens", ["2 Corinthiens"]],
  "Ga": [6, "Lettre aux Galates", ["Galates"]],
  "Ep": [6, "Lettre aux Éphésiens", ["Éphésiens", "Ephesiens"]],
  "Ph": [4, "Lettre aux Philippiens", ["Philippiens"]],
  "Col": [4, "Lettre aux Colossiens", ["Colossiens"]],
  "1Th": [5, "Première lettre aux Thessaloniciens", ["1 Thessaloniciens"]],
  "2Th": [3, "Deuxième lettre aux Thessaloniciens", ["2 Thessaloniciens"]],
  "1Tm": [6, "Première lettre à Timothée", ["1 Timothée"]],
  "2Tm": [4, "Deuxième lettre à Timothée", ["2 Timothée"]],
  "Tt": [3, "Lettre à Tite", ["Tite"]],
  "Phm": [1, "Lettre à Philémon", ["Philémon", "Philemon"]],
  "He": [13, "Lettre aux Hébreux", ["Hébreux", "Hebreux"]],
  "Jc": [5, "Lettre de saint Jacques", ["Jacques"]],
  "1P": [5, "Première lettre de saint Pierre", ["1 Pierre"]],
  "2P": [3, "Deuxième lettre de saint Pierre", ["2 Pierre"]],
  "1Jn": [5, "Première lettre de saint Jean", ["1 Jean"]],
  "2Jn": [1, "Deuxième lettre de saint Jean", ["2 Jean"]],
  "3Jn": [1, "Troisième lettre de saint Jean", ["3 Jean"]],
  "Jude": [1, "Lettre de saint Jude", ["Jude"]],
  "Ap": [22, "Apocalypse de saint Jean", ["Apocalypse"]],
};

/** Repli casse/accents, pour comparer « Isaïe », « isaie » et « ISAIE ». */
function clef(texte) {
  return texte
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]/g, "");
}

const PAR_CLEF = new Map();
for (const [code, [, nom, alias]] of Object.entries(LIVRES)) {
  PAR_CLEF.set(clef(code), code);
  PAR_CLEF.set(clef(nom), code);
  for (const graphie of alias) PAR_CLEF.set(clef(graphie), code);
  // « Genèse » doit marcher autant que « Livre de la Genèse ».
  const court = nom.replace(/^Livre (de la |des |du |d'|de )/, "");
  if (!PAR_CLEF.has(clef(court))) PAR_CLEF.set(clef(court), code);
}

/** Résout « Rm », « romains », « Lettre aux Romains » vers le même code. */
export function trouverLivre(nomOuCode) {
  if (!nomOuCode) return null;
  return PAR_CLEF.get(clef(nomOuCode)) || null;
}

/** Liste compacte pour le prompt système : « Gn (50 ch.) Livre de la Genèse ». */
export function catalogue() {
  return Object.entries(LIVRES)
    .map(([code, [chapitres, nom]]) => `${code} (${chapitres} ch.) ${nom}`)
    .join("\n");
}
