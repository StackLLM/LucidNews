# LucidNews — frontend

Statut : **6 écrans construits** (Édition, Fiche d'une news, Archives, Santé des
sources, Préférences, Qualité), branchés sur l'API du moteur Python.

## Lancer

```bash
uv run lucidnews-api          # à la racine du dépôt : API sur 127.0.0.1:8765
cd frontend && npm install && npm run dev   # http://localhost:5173
```

API sur un autre port : `LUCIDNEWS_API=http://127.0.0.1:8766 npm run dev`.

Vérifications : `npm run typecheck` · `npm test` · `npm run build`.

## Documents

- [Direction UI](docs/direction-ui.md) : analyse des modèles, ce qu'on garde, ce qu'on écarte, couleurs, typographie.
- [Dépendances](docs/dependances.md) : chaque librairie et sa justification.

## Direction artistique

Premium, calme, fin, professionnel. Impressionnant sans être chargé.

- Fond clair teinté, cartes blanches pour lire, verre pour ce qui flotte.
- Profondeur par ombres très diffuses, pas par des couleurs vives.
- Micro-interactions courtes et douces, toujours désactivables.
- La fiabilité d'une information est l'élément visuel le plus clair de l'écran.

## Écrans prévus

| Écran | Rôle | Données existantes côté moteur |
|---|---|---|
| Édition du jour ✅ | Lire le digest : sections, score, fiabilité. Filtre de date : dernière édition, ou toutes les éditions d'un jour, d'un mois ou d'une année (adresse `?day=`, `?month=`, `?year=`), sans limite de news. Filtre de domaine à côté (`?domain=`) | API `/api/editions/latest`, `/api/editions/period` |
| Fiche d'une news ✅ | Article complet + colonne Fiabilité (éditeur, affirmation, preuve, corroboration), actions, éditions | API `/api/items/<id>` |
| Archives ✅ | Retrouver une édition par date (calendrier + liste) | API `/api/editions` |
| Préférences ✅ | Abonnés (ajout, suppression), langue, thèmes, sources, rythme, niveau de détail (bref / complet), importance, infos non confirmées, limite, offre affichée ; aperçu de l'e-mail dans un cadre sans script | API `/api/subscribers`, `/api/subscribers/<id>/preview` (local) |
| Sources ✅ | Onglet Sources : santé (chiffres clés, volume par run), sources configurées par domaine ou par type, domaine affiché sur chaque source : activer, ajouter, modifier, tester, supprimer. Onglet Domaines : couverture des 12 catégories, lacunes, domaines suivis, sources recommandées | API `/api/sources`, `/api/coverage`, `/api/catalog`, `/api/sources/config`, `/api/sources/test` (local) |

| Qualité ✅ | Vue d'ensemble de la veille (couverture, diversité, santé, fraîcheur, doublons, filtrage, fiabilité), annotation à l'aveugle, résultats | API `/api/quality/overview`, `/api/eval/*` (local), voir `docs/evaluation.md` |
| Réglages ✅ | Runs (lancer, suivre, planifier, historique), clés API (jamais réaffichées), IA, collecte, sélection, fiabilité, archive, versions précédentes | API `/api/runs`, `/api/schedule`, `/api/settings`, `/api/secrets` (local) |

Pas de paiement, pas de paywall : l'offre Premium est seulement affichée.

## Architecture prévue

```
frontend/
├── src/
│   ├── app/          routes, mise en page, fournisseurs (requêtes, animations)
│   ├── design/       tokens, styles globaux, composants de base (Card, Button, Badge…)
│   ├── features/     edition/, item/, archive/, preferences/, sources/, quality/, settings/
│   ├── lib/          client API, schémas zod, i18n, formats
│   └── test/
└── docs/
```

- Code et noms de composants en anglais, comme le moteur Python.
- Textes de l'interface en EN et FR, extensibles.

## API

Commande `lucidnews-api` : lit l'archive SQLite sans jamais l'écrire, écoute sur
localhost. Aucune dépendance Python ajoutée (serveur HTTP de la bibliothèque standard).
Ce qui s'écrit, en local seulement : les préférences des abonnés (`data/subscribers.json`),
les annotations, la configuration (`data/config.json`, avec copie dans `data/backups/`)
et les clés API (`.env` du projet).

