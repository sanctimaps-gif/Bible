# La Bible — texte liturgique AELF

**<https://sanctimaps-gif.github.io/Bible/>**

Lire la Bible, chercher dans le texte, suivre les lectures de la messe. Rien à
installer, aucun compte, aucune clé, **aucune IA** : la page ouvre et fonctionne.

Le texte est celui de l'**AELF** — la traduction liturgique officielle
francophone.

| | |
|---|---|
| **Aujourd'hui** | Les lectures de la messe : fête, première lecture, psaume, évangile |
| **Chercher** | Recherche plein texte dans toute la Bible, par mot et par famille de mots |
| **Lire** | N'importe quel livre, n'importe quel chapitre, verset par verset |

Chaque passage renvoie à sa page d'origine sur aelf.org.

---

## Comment cela peut marcher sans serveur

GitHub Pages ne sait servir que des fichiers. La page n'a donc besoin de rien
d'autre : **c'est GitHub lui-même qui télécharge le texte depuis AELF**, une
fois, par un workflow (`.github/workflows/corpus.yml`), et le dépose dans
`site/donnees/`. La page lit ensuite ses propres fichiers.

Conséquences :

* aucune requête ne part vers un autre domaine — un test le vérifie ;
* pas de blocage inter-domaines, puisqu'il n'y a pas de domaine à traverser ;
* la recherche s'exécute dans le navigateur, sur le corpus déjà chargé ;
* les lectures du jour sont rafraîchies chaque nuit par le même workflow.

La recherche est un BM25 adapté au français : elle trouve les mots **et leur
famille**. Chercher *tromperie* remonte aussi *tromper*, *trompeur*, *trompée* —
c'est ce qui permet de répondre à « que dit le Nouveau Testament sur la
tromperie ? » en filtrant sur le Nouveau Testament.

---

## Ce que cette version ne fait pas

Il faut le dire nettement : **elle ne reconnaît pas une scène biblique sur une
image**, et elle ne rédige pas de synthèse. Ces deux choses demandent une IA.
Sans IA, une question thématique rend **les passages eux-mêmes**, avec leurs
références — plus vérifiable qu'un texte rédigé, mais ce n'est pas la même
chose.

Si vous voulez ces fonctions, le dépôt contient deux autres versions, décrites
plus bas : une page qui demande sa clé au visiteur (`assistant-ia.html`) et une
version serveur complète (`app/`).

---

## Les trois versions du projet

| | **La Bible** (`index.html`) | **Assistant IA** (`assistant-ia.html`) | **Version serveur** (`app/`) |
|---|---|---|---|
| Où elle tourne | GitHub Pages | GitHub Pages | Votre machine ou un hébergeur |
| IA | aucune | oui, clé du visiteur | oui, clé côté serveur |
| Image d'une scène | non | oui | oui |
| Réponse rédigée | non, des passages | oui | oui |
| Recherche | plein texte, tout le corpus | le modèle propose puis vérifie | plein texte, tout le corpus |
| Lectures du jour | oui | oui | oui |
| Mise en route | rien | coller une clé | quatre commandes |

---

## Sources

| Domaine | Sert à | Point d'entrée |
|---|---|---|
| `aelf.org` | Texte biblique et lectures de la messe | <https://www.aelf.org/2026-09-17/romain/messe> |
| `sanctimaps.fr` | Questions sur les saints (versions IA seulement) | <https://sanctimaps.fr> |

---

## Comment la contrainte « une seule source » est tenue

Ce n'est pas une consigne polie dans un prompt : c'est une propriété du code.

1. **Le modèle n'a aucun accès direct au web.** Il ne dispose que de cinq
   outils (`app/ia/outils.py`), tous branchés sur les clients maison.
2. **Chaque client vérifie le domaine avant d'émettre une requête**
   (`verifier_domaine`, `app/sources/aelf.py`). Le contrôle porte sur l'hôte,
   pas sur une sous-chaîne : `https://aelf.org.pirate.net/` est rejeté.
   Une URL hors domaine lève `SourceInterdite`.
3. **Le prompt système interdit la réponse de mémoire** (`app/ia/prompts.py`) :
   même quand le modèle « connaît » le verset, il doit l'aller chercher et le
   citer tel qu'AELF le publie.
