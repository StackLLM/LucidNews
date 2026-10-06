# Fiabilité des informations

Principe : **une information non confirmée n'est jamais présentée comme un fait.**

La fiabilité d'un item combine deux signaux indépendants :

1. **Qui publie** : le niveau de confiance de l'éditeur de l'URL principale. Calcul déterministe, sans IA.
2. **Ce qui est affirmé** : le statut de l'affirmation principale, jugé par l'IA pendant l'analyse, à partir des seules preuves fournies.

## 1. Confiance de l'éditeur (`SourceTier`)

| Niveau | Exemples |
|---|---|
| `official` | Site, blog, documentation ou release de l'acteur concerné (openai.com, aws.amazon.com, kubernetes.io, release GitHub du projet), organismes de normalisation et autorités de sécurité (W3C, IETF, NIST, CISA, ANSSI / CERT-FR) |
| `reputable` | Presse technique établie et experts reconnus (LWN, Ars Technica, The Register, BleepingComputer, Le Monde Informatique…), publications de recherche (arXiv, ACM, IEEE) |
| `community` | Agrégateurs, forums, réseaux sociaux, plateformes de blog ouvertes (Hacker News, Reddit, X, Medium, dépôt GitHub quelconque…) |
| `unknown` | Domaine absent du registre |

Règles de résolution :

- C'est l'**URL de l'article** qui compte, pas le canal de découverte.
- Le domaine le plus spécifique gagne : `lilianweng.github.io` (reconnu) l'emporte sur `github.io` (communautaire).
- `github.com/<owner>/<repo>/releases/...` est `official` : c'est une publication du projet lui-même.
- Ordre de priorité : `trust` du flux RSS > `reliability.domains` de la config > registre intégré (`src/reliability/registry.py`).

## 2. Statut de l'affirmation (`ClaimStatus`)

L'IA applique ces définitions (voir `src/ai/prompting/analysis.py`) :

| Statut | Signification |
|---|---|
| `confirmed` | Annoncé, documenté ou livré par l'acteur concerné, ou démontré dans l'item |
| `reported` | Rapporté par un média ou un expert crédible, sans confirmation de l'acteur |
| `unverified` | Source unique ou faible, ou preuves qui ne soutiennent pas le titre |
| `rumor` | Fuite, sources anonymes, spéculation, prédiction, « selon certaines rumeurs » |

Popularité, votes et commentaires ne comptent pas comme preuve. En cas de doute, l'IA doit choisir le niveau le plus faible. Une réponse invalide est traitée comme « non évaluée ».

## 3. Étiquette finale (`ReliabilityLabel`)

| Éditeur \ Affirmation | non évaluée | `confirmed` | `reported` | `unverified` | `rumor` |
|---|---|---|---|---|---|
| `official` | Confirmé | Confirmé | Confirmé | Non vérifié | Rumeur |
| `reputable` | Fiable | Fiable | Fiable | Non vérifié | Rumeur |
| `community` / `unknown` | Non vérifié | Fiable | Non vérifié | Non vérifié | Rumeur |

Règles clés :

- Une rumeur reste une rumeur, même sur un domaine officiel.
- Une source faible ne monte qu'à « Fiable », et seulement si l'IA a trouvé une confirmation explicite dans le contenu, ou si l'information est corroborée (voir ci-dessous).

## 4. Corroboration

Quand le dédoublonnage par sujet fusionne plusieurs articles qui racontent le même événement, les adresses des articles fusionnés sont gardées. Chaque **site différent** du site principal, de niveau `official` ou `reputable`, compte comme une corroboration indépendante. Les sous-domaines d'un même site comptent pour un seul site (`blog.example.com` = `example.com`). Les sources communautaires ou inconnues ne comptent pas.

| Situation | Effet |
|---|---|
| Un site **officiel** (l'acteur concerné) rapporte aussi l'événement | → Confirmé |
| Affirmation `unverified` + au moins **2** sites reconnus | → Fiable |
| Étiquette « Non vérifié » (source faible) + au moins **1** site reconnu | → Fiable |
| Affirmation `rumor` | Reste Rumeur, même répétée par plusieurs médias |

Le digest l'affiche, par exemple `Fiable · source communautaire · corroboré par 2 source(s) indépendante(s)`. Le détail (sites concernés) est dans `processing.reliability.corroborated_by` et `reasons`.

## Effets dans le produit

- **Digest** : chaque item affiche une ligne « Fiabilité », par exemple `Confirmé · source officielle`. Les items « Non vérifié » et « Rumeur » portent ⚠️ et la mention explicite qu'ils ne sont pas confirmés.
- **Enrichissement** : l'étiquette est transmise à l'IA. Pour `unverified` ou `rumor`, elle doit attribuer l'affirmation (« selon… », « une fuite suggère… »), signaler qu'elle n'est pas confirmée et nuancer le titre.
- **Filtrage global** : `reliability.exclude_labels` retire des étiquettes du digest, par exemple `["rumor"]`.
- **Newsletter** : chaque abonné peut refuser les items non confirmés (`include_unconfirmed: false`).
- **Traçabilité** : `processing.reliability.reasons` explique la décision (domaine, statut, preuve citée par l'IA). Ces raisons sont visibles dans les étapes MCP.

## Configuration

```json
"reliability": {
  "domains": { "internal-blog.example": "official", "some-tabloid.example": "community" },
  "exclude_labels": []
},
"sources": { "rss": [ { "name": "Python Insider", "url": "https://pythoninsider.blogspot.com/feeds/posts/default", "trust": "official" } ] }
```

## Limites connues et évolutions

- La vérification s'appuie sur le contenu collecté. L'IA ne consulte pas d'autres sources pendant l'analyse ; la recherche web n'intervient qu'à l'enrichissement.
- La corroboration ne porte que sur les news qui ont passé le seuil de score et sur un même run : un article reconnu mal noté, ou publié la veille, n'est pas encore pris en compte (voir la [roadmap](roadmap.md)).
- Le registre intégré est une base de départ et doit être enrichi au fil de l'usage.
