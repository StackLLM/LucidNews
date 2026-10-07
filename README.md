# LucidNews

**Veille technologique fiable et newsletter IT.**

LucidNews surveille les sources importantes de l'écosystème IT, écarte le bruit, vérifie la fiabilité de chaque information, la classe, la résume en anglais et en français, puis la distribue (fichier Markdown, email, webhook).

```
Collecter → Filtrer → Vérifier → Classer → Résumer → Prioriser → Distribuer
```

> Statut : **Phase 1 — fondations techniques**. Pas encore d'interface : le produit tourne en ligne de commande et produit des digests Markdown et des emails.

---

## Sommaire

- [Fonctionnalités](#fonctionnalités)
- [Installation](#installation)
- [Configuration](#configuration)
- [Lancement](#lancement)
- [Tests](#tests)
- [Structure du dépôt](#structure-du-dépôt)
- [Documentation](#documentation)
- [Origine et licence](#origine-et-licence)

## Fonctionnalités

| Domaine | Ce que fait LucidNews |
|---|---|
| **Collecte** | 9 types de sources : RSS/Atom, Hacker News, GitHub (releases, activité), Reddit, Telegram, X/Twitter, OSS Insight, GDELT, Google News. Collecte en parallèle, rapport d'échec par source. |
| **Filtrage** | Fusion des doublons multi-sources (URL normalisée), score IA de 0 à 10 par profil, seuils par profil, dédoublonnage sémantique par sujet, quotas par catégorie. Une news que l'IA n'a pas pu noter n'est jamais publiée. |
| **Fiabilité** | Niveau de confiance de l'éditeur (officiel, reconnu, communautaire, inconnu) + vérification de l'affirmation par l'IA (confirmée, rapportée, non vérifiée, rumeur) → étiquette **Confirmé / Fiable / Non vérifié / Rumeur**. Une info non confirmée est toujours signalée comme telle. |
| **Classification** | Routage par profil éditorial (`tech-news`, `tech-blog`, `ai-creator`) et attribution de 1 à 3 catégories parmi 12 catégories IT. |
| **Résumé** | Enrichissement IA par blocs (résumé, contexte, impact, discussion), recherche web et recherche dans l'historique des digests, sources citées. |
| **Langues** | Anglais et français (le chinois reste disponible). Architecture extensible : une langue = une entrée dans `src/i18n.py`. |
| **Distribution** | Digest Markdown quotidien, email personnalisé par abonné (langue, catégories, sources, importance, fiabilité), webhooks (Slack, Discord, Feishu/Lark, DingTalk, générique), serveur MCP. |
| **Newsletter** | Abonnés, préférences, plans Free/Premium préparés (sans paiement), une version du digest par jeu de préférences. |

## Installation

Prérequis : Python ≥ 3.11 et [uv](https://github.com/astral-sh/uv).

```bash
git clone <url-du-depot> LucidNews
cd LucidNews
uv sync --extra dev
```

Extras optionnels :

```bash
uv sync --extra twitter   # X/Twitter en mode Playwright
```

Docker :

```bash
docker compose build
docker compose run --rm lucidnews --hours 24
```

## Configuration

Deux fichiers, tous deux **ignorés par git** :

| Fichier | Rôle |
|---|---|
| `.env` | Secrets (clés API, mots de passe). Modèle : [`.env.example`](.env.example). |
| `data/config.json` | Réglages : fournisseur IA, langues, sources, seuils, fiabilité, livraison. Modèle : [`data/config.example.json`](data/config.example.json). |

```bash
cp .env.example .env
cp data/config.example.json data/config.json
```

Règle importante : `ai.api_key_env` contient le **nom** d'une variable d'environnement, jamais la clé elle-même.

```json
"ai": { "provider": "gemini", "model": "gemini-2.5-flash", "api_key_env": "GOOGLE_API_KEY", "languages": ["en", "fr"] }
```

Un assistant interactif peut aussi générer la configuration :

```bash
uv run lucidnews-wizard
```

Détails : [docs/configuration.md](docs/configuration.md) (référence complète) et [docs/architecture.md](docs/architecture.md#configuration).

### Variables d'environnement

| Variable | Utilisation |
|---|---|
| `GOOGLE_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `AZURE_OPENAI_API_KEY` + `AZURE_OPENAI_ENDPOINT`, `DEEPSEEK_API_KEY`, `DASHSCOPE_API_KEY`, `DOUBAO_API_KEY`, `MINIMAX_API_KEY` | Clé du fournisseur IA choisi (une seule suffit) |
| `LUCIDNEWS_OLLAMA_BASE_URL` | Adresse d'un serveur Ollama local (optionnel) |
| `GITHUB_TOKEN` | Relève la limite de l'API GitHub de 60 à 5000 requêtes/heure (recommandé) |
| `APIFY_TOKEN` | X/Twitter en mode Apify |
| `LWN_KEY` | Flux LWN en texte intégral (abonnés) |
| `EMAIL_PASSWORD` | Mot de passe SMTP/IMAP de la boîte newsletter |
| `LUCIDNEWS_WEBHOOK_URL` | URL du webhook |
| `LUCIDNEWS_PRESETS_URL` | Catalogue distant de sources pour l'assistant (sinon `data/presets.json`) |
| `LUCIDNEWS_PATH`, `LUCIDNEWS_MCP_SECRETS_PATH` | Serveur MCP |

Toute valeur de `config.json` peut référencer une variable avec `${NOM}`.

## Lancement

```bash
uv run lucidnews                # fenêtre définie par collection.time_window_hours (24 h par défaut)
uv run lucidnews --hours 8      # forcer une fenêtre
uv run lucidnews --log-level INFO
```

Résultats : `data/summaries/lucidnews-AAAA-MM-JJ-<langue>.md`, plus les emails et webhooks s'ils sont activés.

Autres commandes :

| Commande | Rôle |
|---|---|
| `uv run lucidnews-wizard` | Assistant de configuration |
| `uv run lucidnews-webhook` | Tester ou renvoyer un webhook |
| `uv run lucidnews-sources` | Santé des sources (mortes, en échec, silencieuses, bruyantes) |
| `uv run lucidnews-api` | API web en lecture seule pour le frontend (`frontend/`), sur localhost |
| `uv run lucidnews-mcp` | Serveur MCP (pipeline par étapes pour agents IA) |
| `./scripts/daily-run.sh [heures]` | Exécution quotidienne (cron) |

## Tests

```bash
uv run pytest            # suite complète (aucun appel réseau ni IA réel)
uv run pytest -k reliability
```

La suite couvre la collecte (chaque scraper), la fusion des doublons, le filtrage, la classification, l'analyse, la fiabilité, la taxonomie, les langues, l'enrichissement, le rendu, la newsletter, le stockage, les webhooks, l'email, l'assistant et le serveur MCP.

Avant de livrer, faire aussi un vrai cycle : `uv run lucidnews --hours 6`, puis relire le digest produit.

## Structure du dépôt

```
src/
  main.py              point d'entrée CLI
  orchestrator.py      pipeline complet (collecte → distribution)
  models.py            modèles de données et schéma de configuration
  scrapers/            une classe par type de source
  extractors/          extraction du texte intégral des pages
  ai/                  clients IA, classification, analyse, enrichissement, rendu
  processing/          profils éditoriaux, outils (web, historique), sélection de contenu
  reliability/         confiance des sources et étiquettes de fiabilité
  taxonomy.py          12 catégories IT et niveaux d'importance
  i18n.py              langues et textes localisés
  newsletter/          abonnés, préférences, plans, sélection, plan d'envoi
  services/            email, webhook
  storage/             configuration, digests, abonnés (fichiers)
  mcp/                 serveur MCP
  setup/               assistant de configuration et catalogue de sources
profiles/              profils éditoriaux (prompts Markdown + JSON)
data/                  configuration d'exemple, catalogue de sources ; données locales ignorées par git
docs/                  documentation
tests/                 tests automatisés (pytest)
```

## Documentation

| Document | Contenu |
|---|---|
| [Architecture](docs/architecture.md) | Vue d'ensemble, flux de données, modules, configuration, points sensibles |
| [Collecte et sources](docs/collecte.md) | Fonctionnement de la collecte, catalogue de sources, ajout d'une source |
| [Fiabilité](docs/fiabilite.md) | Niveaux de confiance, vérification des affirmations, étiquettes, réglages |
| [Catégories et langues](docs/categories-et-langues.md) | Taxonomie IT, importance, langues, ajout d'une langue |
| [Newsletter](docs/newsletter.md) | Abonnés, préférences, plans, envoi |
| [Roadmap technique](docs/roadmap.md) | Prochaines étapes |
| Références (en anglais) | [configuration](docs/configuration.md), [profils](docs/profiles.md), [score](docs/scoring.md), [scrapers](docs/scrapers.md), [extracteurs](docs/extractors.md), [cookies X](docs/twitter-cookies.md), [MCP](src/mcp/README.md) |

## Origine et licence

LucidNews est construit à partir du projet open source [Horizon](https://github.com/Thysrael/Horizon) (licence MIT, © 2026 Thysrael), dont il reprend le moteur de collecte et de traitement. Conformément à la licence MIT, la notice de copyright d'origine est conservée dans [LICENSE](LICENSE).