4. **Les tests le vérifient** : `tests/test_sources.py` et `tests/test_outils.py`
   simulent tout le réseau et échouent si un appel part ailleurs.

### Portée de la source

Le cahier des charges cite une URL précise :
`https://www.aelf.org/2026-09-17/romain/messe`. Cette page ne contient que les
lectures **d'un seul jour** — de quoi répondre à « quelles sont les lectures
d'aujourd'hui ? », mais pas à « raconte-moi Jonas » ni à « que dit le Nouveau
Testament sur la tromperie ? ».

Le projet lit donc **tout `aelf.org`**, et rien d'autre : la même page de messe
(pour n'importe quelle date et n'importe quelle zone liturgique) *et* le
navigateur biblique `aelf.org/bible/<livre>/<chapitre>`, qui publie la même
traduction liturgique officielle. C'est la lecture qui rend le cahier des
charges réalisable ; si vous vouliez vraiment restreindre à la seule page du
17 septembre 2026, il suffit de retirer `lire_passage` et `chercher_ecriture`
de `DEFINITIONS` — l'assistant se limitera alors aux lectures du jour.

---

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env    # puis renseignez ANTHROPIC_API_KEY
```

### Télécharger le corpus biblique depuis AELF

La recherche par thème a besoin d'une copie locale du texte. On la construit
une fois, depuis AELF :

```bash
python scripts/ingerer_bible.py                 # tout le canon (1 334 chapitres)
python scripts/ingerer_bible.py --nouveau       # Nouveau Testament seul
python scripts/ingerer_bible.py Jonas Isaïe     # quelques livres
```

L'opération est volontairement lente (une demi-seconde entre deux requêtes, réglable
par `BIBLE_DELAI_INGESTION`) : AELF est un service gratuit, on ne le martèle
pas. Elle **reprend là où elle s'est arrêtée** — interrompez-la et relancez-la
sans rien perdre.

Sans ce corpus, l'assistant fonctionne quand même : il peut lire un passage dont
il connaît la référence et les lectures de la messe, mais il dira franchement
que la recherche thématique est indisponible.

---

## Utilisation

### En ligne de commande

```bash
python -m app.cli "Raconte-moi l'histoire du prophète Jonas."
python -m app.cli "Que dit le Nouveau Testament sur la tromperie ?"
python -m app.cli --image annonciation.jpg "Quelle scène est représentée ?"
python -m app.cli --messe 2026-09-17     # lectures brutes, sans passer par l'IA
python -m app.cli --etat                 # état du corpus et de la configuration
```

Les recherches en cours s'affichent sur la sortie d'erreur, la réponse sur la
sortie standard — `python -m app.cli "…" > reponse.md` ne garde que la réponse.

### Interface web

```bash
uvicorn app.api:application --reload
# puis http://127.0.0.1:8000
```

L'interface accepte le texte et l'image, et montre en direct ce que l'assistant
va chercher (« Recherche « mensonge » dans le Nouveau Testament chez AELF »),
ce qui rend ses sources vérifiables au fil de la réponse.

### API HTTP

| Route | Rôle |
|---|---|
| `GET /api/etat` | Modèle, zone, taille du corpus |
| `GET /api/messe?date=AAAA-MM-JJ&zone=romain` | Lectures brutes depuis AELF |
| `POST /api/question` (`texte`, `image` facultative) | Réponse diffusée en Server-Sent Events |

Les événements SSE portent un champ `type` : `outil` (une recherche commence),
`resultat` (ce qu'elle a donné), `texte` (fragment de réponse), `fin`, `erreur`.

---

## Mise en ligne

### GitHub Pages

Rien à faire : `index.html` et `site/` sont servis tels quels depuis la branche,
et `.nojekyll` empêche GitHub de retransformer le README en page.

Le corpus, lui, est déposé par le workflow **Corpus AELF**. Il tourne chaque
nuit pour les lectures du jour, et peut être lancé à la main depuis l'onglet
Actions du dépôt. La première exécution est longue — 1 334 chapitres, une
demi-seconde entre chaque requête par courtoisie pour AELF ; les suivantes ne
font que rafraîchir.

Une clé API, en revanche, ne peut pas vivre sur une page : elle serait lisible
par tous les visiteurs. C'est pourquoi `assistant-ia.html` demande la sienne au
visiteur, et pourquoi offrir l'IA sans rien demander suppose un serveur — objet
de la section suivante.

### Avec Docker

```bash
docker build -t assistant-biblique .
docker run -p 8000:8000 \
  -e ANTHROPIC_API_KEY=sk-ant-... \
  -v assistant-donnees:/données \
  assistant-biblique
