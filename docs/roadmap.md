# Roadmap technique

Priorités, dans cet ordre : **fiabilité → qualité des données → qualité des sources → stabilité → valeur réelle**. La monétisation et l'interface viennent ensuite.

## Phase 1 — Fondations (fait)

- Reprise du moteur Horizon, renommage en LucidNews, retrait de ce qui servait l'ancien produit (WeChat, finance/OpenBB, site Pages, références au serveur de l'auteur d'origine).
- Corrections de fiabilité : un item non noté n'est plus publié, apostrophes correctement rendues, profil `ai-creator` neutre en langue, sources GitHub normalisées, réessai des erreurs temporaires de classification, limiteur de débit IA.
- Fiabilité : registre de confiance des domaines, vérification des affirmations, étiquettes, consignes de rédaction prudente.
- Taxonomie des 12 catégories IT et niveaux d'importance.
- Langues : registre extensible, anglais et français complets.
- Newsletter : abonnés, préférences, plans Free/Premium (sans gating), envoi personnalisé par groupe de préférences.
- Catalogue de 31 flux IT vérifiés, documentation produit.

## Phase 2 — Qualité et stabilité des données

- **Corroboration** : compter les éditeurs indépendants qui rapportent le même événement (via le dédoublonnage par sujet), et faire monter une affirmation `reported` à « Fiable » quand plusieurs sources reconnues concordent.
- **Santé des sources** *(fait)* : historique par source dans l'archive (statut, erreur, news collectées et retenues), classement `dead` / `failing` / `silent` / `noisy` / `healthy`, alerte en fin de run et commande `lucidnews-sources`. Reste à faire : score de qualité par source utilisé dans la sélection.
- **Archive d'items** *(fait)* : runs et news analysées stockés dans SQLite ; les analyses de news inchangées sont réutilisées. Ouvre la voie à l'envoi hebdomadaire, aux statistiques et à la reprise.
- **Robustesse IA** *(fait)* : nouvelle tentative en fin d'étape pour l'analyse et l'enrichissement, puis reprise des news non notées aux runs suivants depuis l'archive. Reste à faire : budget de tokens par run.
- **Évaluation** : jeu d'items annotés à la main pour mesurer la précision du score, des catégories et du statut de vérification à chaque changement de prompt.
- Enrichir le registre de confiance (éditeurs français, autorités européennes) et `trust` pour les comptes X/Telegram officiels.

## Phase 3 — Newsletter

- Envoi hebdomadaire (dépend de l'archive d'items).
- Double opt-in, lien de désinscription signé, page de gestion des préférences (avec la phase UI).
- Fournisseur d'emailing transactionnel (délivrabilité, rebonds, statistiques) à la place du SMTP direct.
- Passage du stockage JSON des abonnés à une base de données (même interface `SubscriberStore`).
- Ordonnancement (cron / tâche planifiée) par fuseau horaire des abonnés.

## Phase 4 — Interface et SaaS (hors périmètre actuel)

- Interface web : digest, recherche, préférences, administration des sources.
- Comptes utilisateurs, authentification.
- Activation des limites du plan Free et de l'offre Premium (`PLAN_LIMITS`), puis paiement.

## Dette technique identifiée

- Le paquet Python s'appelle `src` (héritage) ; le renommer en `lucidnews` demandera de mettre à jour tous les imports et les points d'entrée.
- `orchestrator.py` concentre beaucoup de responsabilités (≈ 1 100 lignes). À découper en étapes (`collect`, `select`, `deliver`) quand l'archive d'items arrivera.
- L'email HTML est un gabarit minimal ; il sera refait avec la phase UI.
- Les métadonnées fusionnées entre sources peuvent mélanger les auteurs (par exemple « Lobsters » affiché sur un item Hacker News).
