# LucidNews — frontend

Statut : **3 écrans construits** (Édition, Archives, Santé des sources), branchés
sur l'API en lecture seule du moteur Python. Détail d'une news et Préférences sont prévus.

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
| Détail d'une news | Article + colonne Fiabilité / sources / discussion | Analyse, fiabilité, corroborations |
| Archives ✅ | Retrouver une édition par date (calendrier + liste) | API `/api/editions` |
| Préférences | Langues, catégories, seuil, fréquence, offre affichée | Modèle d'abonné et préférences |
| Santé des sources ✅ | Chiffres clés, volume par run, tableau filtrable | API `/api/sources` |

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

## API (lecture seule)

Commande `lucidnews-api` : lit l'archive SQLite, n'écrit jamais, écoute sur
localhost. Aucune dépendance Python ajoutée (serveur HTTP de la bibliothèque standard).

| Route | Contenu |
|---|---|
| `GET /api/editions` | Runs ayant publié une édition |
| `GET /api/editions/latest?lang=fr` | Dernière édition, dans une langue |
| `GET /api/editions/<id>?lang=fr` | Une édition précise |
| `GET /api/sources?days=14` | Santé des sources configurées (1 à 90 jours) et volume par run |

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