```

Le volume `assistant-donnees` conserve le corpus biblique. Sans lui, il est
retéléchargé depuis AELF à chaque redémarrage — une dizaine de minutes, et
autant de charge inutile pour AELF.

L'image tourne telle quelle chez tout hébergeur acceptant Docker : Render,
Railway, Fly.io, Hugging Face Spaces, Scaleway, ou un VPS avec nginx en façade.
La plupart imposent le port par la variable `PORT`, que l'image respecte.

### Variables à définir en production

| Variable | Rôle |
|---|---|
| `ANTHROPIC_API_KEY` | Obligatoire. À passer en secret, jamais dans le dépôt. |
| `PORT` | Port d'écoute, souvent imposé par l'hébergeur. |
| `BIBLE_DONNEES` | Emplacement du corpus (`/données` dans l'image). |
| `BIBLE_INGERER_AU_DEMARRAGE` | `0` pour ne pas télécharger le corpus au premier lancement. |

---

## Ce qu'on a « appris » à l'IA

Tout tient dans `app/ia/prompts.py`, en trois leçons.

**1. D'où elle a le droit de parler.** Deux sources, jamais de réponse de
mémoire, aucune référence qu'elle n'ait pas lue par un outil, et l'aveu franc
quand la recherche ne donne rien.

**2. Comment chercher.** Une méthode par type de question. La plus utile est
celle des questions thématiques : le vocabulaire de la traduction liturgique
n'est pas celui de la question posée. « Tromperie » ne figure presque nulle
part ; « mensonge », « séduire », « ruse », « hypocrisie », « faux témoignage »
y sont. L'assistant est donc instruit de lancer **plusieurs recherches de
vocabulaires différents** avant de conclure — et l'index s'y prête, puisqu'il
indexe les mots par radical (« tromperie », « tromper » et « trompeur »
tombent dans le même seau, voir `app/corpus/recherche.py`).

**3. Comment écrire.** La réponse d'abord, en une ou deux phrases ; puis des
paragraphes d'une idée ; des phrases courtes ; le présent de narration pour les
récits ; une à trois citations, entre guillemets français et suivies de leur
référence ; la distinction explicite entre ce que dit le texte et ce qu'on en
comprend ; pas de sermon ; et les références en fin de réponse, avec les liens
AELF consultés.

---

## Architecture

```
app/
├── config.py              Domaines autorisés, modèle, chemins
├── sources/
│   ├── aelf.py            Client AELF : messe du jour + navigateur biblique
│   ├── sanctimaps.py      Client sanctimaps.fr
│   └── cache.py           Cache disque (une requête par ressource et par semaine)
├── corpus/
│   ├── livres.py          Les 73 livres : codes AELF, noms, alias, chapitres
│   ├── references.py      « Rm 12, 1-5 » → structure exploitable
│   ├── recherche.py       Index BM25 avec radicaux français
│   └── ingestion.py       Téléchargement du corpus, reprise sur interruption
├── ia/
│   ├── prompts.py         Les trois leçons ci-dessus
│   ├── outils.py          Les cinq outils du modèle
│   └── agent.py           Boucle question → recherches → réponse
├── api.py                 FastAPI + SSE
└── cli.py                 Ligne de commande

index.html                 La page servie par GitHub Pages
site/
├── livres.js              Table des livres — engendrée depuis livres.py
├── prompt.js              Le même prompt système, adapté aux outils du navigateur
├── claude.js              Appel de l'API et boucle d'outils, côté navigateur
├── app.js                 Interface
└── style.css

