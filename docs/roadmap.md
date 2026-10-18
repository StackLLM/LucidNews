# Roadmap technique

Le détail des lots clôturés et à venir est dans [lots.md](lots.md).

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

- **Corroboration** *(fait)* : les sites reconnus et indépendants qui rapportent le même événement sont comptés lors du dédoublonnage par sujet et font monter l'étiquette (règles dans `docs/fiabilite.md`). Étendue aux news sous le seuil et aux runs des 72 dernières heures via l'archive, et commande `lucidnews-reassess` pour recalculer les étiquettes archivées *(faits, lot 14 bis)*.
- **Santé des sources** *(fait)* : historique par source dans l'archive (statut, erreur, news collectées et retenues), classement `dead` / `failing` / `silent` / `noisy` / `healthy`, alerte en fin de run et commande `lucidnews-sources`. Score de qualité par source, utilisé pour départager les news de même score *(fait, lot 14 bis)*.
- **Archive d'items** *(fait)* : runs et news analysées stockés dans SQLite ; les analyses de news inchangées sont réutilisées. Ouvre la voie à l'envoi hebdomadaire, aux statistiques et à la reprise.
- **Robustesse IA** *(fait)* : nouvelle tentative en fin d'étape pour l'analyse et l'enrichissement, puis reprise des news non notées aux runs suivants depuis l'archive. Budget de tokens par run, quota épuisé géré sans bloquer le run (news publiées à part, sans analyse) et réutilisation de l'enrichissement *(faits, lot 14)*.
- **Évaluation** *(outil fait)* : annotation à l'aveugle dans l'écran Qualité, commande `lucidnews-eval` (sélection, importance, thèmes, affirmation, faux fiables), re-analyse avec `--rerun` pour tester un changement de consigne. Reste à faire : annoter au moins 30 news. Voir `docs/evaluation.md`.
- **Registre de confiance enrichi** *(fait)* : comptes de réseaux sociaux (X, Mastodon, Bluesky, Telegram) jugés sur leur compte et non sur la plateforme, éditeurs français et européens, autorités françaises et européennes, sites officiels de projets repérés dans l'archive. Reste à faire : poursuivre au fil des domaines inconnus.

## Phase 2 bis — Pilotage depuis l'interface

Objectif : utiliser LucidNews sans terminal pour les opérations courantes. Détail et ordre dans [lots.md](lots.md).

- Cartes d'actualité interactives (lot 15).
- Réglages : clés API (jamais réaffichées), IA, collecte et traitement (lot 16).
- Gestion des sources : ajout, modification, activation, suppression, test (lot 17).
- Domaines surveillés, couverture et sources recommandées (lot 18).
- Qualité de la veille : couverture, diversité, fraîcheur, doublons, fiabilité (lot 19).
- Lancement et planification des runs (lot 20).

## Phase 3 — Newsletter

- Contenu et préférences : envoi hebdomadaire, niveau de détail, aperçu, e-mail HTML refait (lot 21, fait).
- Envoi fiable : double opt-in, désinscription signée, fournisseur transactionnel, journal des envois, abonnés en base, fuseau horaire (lot 22).
- Recherche dans l'archive (lot 23), puis finitions de l'interface : mode sombre, contrastes, socle allégé (lot 24).

## Où on en est (18 octobre 2026)

Lots 0 à 32 et 12 bis (outil) clôturés. Le détail de chacun, avec ses vérifications, est dans [lots.md](lots.md).

