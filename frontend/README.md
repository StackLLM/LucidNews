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
| Édition du jour ✅ | Lire le digest : sections, score, fiabilité | API `/api/editions/latest` |
| Fiche d'une news ✅ | Article complet + colonne Fiabilité (éditeur, affirmation, preuve, corroboration), actions, éditions | API `/api/items/<id>` |
| Archives ✅ | Retrouver une édition par date (calendrier + liste) | API `/api/editions` |
| Préférences ✅ | Abonnés (ajout, suppression), langue, thèmes, sources, rythme, importance, infos non confirmées, limite, offre affichée | API `/api/subscribers` (local) |
| Santé des sources ✅ | Chiffres clés, volume par run, tableau filtrable | API `/api/sources` |

| Qualité ✅ | Annotation à l'aveugle des news, résultats (sélection, importance, thèmes, affirmation, faux fiables) | API `/api/eval/*` (local), voir `docs/evaluation.md` |

Pas de paiement, pas de paywall : l'offre Premium est seulement affichée.

## Architecture prévue

```
frontend/
├── src/
│   ├── app/          routes, mise en page, fournisseurs (requêtes, animations)
│   ├── design/       tokens, styles globaux, composants de base (Card, Button, Badge…)
│   ├── features/     edition/, item/, archive/, preferences/, sources/
│   ├── lib/          client API, schémas zod, i18n, formats
│   └── test/
└── docs/
```

- Code et noms de composants en anglais, comme le moteur Python.
- Textes de l'interface en EN et FR, extensibles.

## API

Commande `lucidnews-api` : lit l'archive SQLite sans jamais l'écrire, écoute sur
localhost. Aucune dépendance Python ajoutée (serveur HTTP de la bibliothèque standard).
Seules les préférences des abonnés s'écrivent (`data/subscribers.json`).

| Route | Contenu |
|---|---|
| `GET /api/editions` | Runs ayant publié une édition |
| `GET /api/editions/latest?lang=fr` | Dernière édition, dans une langue |
| `GET /api/editions/<id>?lang=fr` | Une édition précise |
| `GET /api/items/<id>?lang=fr` | Une news : contenu, fiabilité détaillée, éditions qui l'ont publiée |
| `GET /api/sources?days=14` | Santé des sources configurées (1 à 90 jours) et volume par run |

| `GET /api/preferences/options` | Langues, thèmes, sources filtrables, offres |
| `GET /api/subscribers` | Abonnés et leurs préférences |
| `POST /api/subscribers` | Ajouter un abonné (`{"email": …}`) |
| `PUT /api/subscribers/<id>` | Enregistrer ses préférences |
| `DELETE /api/subscribers/<id>` | Le supprimer (rien n'est conservé) |
| `GET /api/eval/items` · `GET /api/eval/report` | News à annoter (sans l'avis de l'IA) · résultats |
| `PUT` / `DELETE /api/eval/annotations/<id>` | Enregistrer / effacer une annotation (local) |

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