Dockerfile, entrypoint.sh  Mise en ligne de la version serveur
scripts/exporter_livres.py Régénère site/livres.js
```

Le modèle par défaut est **Claude Opus 5** (`claude-opus-5`), en raisonnement
adaptatif, effort `high` — réglable par `BIBLE_MODELE` et `BIBLE_EFFORT`.

La boucle d'outils est écrite à la main plutôt qu'avec le `tool_runner` du SDK,
pour diffuser en direct les recherches en cours et borner le nombre de tours
(`BIBLE_TOURS_MAX`, 12 par défaut).

---

## Tests

```bash
pytest        # version serveur — 106 tests
npm test      # les deux pages — 19 parcours dans un vrai navigateur
```

Aucun accès réseau : les réponses d'AELF, de sanctimaps et de l'API Anthropic
sont toutes simulées, et aucune clé n'est nécessaire.

Les tests Python couvrent l'analyse des références, l'index de recherche,
l'extraction du HTML liturgique, le refus des domaines non autorisés, la boucle
de dialogue et les routes HTTP.

Les tests du navigateur chargent réellement les pages dans Chromium.

Pour `index.html` (12 parcours) : les lectures du jour, la recherche et ses
familles de mots, le filtre par testament, la lecture suivie, le passage d'un
résultat à son chapitre, et le comportement quand le corpus manque. L'un d'eux
vérifie qu'**aucune requête ne sort du site**.

Pour `assistant-ia.html` (7 parcours) : les appels à `api.anthropic.com` sont
interceptés et un flux d'événements identique à celui de l'API y est rejoué.
Sont vérifiés l'analyse du flux, la boucle d'outils, le renvoi des blocs de
réflexion avec leur signature, l'envoi des images, les en-têtes et les messages
d'erreur.

```bash
npm run capture   # relit le rendu en clair et en sombre, sans clé
```

---

## Limites connues, à lire avant de déployer

* **Les sélecteurs HTML n'ont pas pu être validés contre le site réel.**
  L'environnement où ce code a été écrit n'avait pas accès à `aelf.org` ni à
  `sanctimaps.fr` (bloqués par la politique réseau). L'extraction des versets
  (`_extraire_versets`) essaie donc **trois stratégies** successives et échoue
  proprement — `SourceIndisponible`, jamais un texte mutilé — si aucune ne
  marche. Premier test à faire après clonage :

  ```bash
  python -c "from app.sources.aelf import ClientAelf; print(ClientAelf().chapitre('Jon', 1).texte)"
  ```

  Si la sortie est vide ou l'erreur explicite, adaptez `_extraire_versets` dans
  `app/sources/aelf.py` : c'est le seul endroit à corriger. Même chose pour
  `_texte_principal` dans `app/sources/sanctimaps.py`.
* **Les codes de livres** (`Gn`, `Rm`, `1Co`…) suivent les abréviations
  liturgiques françaises usuelles. Si AELF en emploie une autre pour un livre,
  corrigez le champ `code` dans `app/corpus/livres.py`.
* **L'index de recherche est lexical, pas sémantique.** Il trouve les mots et
  leurs familles, pas les synonymes lointains — d'où la consigne donnée au
  modèle de varier ses recherches. Un index vectoriel améliorerait le rappel sur
  les questions abstraites.
* **Le cache est daté d'une semaine** (`BIBLE_CACHE_TTL`). Pour la messe du
  jour, c'est sans conséquence (une date = une page) ; réduisez-le si vous
  voulez suivre des corrections éditoriales d'AELF au plus près.
* **La version page n'a pas été essayée contre l'API réelle**, faute de clé dans
  l'environnement de développement. Tout ce qui pouvait l'être l'a été dans un
  vrai navigateur, API simulée : analyse du flux, boucle d'outils, signatures,
  images, en-têtes, erreurs. Ce qui reste à confirmer à la première question
  posée avec une vraie clé, ce sont deux points de contrat côté API :
  l'acceptation de l'en-tête d'accès navigateur, et le comportement exact de
  `web_fetch` sur les adresses d'AELF. Si `web_fetch` refuse une adresse, le
  modèle se rabat sur `web_search` — c'est prévu, mais la réponse sera moins
  précise.
* **La recherche thématique est plus faible dans la version page.** Sans index
  local, le modèle propose des passages de mémoire puis les vérifie un par un.
  C'est honnête — rien n'est cité sans avoir été lu — mais moins exhaustif que
  le balayage BM25 de la version serveur.

---

## Droits

Le texte biblique et les lectures proviennent de l'**AELF** (Association
épiscopale liturgique pour les pays francophones) ; les notices de saints, de
**sanctimaps.fr**. Ce dépôt ne redistribue aucun de ces textes : il les
télécharge pour un usage local (`data/`, exclu du dépôt par `.gitignore`).
Vérifiez les conditions d'utilisation de chaque site avant tout usage public ou
commercial.