| Route | Contenu |
|---|---|
| `GET /api/editions?limit=30` | Runs ayant publié une édition (jusqu'à 2000) |
| `GET /api/sources/domains?days=90` | Domaine de chaque source (archive, sinon catalogue) |
| `GET /api/editions/period?since=&until=&lang=` | Les news de toutes les éditions commencées dans la période (instants ISO), sans doublon  ; toutes sont listées |
| `GET /api/editions/latest?lang=fr` | Dernière édition, dans une langue |
| `GET /api/editions/<id>?lang=fr` | Une édition précise |
| `GET /api/items/<id>?lang=fr` | Une news : contenu, fiabilité détaillée, éditions qui l'ont publiée |
| `GET /api/sources?days=14` | Santé des sources configurées (1 à 90 jours) et volume par run |
| `GET /api/coverage?days=14` | Couverture des 12 catégories d'après l'archive, domaines suivis, seuils de lacune |
| `GET /api/catalog?category=ai` | Sources recommandées absentes de la config |

| `GET /api/preferences/options` | Langues, thèmes, sources filtrables, offres |
| `GET /api/subscribers` | Abonnés et leurs préférences |
| `POST /api/subscribers` | Ajouter un abonné (`{"email": …}`) |
| `PUT /api/subscribers/<id>` | Enregistrer ses préférences |
| `DELETE /api/subscribers/<id>` | Le supprimer (rien n'est conservé) |
| `GET /api/subscribers/<id>/preview` | L'e-mail de cet abonné tel qu'il serait envoyé (objet, HTML, texte), depuis l'archive |
| `GET /api/quality/overview?days=14` | Indicateurs de la veille sur la période, depuis l'archive (résumé des annotations seulement en local) |
| `GET /api/eval/items` · `GET /api/eval/report` | News à annoter (sans l'avis de l'IA) · résultats |
| `PUT` / `DELETE /api/eval/annotations/<id>` | Enregistrer / effacer une annotation (local) |
| `GET /api/settings` · `PUT /api/settings` | Réglages modifiables, options, champs verrouillés, version · enregistrer (`{version, values}`) |
| `GET /api/settings/backups` · `POST /api/settings/restore` | Versions précédentes de la config · en restaurer une (`{name}`) |
| `GET /api/secrets` | Variables de clés utilisées par la config et leur état (jamais leur valeur) |
| `PUT` / `DELETE /api/secrets/<NOM>` | Enregistrer (`{value}`) / retirer une clé du fichier `.env` |
| `GET /api/sources/config` · `POST /api/sources/config` | Sources configurées, état, valeurs modifiables, version · ajouter (`{version, kind, values}`) |
| `PUT` / `DELETE /api/sources/config/<clé>` | Modifier, activer ou désactiver (`{version, values}`) / supprimer (`{version}`) |
| `GET /api/runs` · `POST /api/runs` | Derniers runs avec leur statut · lancer un run (local) |
| `GET /api/runs/current` | Run en cours ou dernier run lancé depuis l'écran : étape, journal nettoyé, code de sortie |
| `GET /api/schedule` · `PUT /api/schedule` | Planification launchd · l'écrire (`{enabled, hour, minute, weekdays}`) ou la retirer (`{enabled: false}`) |
| `POST /api/sources/test` | Tester une source enregistrée (`{key}`) ou un brouillon (`{kind, values}`), sans IA ni écriture |

### Réglages et clés API

- Mêmes protections que les préférences : localhost seulement, Host et Origin vérifiés, JSON seulement.
- La config est modifiée **brute** : seuls les champs changés sont écrits, les `${VARIABLE}`
  restent intacts, et un champ qui en contient une est verrouillé dans l'écran.
- Chaque écriture est vérifiée par le modèle `Config`, faite de façon atomique, et précédée
  d'une copie horodatée (les 10 dernières sont gardées). Si le fichier a changé depuis sa
  lecture, l'écriture est refusée (409).
- Les clés vont dans `.env` (non versionné, droits 600). Seuls les noms de variables cités
  par la config sont acceptés. Une valeur n'est jamais renvoyée, journalisée ni répétée
  dans un message d'erreur. Une clé collée par erreur dans le champ « Variable de la clé »
  est refusée.
- Une variable déjà définie dans le terminal qui a lancé LucidNews est prioritaire sur
  `.env` : l'écran le signale.

### Runs et planification

- « Lancer un run » démarre le pipeline dans un processus séparé, avec la même commande
  qu'en terminal (`python -m src.main --data-dir …`) : même édition. Sortie dans
  `data/runs/` (ignoré par Git).
- Un seul run à la fois, quelle que soit son origine (interface, terminal, planification) :
  le pipeline tient un verrou (`data/run.lock`) pendant tout le run ; un second lancement
  est refusé (409 dans l'interface, code 75 en terminal). Le verrou se libère seul si le
  run plante.
- Suivi en direct : étape (collecte, analyse IA, sélection, édition, fini) et dernières
  lignes du journal, sans couleurs ni valeur de clé ; la page interroge l'API toutes les
  2 s pendant un run, même en arrière-plan.
- Planification (macOS) : une tâche launchd `com.lucidnews.pipeline` dans
  `~/Library/LaunchAgents`, écrite, chargée et retirée depuis l'écran. Elle lance la même
  commande, ne contient aucune clé (elles restent dans `.env`) et écrit dans
  `data/runs/scheduled.log`. Mac en veille : le run part au réveil.
- Historique : les 20 derniers runs de l'archive avec leur statut réel (réussi, rien de
  nouveau, échec) et leur erreur.

### Gestion des sources

- Mêmes protections que les réglages, et même écriture : config brute, copie de
  sauvegarde, version vérifiée, `${VARIABLE}` conservées.
- Chaque source porte la clé de la santé des sources : l'écran joint les deux.
  Une source sans historique est marquée « Pas encore collectée » ; une source
  coupée par l'interrupteur Reddit ou Telegram est « En pause ».
- Ajout : flux RSS, dépôt ou compte GitHub, subreddit, compte Reddit, chaîne
  Telegram. Les liens collés sont acceptés (`r/rust`, `https://t.me/s/…`, URL GitHub).
  Doublons refusés (même clé, ou même flux).
- Sources intégrées (Hacker News, OSS Insight, GDELT, Google News) : activer et régler,
  pas supprimer. X (Twitter) : lecture seule (cookies ou jeton Apify, dans `config.json`).
- Une adresse de flux doit être publique : `localhost`, adresses privées et
  `${VARIABLE}` sont refusés. Le test vérifie aussi chaque requête et chaque redirection.
- Le test lance le vrai collecteur sur 7 jours, 45 s au plus, sans IA ni archive, et
  dit combien de contenus tombent dans la fenêtre de collecte. Un jeton d'une
  `${VARIABLE}` n'apparaît jamais dans sa réponse.

### Vue d'ensemble de la qualité

- Page Qualité, premier onglet (`/quality`). Annoter : `/quality/annotate`. Résultats : `/quality/results`.
- Chaque carte dit d'où viennent ses chiffres et sur quelle période.
- Les compteurs de doublons (fusions par URL, par sujet, news au-dessus du seuil) sont
  enregistrés par run depuis le lot 19. Les runs plus anciens sont comptés à part, avec
  « pas de donnée », jamais estimés.
- Fraîcheur : âge d'une news publiée au lancement du run qui l'a publiée (médiane, 90e centile, part sous 24 h).
- Qualité du filtrage : résumé des annotations (lot 11), avec « échantillon insuffisant »
  sous 30 news comparées ; seulement avec l'API locale.

### Domaines et couverture

- Tous les chiffres viennent de l'archive : catégories données par l'IA, source qui a
  collecté la news, publication par un run, étiquette de fiabilité. Une news sans
  analyse IA n'est pas comptée (le nombre est affiché).
- Une source active est une source configurée et activée qui a alimenté le domaine
  sur la période. Une source qui ne l'est plus reste listée, barrée.
- Une recommandation vient du catalogue livré avec le projet et n'est jamais une
  source configurée (ni par sa clé, ni par l'adresse de son flux). Elle s'ajoute avec
  la route du lot 17, après un test.
- Suivre un domaine, l'option « ne publier que les domaines suivis » et les seuils de
  lacune passent par `PUT /api/settings` (local).

### Préférences : version locale, sans comptes

- Les routes abonnés n'existent que si l'API écoute sur localhost (sinon : 403).
- Requêtes refusées si le nom d'hôte n'est pas local (protection DNS rebinding)
  ou si elles viennent d'un autre site (en-tête `Origin`).
- Écritures en JSON seulement (un formulaire d'un autre site ne peut pas en envoyer
  sans autorisation du navigateur), corps limité à 64 Ko.
- Un abonné est désigné par un identifiant opaque (empreinte de l'e-mail) :
  l'adresse n'apparaît jamais dans les URL.
- L'offre (Gratuite / Premium) est affichée, jamais modifiable depuis l'écran :
  pas de paiement.
- L'aperçu de la newsletter est affiché dans un `iframe` avec `sandbox` sans
  `allow-scripts` : le HTML des sources ne peut rien exécuter. Les liens s'ouvrent
  dans un nouvel onglet.

Les tests du frontend utilisent les vraies réponses de l'API sur l'archive
locale du 6 octobre 2026 (`src/test/fixtures/`).

## Points connus

- Un fichier JS par écran : les graphiques (≈ 107 Ko compressé) ne se chargent que
  sur Santé des sources, le calendrier que sur Archives.
- Le socle commun pèse encore ≈ 160 Ko compressé (React, routeur, animations,
  validation). Piste : version allégée de `motion` et de `zod`.
- Sur téléphone, la navigation passe dans une barre flottante en bas.
- Les couleurs du graphique ont été validées (daltonisme, contraste). La couleur
  claire est sous 3:1 de contraste : la légende et la vue Tableau compensent.
