# Collecte et sources

## Fonctionnement

1. `PipelineOrchestrator.fetch_all_sources(since)` crée un client HTTP partagé et lance un scraper par type de source activé, **en parallèle**.
2. Chaque scraper renvoie des `ContentItem` publiés après `since` (par défaut : les dernières `collection.time_window_hours` heures, ou `--hours`).
3. Le résultat de chaque source est consigné dans un `FetchReport` : `success`, `empty` ou `failure` (avec l'erreur). Si toutes les sources échouent, le run s'arrête en erreur et un webhook d'échec est envoyé s'il est configuré.
4. Les items pointant vers la même URL normalisée sont fusionnés (`merged_sources` garde la liste des canaux).

Le **canal** (Hacker News, Reddit…) sert à découvrir une information. La **fiabilité** est évaluée sur l'URL principale : un post Hacker News qui pointe vers une release GitHub est jugé sur la release (voir [fiabilite.md](fiabilite.md)).

## Santé des sources

Chaque source configurée reçoit un **identifiant de source** : `rss/LWN.net`, `github/vllm-project/vllm`, `github/@torvalds`, `reddit/r/devops`, `telegram/@chaine`, `hackernews`…

À chaque run, l'archive garde pour chaque source :

- son statut : `success` (des news), `empty` (aucune news) ou `failure` (erreur) ;
- l'erreur ;
- le nombre de news collectées et retenues dans le digest.

Un flux RSS ou un dépôt GitHub en erreur est signalé individuellement, sans bloquer les autres.

Le rapport classe chaque source sur les 14 derniers jours :

| Statut | Règle |
|---|---|
| `dead` (morte) | En échec aux 3 derniers runs d'affilée |
| `failing` (en échec) | En échec à au moins la moitié de ses runs |
| `silent` (silencieuse) | Joignable, mais aucune news en 5 runs ou plus |
| `noisy` (bruyante) | Au moins 30 news, et moins de 2 % retenues |
| `healthy` (saine) | Le reste |

À la fin de chaque run, les sources `dead` et `failing` sont listées dans le terminal. Le rapport complet :

```bash
uv run lucidnews-sources              # tableau, 14 derniers jours
uv run lucidnews-sources --days 30 --status dead --status failing
uv run lucidnews-sources --json       # pour un outil ou un tableau de bord
```

Les seuils sont des constantes en tête de `src/source_health.py`.

## Types de sources

| Type | Clé de config | Ce qui est collecté | Prérequis |
|---|---|---|---|
| RSS / Atom | `sources.rss[]` | Articles de flux ; texte intégral optionnel via `content_extractor` | — |
| Hacker News | `sources.hackernews` | Top stories au-dessus de `min_score`, avec les meilleurs commentaires | — |
| GitHub | `sources.github[]` | `repo_releases` (releases d'un dépôt) ou `user_events` (activité d'un compte) | `GITHUB_TOKEN` recommandé |
| Reddit | `sources.reddit` | Subreddits et utilisateurs, avec commentaires | — |
| Telegram | `sources.telegram` | Messages de chaînes publiques | — |
| X / Twitter | `sources.twitter` | Comptes et mots-clés | `APIFY_TOKEN` ou cookies ([guide](twitter-cookies.md)) |
| OSS Insight | `sources.ossinsight` | Dépôts GitHub en tendance | — |
| GDELT | `sources.gdelt` | Recherche d'actualités mondiales | — |
| Google News | `sources.google_news` | Recherche Google News par requête | — |

Chaque entrée accepte :

- `enabled` : activer ou désactiver ;
- `category` : étiquette libre utilisée pour les **quotas** du digest (`digest.category_groups`) ;
- `profile` : profil éditorial forcé (`"tech-news"`), choix automatique (`"auto"`) ou liste de candidats ;
- `trust` (RSS uniquement) : niveau de confiance imposé pour les items de ce flux (`official`, `reputable`, `community`, `unknown`).

Pour un dépôt GitHub, `repo` accepte un nom (`"vllm"` avec `owner`), `"owner/repo"` ou une URL complète, normalisés au chargement.

Le détail de chaque scraper est dans [scrapers.md](scrapers.md) (anglais).

## Catalogue de sources de référence

`data/config.example.json` contient un catalogue vérifié (tous les flux répondaient au moment de l'écriture), qui couvre les 12 catégories :

| Catégorie | Sources |
|---|---|
| IA / LLM / Agents | OpenAI News, Google DeepMind, Hugging Face, Simon Willison, releases vLLM |
| Développement logiciel | The Pragmatic Engineer, InfoQ, Le Monde Informatique, Next |
| Cloud | AWS News Blog, Google Cloud Blog, Cloudflare Blog |
| DevOps | Kubernetes Blog, The New Stack, releases Kubernetes |
| Data | Databricks Blog |
| Bases de données | PostgreSQL News |
| Cybersécurité | CERT-FR, Krebs on Security, BleepingComputer |
| Web | Chrome for Developers, web.dev, Mozilla Hacks |
| Open source | GitHub Blog, LWN.net |
| Outils développeurs | Microsoft DevBlogs, Rust Blog, Python Insider, JetBrains Blog, releases uv |
| Infrastructure | Ars Technica, The Register |
| Technologies émergentes | IEEE Spectrum |
| Généraliste (désactivé par défaut) | Hacker News (activé), Reddit, GDELT, Google News, OSS Insight |

## Ajouter une source

**Un flux RSS** : ajouter une entrée dans `sources.rss`, vérifier qu'elle répond, puis vérifier le domaine dans le registre de confiance :

```json
{ "name": "Vendor Blog", "url": "https://vendor.example/feed.xml", "category": "cloud", "profile": "tech-news", "trust": "official" }
```

**Un nouveau type de source** :

1. Créer `src/scrapers/<nom>.py` avec une classe héritant de `BaseScraper` et implémentant `fetch(since)`.
2. Ajouter le type à `SourceType` et `SOURCE_REGISTRY`, et son modèle de config à `SourcesConfig` (`src/models.py`).
3. L'enregistrer dans `PipelineOrchestrator.fetch_all_sources`.
4. Ajouter des tests (HTTP simulé) sur le modèle de `tests/test_rss.py`.