| Domaine | État |
|---|---|
| Collecte, doublons, sélection, fiabilité, IA facultative | ✅ opérationnel |
| Application web : édition par domaine, archive, recherche, sources, qualité, réglages | ✅ opérationnel |
| Comptes : e-mail + mot de passe, Google OAuth, rôles `admin` / `reader`, page Mon compte, préférences et « Ma sélection » | ✅ sans e-mail |
| Sécurité : ASVS niveau 1, limite de requêtes, proxy de confiance, CSP, audit des dépendances | ✅ [docs/securite/](securite/) |
| Tests : 920 Python, 174 interface, 5 parcours Playwright ; CI GitHub Actions (API, interface, parcours, pile Docker) | ✅ |
| Exécution serveur : `docker compose up -d --build` (init, api, scheduler, Caddy), planificateur serveur, SQLite en WAL | ✅ vérifié en local |
| Newsletter par e-mail (envoi réel, vérification d'adresse, mot de passe oublié) | ⏳ code prêt, **reporté** (lot 33) |
| Sauvegardes, observabilité | ❌ lots 34 et 35 |
| Mesure de la fiabilité | 🟡 outil prêt (`lucidnews-eval`) ; il manque 100 news annotées (action humaine, lot 12 bis) |

## La route

Ordre conseillé. Chaque lot garde ses critères dans [lots.md](lots.md) une fois clôturé.

### Lot 12 bis — Preuve de qualité *(action humaine)*
Annoter au moins 100 news dans l'écran Qualité, puis `lucidnews-eval`. Objectif : taux de « faux fiables » < 5 %, publié sur une page « Méthode ». Il n'y a aujourd'hui que 81 news analysées par l'IA (l'IA est désactivée dans la configuration locale) : il faut d'abord en produire.

### Lot 33 — E-mail en production *(reporté)*
Vérification de l'adresse, mot de passe oublié par e-mail, envoi réel de la newsletter. Domaine d'envoi authentifié (SPF, DKIM, DMARC), webhooks du fournisseur (rebonds et plaintes désinscrivent), service public de confirmation et de désinscription (`lucidnews-public`, déjà écrit, hors de la pile Docker tant que l'e-mail est reporté).
*Critères* : premier envoi reçu chez Gmail et Outlook ; un rebond simulé désactive l'adresse (test).

### Lot 34 — Données
Sauvegarde à chaud, chiffrée et quotidienne des trois bases SQLite (archive, newsletter, comptes), conservée hors du serveur ; restauration documentée.
*Critères* : restauration testée de bout en bout en moins de 30 minutes ; 7 sauvegardes quotidiennes et 4 hebdomadaires gardées.

### Lot 35 — Observabilité et coûts
Suivi d'erreurs, sonde de disponibilité externe (le point de contrôle `GET /api/healthz` existe), coût IA par mois à partir des tokens archivés, alerte de budget.
*Critères* : une erreur provoquée remonte en moins de 5 minutes ; alerte si le coût IA du mois dépasse le budget fixé.

### Lot 36 — Conformité
Politique de confidentialité, conditions d'utilisation, page « Sources et attribution », procédure de retrait pour un éditeur. L'export et la suppression de compte existent déjà (lot 28).

### Lots 37 et 38 — Hébergement et bêta privée
Un VPS avec Docker Compose et Caddy (la pile existe), déploiement et retour arrière en une commande depuis la CI, puis une bêta sur invitation (`auth.allow_signup` fermé). À décider après la fin de l'application.

### Après le lancement *(à confirmer par les résultats)*
39 fil d'un événement (une page par histoire : sources, chronologie, évolution de l'étiquette) · 40 synthèse hebdomadaire des tendances · 41 alertes et suivi d'entités · 42 limites par plan et paiement · 43 équipes · 44 sources personnelles par utilisateur · 45 arabe · 46 PostgreSQL et plusieurs instances.

## Dépendances

```
27 Rôles ──► 28 Compte ──► 29 Veille personnelle ──► 30 Sécurité ──► 31 E2E + CI ──► 32 Serveur
                                                                                      │
   33 E-mail (reporté) ───────────────────────────────────────────────────────────────┤
   34 Données ──► 37 Hébergement ──► 38 Bêta ──► lots 39 à 46
   35 Observabilité, 36 Conformité ──► 38
   12 bis Preuve de qualité ──► toute communication sur la fiabilité
```

## Décisions techniques en vigueur

| Sujet | Décision | Raison |
|---|---|---|
| Modèle | Une veille éditée et partagée ; chaque lecteur règle sa sélection | Le coût IA ne dépend pas du nombre de lecteurs (environ 3 000 tokens par news) |
| Base de données | SQLite en mode WAL, un seul serveur, sauvegardes (lot 34) | Peu d'écritures concurrentes ; PostgreSQL seulement avec plusieurs instances ou sans disque local (lot 46) |
| Comptes | Rôles `admin` / `reader`, tout ce qui n'est pas dans `READER_ROUTES` est réservé à l'admin (refus par défaut) | Les routes d'administration ne dépendent plus de l'écoute en local |
| Mot de passe oublié | Sans e-mail : l'admin le réinitialise (`lucidnews-users passwd`) | L'e-mail est reporté (lot 33) |
| Planification | `launchd` sur Mac, `lucidnews-scheduler` sur un serveur (`LUCIDNEWS_SCHEDULER=server`) | Un conteneur n'a pas launchd |
| Reverse proxy | Caddy, adresse fixe déclarée dans `server.trusted_proxies` | La limite de requêtes doit voir le vrai visiteur |
| E-mail | Fournisseur transactionnel déjà intégré (Resend) | Voir lot 33 |
| Langues | FR + EN ; l'arabe seulement si la demande le justifie | Aucune preuve de demande aujourd'hui |

## À vérifier avant de s'y fier

- Les métadonnées fusionnées entre sources peuvent mélanger les auteurs (par exemple « Lobsters » affiché sur une news Hacker News).
- `orchestrator.py` concentre encore beaucoup de responsabilités ; à découper en étapes si on y touche en profondeur.
- L'e-mail HTML de la newsletter n'a jamais été envoyé pour de vrai.
