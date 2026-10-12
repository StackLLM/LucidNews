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
- Un **compte de réseau social enregistré** l'emporte sur la plateforme (voir ci-dessous).
- Ordre de priorité : `trust` du flux RSS > comptes (`reliability.accounts`, puis registre) > `reliability.domains` de la config > registre intégré des domaines (`lucidnews/reliability/registry.py`).

### Comptes de réseaux sociaux

Un message publié sur un réseau social est jugé sur **son compte**, pas sur la
plateforme. `mastodon.social` est une plateforme communautaire, mais
`@bagder@mastodon.social` est l'auteur de curl qui parle de curl.

| Plateforme | Identifiant | Reconnu dans les URL |
|---|---|---|
| X | `x:<compte>` | `x.com/<compte>/…`, `twitter.com/<compte>/…` |
| Mastodon (fédiverse) | `mastodon:<utilisateur>@<serveur>` | `<serveur>/@<utilisateur>/…` |
| Bluesky | `bluesky:<identifiant>` | `bsky.app/profile/<identifiant>/…` |
| Telegram | `telegram:<canal>` | `t.me/<canal>/…`, `t.me/s/<canal>/…` |

- Registre intégré : seulement des comptes **vérifiés à la main** sur leur page publique (octobre 2026) : `mastodon:bagder@mastodon.social` (curl), `telegram:durov` (Telegram), `bluesky:bsky.app` (Bluesky).
- Les comptes X ne sont pas vérifiables sans connexion : aucun n'est inscrit par défaut. Les ajouter par projet avec `reliability.accounts`.
- Deux comptes différents d'une même plateforme comptent comme deux éditeurs indépendants pour la corroboration.
- Limite : « officiel » vaut pour tout ce que publie le compte. Garder la liste aux comptes qui parlent surtout de leur propre travail.

### Couverture du registre

Domaines et comptes, par famille : laboratoires d'IA, éditeurs cloud et logiciels,
projets open source, organismes de normalisation, autorités (États-Unis, Royaume-Uni,
France avec tout `gouv.fr`, CNIL, ARCEP, ANSSI ; Union européenne avec tout
`europa.eu` ; Allemagne, Pays-Bas, Italie, Espagne), recherche (dont Inria et CNRS),
presse technique anglophone, française (LeMagIT, JDN, L'Usine Digitale, Silicon,
Clubic, Frandroid, Les Numériques, Next, Numerama…) et européenne (heise, Golem,
Euractiv, Politico Europe), plateformes communautaires (dont LinuxFr, Developpez,
Journal du hacker, Korben).

## 2. Statut de l'affirmation (`ClaimStatus`)

L'IA applique ces définitions (voir `lucidnews/ai/prompting/analysis.py`) :

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

**Sources de corroboration.** Le dédoublonnage compare chaque news retenue avec d'autres articles, envoyés à l'IA comme « références » dans le même appel :

- les news du run restées **sous le seuil** de score (un article reconnu mal noté peut donc confirmer une news retenue) ;
- les news de l'**archive** publiées dans les 72 dernières heures (`reliability.corroboration_lookback_hours`), par exemple l'annonce officielle de la veille.

Seules les références d'un éditeur `official` ou `reputable` sont envoyées, car les autres ne comptent pas. Il y en a au plus 30 par rubrique (`reliability.corroboration_max_references`, `0` pour couper), les plus récentes d'abord. Une référence n'est jamais publiée ni retirée : elle ajoute seulement son adresse aux corroborations de la news qu'elle couvre. Cela ne coûte pas d'appel IA en plus, sauf pour une rubrique d'une seule news, qui est maintenant comparée à ses références.

Le digest l'affiche, par exemple `Fiable · source communautaire · corroboré par 2 source(s) indépendante(s)`. Le détail (sites concernés) est dans `processing.reliability.corroborated_by` et `reasons`.

## Effets dans le produit

- **Digest** : chaque item affiche une ligne « Fiabilité », par exemple `Confirmé · source officielle`. Les items « Non vérifié » et « Rumeur » portent ⚠️ et la mention explicite qu'ils ne sont pas confirmés.
- **Enrichissement** : l'étiquette est transmise à l'IA. Pour `unverified` ou `rumor`, elle doit attribuer l'affirmation (« selon… », « une fuite suggère… »), signaler qu'elle n'est pas confirmée et nuancer le titre.
- **Filtrage global** : `reliability.exclude_labels` retire des étiquettes du digest, par exemple `["rumor"]`.
- **Newsletter** : chaque abonné peut refuser les items non confirmés (`include_unconfirmed: false`).
- **Quota IA épuisé** : une news que l'IA n'a pas pu lire (quota ou budget de tokens épuisé) prend toujours l'étiquette « Non vérifié », même venant d'une source officielle, car personne n'a vérifié l'affirmation. Elle est publiée à part, dans une section « Sans analyse IA », avec seulement son titre d'origine, sa source et son lien. Aucun texte de l'IA, aucun score. Cela n'arrive **que** si le quota est épuisé : une autre erreur d'analyse garde la news hors du digest.
- **Traçabilité** : `processing.reliability.reasons` explique la décision (domaine, statut, preuve citée par l'IA). Ces raisons sont visibles dans les étapes MCP.

## Configuration

```json
"reliability": {
  "domains": { "internal-blog.example": "official", "some-tabloid.example": "community" },
  "accounts": { "x:openai": "official", "mastodon:someone@fosstodon.org": "reputable" },
  "exclude_labels": []
},
"sources": { "rss": [ { "name": "Python Insider", "url": "https://pythoninsider.blogspot.com/feeds/posts/default", "trust": "official" } ] }
```

## Limites connues et évolutions

- La vérification s'appuie sur le contenu collecté. L'IA ne consulte pas d'autres sources pendant l'analyse ; la recherche web n'intervient qu'à l'enrichissement.
- La corroboration repose sur le jugement de l'IA (« même événement »). Une erreur de rapprochement avec un site officiel ferait passer une news à « Confirmé ». La consigne demande de laisser une référence de côté en cas de doute ; l'écran Qualité permet de repérer ces cas (« faux fiables »).
- Le registre intégré est une base de départ et doit être enrichi au fil de l'usage. La commande `lucidnews-sources` et l'écran Qualité aident à repérer les domaines encore inconnus.
- Un changement de registre s'applique aux **prochains runs**. Les digests déjà envoyés ne changent pas. L'écran Qualité, lui, recalcule toujours avec le registre actuel.

## Recalculer les étiquettes de l'archive

Après un changement de registre, la commande `lucidnews-reassess` recalcule les étiquettes des news archivées, sans appel IA : le statut d'affirmation donné par l'IA est gardé. Les éditions passées de l'interface affichent alors les nouvelles étiquettes.

```bash
uv run lucidnews-reassess            # aperçu : ce qui changerait
uv run lucidnews-reassess --apply    # écrit les nouvelles étiquettes
uv run lucidnews-reassess --json     # aperçu en JSON
```
