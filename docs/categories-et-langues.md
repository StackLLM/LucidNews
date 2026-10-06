# Catégories, importance et langues

## Catégories IT

Définies dans `src/taxonomy.py`. Pendant l'analyse, l'IA attribue à chaque item **1 à 3 catégories**, de la plus à la moins pertinente. Les identifiants inconnus sont ignorés, et les alias courants sont convertis (`llm` → `ai`, `security` → `cybersecurity`, `devtools` → `developer-tools`…).

| ID | Anglais | Français |
|---|---|---|
| `ai` | AI / LLM / Agents | IA / LLM / Agents |
| `software-development` | Software Development | Développement logiciel |
| `cloud` | Cloud | Cloud |
| `devops` | DevOps | DevOps |
| `data` | Data | Data |
| `cybersecurity` | Cybersecurity | Cybersécurité |
| `web` | Web | Web |
| `open-source` | Open Source | Open Source |
| `developer-tools` | Developer Tools | Outils développeurs |
| `databases` | Databases | Bases de données |
| `infrastructure` | Infrastructure | Infrastructure |
| `emerging-tech` | Emerging Technologies | Technologies émergentes |

Deux notions de « catégorie » coexistent :

| Notion | Origine | Usage |
|---|---|---|
| `analysis.categories` (taxonomie ci-dessus) | IA, par item | Préférences newsletter, sélection |
| `category` d'une source (texte libre) | Configuration | Quotas du digest (`digest.category_groups`) |

Pour ajouter une catégorie : ajouter une valeur à `Category`, ses libellés dans `CATEGORY_LABELS` et sa portée dans `CATEGORY_SCOPES`. Le prompt d'analyse est généré à partir de ces tables.

## Importance

Dérivée du score d'analyse (0–10) :

| Niveau | Score |
|---|---|
| `critical` | ≥ 9 |
| `high` | ≥ 7 |
| `medium` | ≥ 5 |
| `low` | < 5 |

Elle sert aux préférences newsletter (`min_importance`). Les seuils de sélection du digest restent réglés par profil (`processing.profile_settings.<profil>.threshold`).

## Profils éditoriaux

Le profil définit **comment** un item est évalué et rédigé :

| Profil | Pour quoi |
|---|---|
| `tech-news` | Releases, incidents, annonces, recherche : actualité datée |
| `tech-blog` | Articles de fond : retours d'expérience, analyses, tutoriels |
| `ai-creator` | Actualité IA utile à des créateurs de contenu (accroches, angles) |

Format et personnalisation : [profiles.md](profiles.md) (anglais).

## Langues

Les langues de sortie se règlent dans `ai.languages`, par exemple `["en", "fr"]`. Pour chaque langue, le pipeline :

1. génère les blocs d'enrichissement directement dans cette langue (l'IA reçoit l'instruction définie dans `src/i18n.py`) ;
2. rend le digest avec les libellés fixes de cette langue ;
3. écrit `data/summaries/lucidnews-<date>-<langue>.md`.

Chaque langue ajoute des appels IA d'enrichissement. L'analyse, elle, est faite une seule fois.

### Langues supportées

| Code | Langue | Libellés traduits |
|---|---|---|
| `en` | Anglais | oui (référence) |
| `fr` | Français | oui |
| `zh` | Chinois simplifié | oui (+ normalisation en caractères simplifiés) |

N'importe quel autre code (`de`, `es`…) fonctionne déjà pour le contenu rédigé par l'IA. Les libellés fixes retombent alors sur l'anglais.

### Ajouter une langue

1. Ajouter une entrée `Language` dans `LANGUAGES` (`src/i18n.py`), avec l'instruction donnée à l'IA.
2. Ajouter une table de messages (copier `_EN` et traduire). Toute clé absente retombe sur l'anglais.
3. Si besoin, ajouter un format de date dans `format_timestamp`.
4. Ajouter éventuellement les noms de profils (`display_names` dans `profiles/*/profile.json`) et les libellés de catégories (`CATEGORY_LABELS`).
5. Le test `test_languages_cover_en_fr_and_fall_back_to_english` vérifie que les tables ont les mêmes clés.

### Langue des abonnés

Chaque abonné choisit sa langue (`preferences.language`). Si cette langue n'a pas été générée pendant le run, il reçoit la première langue de `ai.languages`, et l'écart est signalé dans le terminal. Voir [newsletter.md](newsletter.md).
