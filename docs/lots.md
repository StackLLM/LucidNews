# Lots de travail — LucidNews

Ce document regroupe tous les lots : ceux qui sont **clôturés** et ceux qui
**restent à faire**. Il complète la [roadmap](roadmap.md), qui donne les priorités.

État au 9 octobre 2026. Dernier lot clôturé : lot 15.

Légende : ✅ clôturé · 🟡 outil livré, action humaine attendue · ⏳ proposé, en attente de décision · 📋 planifié.

---

## Sommaire

**Lots clôturés**

- [Lot 0 — Analyse d'Horizon et clé API](#lot-0--analyse-dhorizon-et-clé-api) ✅
- [Lot 1 — Refonte en LucidNews (phase 1)](#lot-1--refonte-en-lucidnews-phase-1) ✅
- [Lot 2 — Archive SQLite des runs et des news](#lot-2--archive-sqlite-des-runs-et-des-news) ✅
- [Lot 3 — Robustesse face aux échecs de l'IA](#lot-3--robustesse-face-aux-échecs-de-lia) ✅
- [Lot 4 — Santé des sources](#lot-4--santé-des-sources) ✅
- [Lot 5 — Corroboration par des sources indépendantes](#lot-5--corroboration-par-des-sources-indépendantes) ✅
- [Lot 6 — Direction UI et dépendances](#lot-6--direction-ui-et-dépendances) ✅
- [Lot 7 — API web et écran Édition du jour](#lot-7--api-web-et-écran-édition-du-jour) ✅
- [Lot 8 — Écrans Archives et Santé des sources](#lot-8--écrans-archives-et-santé-des-sources) ✅
- [Lot 9 — Fiche d'une news](#lot-9--fiche-dune-news) ✅
- [Lot 10 — Écran Préférences (version locale)](#lot-10--écran-préférences-version-locale) ✅
- [Lot 11 — Mesure de la qualité](#lot-11--mesure-de-la-qualité) 🟡
- [Lot 13 — Registre de confiance enrichi](#lot-13--registre-de-confiance-enrichi) ✅
- [Lot 14 — Budget IA et quota épuisé](#lot-14--budget-ia-et-quota-épuisé) ✅
- [Lot 14 bis — Corroboration élargie et qualité des sources](#lot-14-bis--corroboration-élargie-et-qualité-des-sources) ✅
- [Lot 15 — Cartes d'actualité interactives](#lot-15--cartes-dactualité-interactives) ✅

**Lots suivants** (dans l'ordre d'exécution)

- [Ordre d'exécution et dépendances](#ordre-dexécution-et-dépendances)
- [Navigation visée](#navigation-visée)
- [Lot 12 — Annoter au moins 30 news](#lot-12--annoter-au-moins-30-news) 🟡
- [Lot 16 — Socle de pilotage et page Réglages](#lot-16--socle-de-pilotage-et-page-réglages) 📋
- [Lot 17 — Gestion des sources](#lot-17--gestion-des-sources) 📋
- [Lot 18 — Domaines surveillés et couverture](#lot-18--domaines-surveillés-et-couverture) 📋
- [Lot 19 — Qualité de la veille](#lot-19--qualité-de-la-veille) 📋
- [Lot 20 — Lancer et planifier les runs](#lot-20--lancer-et-planifier-les-runs) 📋
- [Lot 21 — Newsletter : contenu et préférences](#lot-21--newsletter--contenu-et-préférences) 📋
- [Lot 22 — Newsletter : envoi fiable](#lot-22--newsletter--envoi-fiable) 📋
- [Lot 23 — Recherche dans l'archive](#lot-23--recherche-dans-larchive) 📋
- [Lot 24 — Finitions de l'interface](#lot-24--finitions-de-linterface) 📋
- [Lot 25 — Dette technique](#lot-25--dette-technique) 📋
- [Lot 26 — Comptes et SaaS (phase 4)](#lot-26--comptes-et-saas-phase-4) 📋
- [Paramètres : où ils vivent](#paramètres--où-ils-vivent-et-comment-ils-sappliquent)
- [Blocages et décisions en attente](#blocages-et-décisions-en-attente)
- [Analyse : besoins d'une newsletter moderne](#analyse--besoins-dune-newsletter-moderne)

**Annexes**

- [Points observés à confirmer](#points-observés-à-confirmer)
- [Décisions prises](#décisions-prises)
- [Historique des commits](#historique-des-commits)

---

# Lots clôturés

## Lot 0 — Analyse d'Horizon et clé API

✅ Clôturé · Travail fait dans le clone Horizon, avant la refonte (aucun commit LucidNews).

**Objectif** : comprendre le projet d'origine sans rien modifier, puis corriger l'erreur « Missing API key ».

**Fait**

- Analyse complète du moteur Horizon (collecte, analyse IA, enrichissement, rendu, envoi).
- Cause de l'erreur : le champ `api_key_env` contenait la **valeur** de la clé au lieu du **nom** de la variable. Corrigé en `GEMINI_API_KEY`.
- Vérification des news du digest du 5 octobre 2026 : les faits étaient exacts. Les défauts relevés (news non notées publiées, apostrophes mal affichées, etc.) ont été traités au lot 1.

---

## Lot 1 — Refonte en LucidNews (phase 1)

✅ Clôturé · Commits `57432f9` → `c01db56` · Dépôt privé `oussamaalmouallim/LucidNews`.

**Objectif** : transformer Horizon en produit propre, sans casser la collecte ni la fiabilité, avec un historique Git neuf et sans secret.

**Choix validés**

- Nom : **LucidNews**.
- Retirés : WeChat, README chinois et japonais, site GitHub Pages, Finance et OpenBB.
- Gardé : le profil `ai-creator`, traduit en anglais.
- Langues : anglais et français, extensibles.
- Aucune interface, aucun paiement, aucun paywall dans cette phase.

**Fait**

| Sujet | Contenu |
|---|---|
| Socle | Import d'Horizon (licence MIT, mention © 2026 Thysrael conservée), renommage complet, retrait des fonctions de l'ancien produit. |
| Corrections | Une news non notée n'est plus jamais publiée. Apostrophes lisibles dans le digest et l'e-mail. Préfixe d'angle traduit. Sources GitHub normalisées. Sélection et rendu durcis. |
| Fiabilité | Registre de confiance des domaines (officiel, reconnu, communautaire, inconnu). Statut de l'affirmation donné par l'IA. Étiquettes Confirmé / Fiable / Non vérifié / Rumeur. Consigne de rédaction prudente : une info non confirmée n'est jamais présentée comme un fait. |
| Taxonomie | 12 catégories IT et 4 niveaux d'importance. |
| Langues | Registre extensible, textes EN et FR complets, repli sur l'anglais. |
| Newsletter | Abonnés, préférences, offres Free et Premium (sans limite), envoi par groupe de préférences. |
| Sources | Catalogue de 31 flux IT vérifiés, environnement documenté. |
| IA | Limiteur de requêtes par minute (quota Gemini gratuit), nouvelles tentatives du classifieur. |
| Sécurité | Fichiers de config locaux, variantes `.env` et fichiers de clés ignorés. Historique Git vérifié sans secret. Image Docker vérifiée sans secret. |
| Docs | README et docs produit en français (architecture, collecte, fiabilité, catégories et langues, newsletter, roadmap). Docs techniques en anglais (configuration, profils, scrapers). SECURITY.md. |

**Incidents traités**

- Erreurs 429 et 503 de Gemini (offre gratuite) : limiteur, nouvelles tentatives, changement de modèle.
- Flux CISA bloqué (403) quel que soit l'agent : flux retiré plutôt que de contourner la protection anti-robot.
- Flux Mozilla (403) : corrigé avec un agent HTTP honnête qui se présente comme LucidNews.

---

## Lot 2 — Archive SQLite des runs et des news

✅ Clôturé · Commit `933b55a` · Étape 1 de la phase 2.

**Objectif** : garder l'historique de chaque run et ne pas repayer l'analyse d'une news déjà vue.

**Fait**

- Base SQLite locale : runs, news, liens run ↔ news (retenue ou non).
- Réutilisation de l'analyse quand le contenu d'une news n'a pas changé.
- Bug corrigé pendant le test : l'enregistrement avant analyse écrasait l'analyse stockée, donc rien n'était réutilisé. Désormais l'écriture se fait après l'analyse, et la base refuse de remplacer une analyse par une copie non analysée.
- Vérifié sur un vrai run : 12 analyses sur 12 réutilisées, environ 70 % de tokens en moins.

---

## Lot 3 — Robustesse face aux échecs de l'IA

✅ Clôturé · Commit `47b4110` · Étape 2 de la phase 2.

**Objectif** : ne plus perdre une news parce que l'IA a échoué une fois.

**Fait**

- Nouvelle tentative en fin d'étape, après une pause, pour l'analyse et l'enrichissement.
- Les news restées non notées sont reprises aux runs suivants depuis l'archive, dans une fenêtre de temps et un nombre d'essais limités.
- Le nombre de news non notées est enregistré pour chaque run.

---

## Lot 4 — Santé des sources

✅ Clôturé · Commit `f2269ab` · Étape 3 de la phase 2.

**Objectif** : savoir quelles sources marchent, échouent ou n'apportent rien.

**Fait**

- Résultat de chaque source à chaque run, stocké dans l'archive.
- Classement : morte, en échec, silencieuse, bruyante, saine.
- Alerte en fin de run, limitée aux sources encore configurées.
- Commande `lucidnews-sources` (tableau ou JSON, filtres par statut et par période, option pour inclure les sources retirées).
- Erreurs suivies source par source pour les flux RSS et les dépôts GitHub.
- Config locale nettoyée : 5 flux hors sujet et 6 sources mortes retirés. Il reste 23 flux RSS et 5 sources GitHub.

---

## Lot 5 — Corroboration par des sources indépendantes

✅ Clôturé · Commit `54f0e88` · Étape 4 de la phase 2.

**Objectif** : quand plusieurs sites sérieux rapportent le même événement, en tenir compte dans la fiabilité.

**Règles**

| Situation | Étiquette |
|---|---|
| L'acteur concerné publie aussi l'info | Confirmé |
| Source faible + 1 site reconnu indépendant | Fiable |
| Affirmation non vérifiée + 2 sites reconnus | Fiable |
| Rumeur, même répétée | Reste Rumeur |

- Les sous-domaines d'un même site comptent pour un seul site.
- Les forums et sites inconnus ne comptent pas.
- Affichage dans le digest : « corroboré par N source(s) indépendante(s) ».

**Limite** : pas encore observée sur un vrai run, aucun sujet n'a été fusionné. Le comportement est couvert par les tests.

---

## Lot 6 — Direction UI et dépendances

✅ Clôturé · Inclus dans le commit `9e0496c`.

**Objectif** : fixer la direction visuelle à partir des modèles, sans copier ce qui ne sert pas une newsletter.

**Fait**

- Deux modèles analysés avec la méthode de la skill UI-Stealer : « Agenta » pour l'ambiance, « Paypay » pour la structure des écrans.
- Analyse détaillée : structure, composants, espacements, typographie, cartes, boutons, champs, tableaux, graphiques, effets, animations, responsive, détails visuels.
- Éléments écartés : violets criards, bloc noir, chiffres marketing, icônes 3D, flux de paiement.
- Couleurs propres à LucidNews. La fiabilité a sa propre gamme, distincte de la couleur d'accent.
- Deux polices : Plus Jakarta Sans pour l'interface, Newsreader pour la lecture.
- Liste des dépendances : chaque paquet est justifié, avec l'option écartée.

**Documents** : [frontend/docs/direction-ui.md](../frontend/docs/direction-ui.md), [frontend/docs/dependances.md](../frontend/docs/dependances.md).

---

## Lot 7 — API web et écran Édition du jour

✅ Clôturé · Commit `9e0496c`.

**Fait**

- Commande `lucidnews-api` : lit l'archive sans jamais l'écrire, écoute en local, aucune dépendance Python ajoutée.
- Application React : React 19, Vite, Tailwind 4, motion, TanStack Query, zod.
- Écran Édition du jour :
  - bandeau avec date et compteurs ;
  - une carte par news : importance, score, étiquette de fiabilité, avertissement si l'info n'est pas confirmée, catégories, bouton « Lire la suite » ;
  - colonne de droite qui reste visible : sommaire des rubriques, répartition de la fiabilité.
- Passage EN/FR (la langue est dans l'URL), bouton « animations off », respect du réglage « réduire les animations ».

**Bugs corrigés pendant les tests** : compteurs à valeur négative, cartes invisibles quand les animations sont coupées, colonne de droite non fixe.

---

## Lot 8 — Écrans Archives et Santé des sources

✅ Clôturé · Commit `9e0496c`.

**Fait**

- Archives : calendrier (seuls les jours avec une édition sont cliquables) et liste des éditions par jour.
- Santé des sources : chiffres clés, graphique « Volume par run » avec une vue Tableau, tableau filtrable par statut, période de 7, 14 ou 30 jours.
- Couleurs du graphique validées pour le daltonisme et le contraste.
- Navigation en barre flottante en bas sur téléphone.
- Un fichier JS par écran.
- Port de l'API configurable (variable `LUCIDNEWS_API`).

**Bugs corrigés** : « 1 retenus », chiffres à zéro colorés en alerte.

---

## Lot 9 — Fiche d'une news

✅ Clôturé · Commit `2e77a82`.

**Fait**

- Route `/api/items/<id>` et écran Fiche, ouvert depuis le bouton « Fiche complète » de chaque carte.
- Contenu : fil d'Ariane vers l'édition d'origine, bandeau score et thèmes, texte complet.
- Colonne Fiabilité : éditeur, statut de l'affirmation, élément de preuve (signalé comme écrit en anglais par l'IA), corroboration.
- Actions : article original, discussion, copier le lien. Liste des éditions qui ont publié la news.
- Sur petit écran, l'étiquette de fiabilité est affichée sous le titre.

**Correctif important** : la règle `lib/` du `.gitignore` excluait `frontend/src/lib`, donc le dépôt poussé ne compilait pas. La règle vise maintenant la racine seulement, et les fichiers sont versionnés.

---

## Lot 10 — Écran Préférences (version locale)

✅ Clôturé · Commit `efc5fbb` · Choix A : version locale, sans comptes.

**Fait**

- Écran Préférences :
  - liste des abonnés, ajout, suppression avec confirmation ;
  - réglages : langue, thèmes, sources, rythme, importance minimale, infos non confirmées, nombre maximum ;
  - barre d'enregistrement visible seulement s'il y a des changements ;
  - offre affichée, jamais modifiable.
- Protections de l'API qui écrit :
  - routes actives seulement en écoute locale ;
  - nom d'hôte local exigé (protection contre le DNS rebinding) ;
  - requêtes venant d'un autre site refusées ;
  - JSON seulement, 64 Ko maximum ;
  - identifiant opaque, jamais d'adresse e-mail dans les URL.
- Nouvelles dépendances : `radix-ui`, `react-hook-form`, `@hookform/resolvers`.

**Bug corrigé** : deux clics rapides sur deux thèmes n'en enregistraient qu'un.

---

## Lot 11 — Mesure de la qualité

🟡 Outil livré · Commit `337b0a2` · Étape 5 de la phase 2.

**Fait**

- Écran Qualité :
  - annotation **à l'aveugle** : aucun avis de l'IA affiché, ordre mélangé ;
  - 4 questions : place dans l'édition, importance, thèmes, statut de l'affirmation ;
  - résultats : sélection, importance, thèmes, affirmation, **faux fiables**.
- Commande `lucidnews-eval` :
  - mode gratuit, sur les analyses stockées ;
  - mode `--rerun`, avec les consignes actuelles (appels IA) ;
  - rapports enregistrés et écart avec la mesure précédente.
- Annotations dans `data/eval/annotations.json` (versionné). Rapports dans `data/eval/reports/` (non versionné).
- Méthode : [evaluation.md](evaluation.md).

**Reste** : les annotations humaines (lot 12). `--rerun` n'a pas encore été lancé avec la vraie clé.

---

## Lot 13 — Registre de confiance enrichi

✅ Clôturé · Étape 6 de la phase 2. Fait avant la fin du lot 12, car indépendant des annotations.

**Objectif** : mieux reconnaître qui publie, pour que l'étiquette de fiabilité soit juste.

**Fait**

| Sujet | Contenu |
|---|---|
| Comptes de réseaux sociaux | Un message est jugé sur **son compte**, pas sur la plateforme. Formats reconnus : X, Mastodon (tout le fédiverse), Bluesky, Telegram. Un compte enregistré l'emporte sur la plateforme. Deux comptes d'une même plateforme comptent comme deux éditeurs indépendants pour la corroboration. |
| Comptes intégrés | Seulement des comptes vérifiés à la main sur leur page publique : curl (Daniel Stenberg, Mastodon), Telegram (Pavel Durov), Bluesky (compte officiel). Aucun compte X : non vérifiable sans connexion. |
| Config | Nouveau réglage `reliability.accounts` (exemple : `"x:openai": "official"`), avec contrôle du format. |
| Autorités | Tout `gouv.fr`, CNIL, ARCEP ; tout `europa.eu` (déjà présent) ; BSI (Allemagne), NCSC (Pays-Bas), Garante (Italie), AEPD (Espagne). |
| Presse française | LeMagIT, JDN, L'Usine Digitale, Silicon, Siècle Digital, Clubic, Frandroid, Les Numériques, Les Échos, Le Figaro, Libération, franceinfo, AFP. |
| Presse européenne | heise, Golem, Euractiv, Politico Europe. |
| Recherche | Inria, CNRS. |
| Communautés françaises | LinuxFr, Developpez, Journal du hacker, Korben. |
| Sites repérés dans l'archive | Vérifiés puis ajoutés : pola.rs, gleam.run, reflection.ai, vals.ai (officiels) ; lucumr.pocoo.org, techdirt.com (reconnus). |
| Mesure de la qualité | L'étiquette de l'IA est recalculée avec le registre actuel : un changement de registre se voit sans relancer le pipeline. |

**Effet mesuré sur les 48 news de l'archive** (sans appel IA)

| Avant | Après |
|---|---|
| 4 Confirmé · 24 Fiable · 20 Non vérifié | 9 Confirmé · 21 Fiable · 18 Non vérifié |
| 20 éditeurs inconnus | 13 éditeurs inconnus |

- 8 news changent d'étiquette. Exemples : curl (Communautaire / Non vérifié → Officiel / Confirmé), Polars 2.0, Gleam et Reflection (Fiable → Confirmé).
- Aucune news ne descend.
- Les étiquettes déjà publiées ne sont pas réécrites. Le nouveau registre s'applique aux prochains runs.

---

## Lot 14 — Budget IA et quota épuisé

✅ Clôturé · Première moitié de la fin de la phase 2 (choix A). Le reste est au lot 14 bis.

**Objectif** : protéger le quota IA, réduire le coût de chaque run, et ne jamais bloquer l'application quand le quota est épuisé.

**Règle validée** : quand le quota est épuisé, l'application affiche les news **sans analyse IA**. Seulement dans ce cas : toute autre erreur d'analyse garde la news hors du digest, comme avant.

**Fait**

| Sujet | Contenu |
|---|---|
| Budget de tokens | Nouveau réglage `ai.max_tokens_per_run`. Une fois atteint, l'IA n'est plus appelée jusqu'à la fin du run. Valeur proposée dans la config d'exemple : 200 000 (un run de 24 h en consomme environ 140 000). |
| Quota du fournisseur | Reconnu à son message d'erreur : quota journalier Gemini, `insufficient_quota` (OpenAI), solde insuffisant (Anthropic, DeepSeek). Une limite **par minute** n'est pas un quota épuisé : elle reste retentée comme avant. |
| Pas de blocage | Dès que le quota est épuisé, chaque appel IA échoue tout de suite : plus d'attente, plus de nouvelle tentative, plus de pause de 30 s. Le run se termine normalement. |
| News non analysées | Marquées « non analysées » dans l'archive. Elles sont reprises au run suivant, sans consommer de tentative. Une news déjà analysée garde son analyse (sans enrichissement s'il n'était pas fait). |
| Publication à part | Jusqu'à 15 news non analysées (`digest.unanalyzed_max_items`, 0 pour aucune), dans une section « Sans analyse IA » : titre d'origine, source, lien. Toujours « Non vérifié », même d'une source officielle. Les sources les mieux connues passent en premier. |
| Digest et e-mail | Section dédiée avec un avertissement. Un abonné ne la reçoit que s'il ne filtre ni par catégorie ni par importance et accepte les infos non confirmées. |
| Interface | Bandeau dans l'édition (« Le quota IA a été épuisé pendant ce run »), section « Sans analyse IA » en fin d'édition et dans le sommaire, fiche d'une news avec un avertissement à la place du résumé, badge « Quota IA épuisé » dans les archives. |
| Suivi par run | L'archive garde, pour chaque run, la raison de l'arrêt de l'IA, les tokens utilisés et le nombre de news non analysées. |
| Réutilisation de l'enrichissement | Une news inchangée reprend aussi son enrichissement (titre traduit, résumé, contexte) s'il existe dans toutes les langues. Désactivable avec `archive.reuse_enrichment`. |

**Vérifié sur des runs simulés** (faux fournisseur IA, sans appel réel)

| Scénario | Résultat |
|---|---|
| Quota épuisé après 2 appels | Run terminé en moins d'une seconde, 3 appels IA au total. 5 news publiées « Sans analyse IA ». |
| Quota épuisé en cours de route | 4 news analysées dans le digest, 2 à part. |
| Budget de 1 500 tokens | Arrêt à 1 500 tokens, 3 news analysées, 3 à part. |
| Même lot de news au run suivant | Enrichissement repris : 19 appels IA → 1 seul. |

---

## Lot 14 bis — Corroboration élargie et qualité des sources

✅ Clôturé · Partie B du lot 14. Termine la phase 2 côté données (il reste les annotations du lot 12).

**Objectif** : mieux confirmer les news grâce à l'archive, et départager les news avec la fiabilité passée de leur source.

**Fait**

| Sujet | Contenu |
|---|---|
| Corroboration élargie | Une news retenue peut être confirmée par une news du même run restée **sous le seuil**, ou par une news de l'**archive** des 72 dernières heures. Ces « références » sont envoyées dans l'appel de dédoublonnage déjà existant : pas d'appel IA en plus, sauf pour une rubrique d'une seule news. |
| Garde-fous | Seules les références officielles ou reconnues sont envoyées (les autres ne comptent pas). 30 au plus par rubrique, les plus récentes d'abord. Une référence n'est jamais publiée ni retirée du digest. Une rumeur reste une rumeur. |
| Score de qualité par source | De 0 à 100, sur 30 jours : moitié score IA moyen, moitié part de news « Confirmé » ou « Fiable » (recalculée avec le registre actuel). Lissé vers 50 tant qu'une source a peu de news. |
| Usage du score | Il **départage seulement** deux news de même score IA (ordre du digest, choix de la news gardée lors d'un doublon, coupe aux quotas). Il ne fait jamais passer une news devant une news mieux notée. |
| Affichage du score | Nouvelle colonne « Qualité » dans `lucidnews-sources` et dans l'écran Sources, avec le détail au survol. |
| Recalcul de l'archive | Nouvelle commande `lucidnews-reassess` : aperçu par défaut, `--apply` pour écrire. Aucun appel IA. Les éditions passées affichent ensuite les étiquettes à jour. |
| Barre de navigation | Corrigé en passant : entre 768 et 1 024 px, la barre du haut débordait de l'écran. La barre du bas sert maintenant jusqu'à 1 024 px. |

**Mesuré sur une copie de l'archive** (48 news, sans appel IA)

| Mesure | Résultat |
|---|---|
| `lucidnews-reassess` | 4 Confirmé · 24 Fiable · 20 Non vérifié → 9 · 21 · 18. 6 news changent d'étiquette (curl, Polars 2.0, Gleam, Reflection…), 2 autres changent seulement de détail. Un second passage ne change plus rien. |
| Score de qualité | De 40 (Lobsters, 19 news, score moyen 3,4) à 61 (LWN, 4 news). Les sources sans news analysée n'ont pas de score. |

---

## Lot 15 — Cartes d'actualité interactives

✅ Clôturé · Premier lot du plan « interface complète ».

**Objectif** : chaque carte de l'édition s'ouvre au clic et montre l'essentiel, sans quitter l'édition.

**Fait**

| Sujet | Contenu |
|---|---|
| Ouverture | Clic n'importe où sur la carte, ou bouton « Détails ». Les liens (titre, source, discussion, fiche complète) gardent leur rôle. Une sélection de texte n'ouvre pas la carte. |
| Clavier | Bouton avec `aria-expanded` ; Échap referme la carte et rend le focus au bouton. |
| Carte fermée | Titre, source, date, domaines, résumé IA, étiquette de fiabilité (inchangé). |
| Carte ouverte | Blocs de l'IA (contexte, impact…), affirmation et preuve (marquée « en anglais »), fiabilité (éditeur, niveau, corroborations), tags, bouton « Lire l'article original ». |
| Données | Chargées au premier clic seulement, avec le même cache que la fiche complète : ouvrir la fiche ensuite ne refait pas la requête. Si l'API renvoie une autre news que celle de la carte, rien n'est affiché. |
| États | Chargement (zones animées), erreur avec « Réessayer », résumé IA absent (« Pas encore de résumé IA pour cette news »). |

**Vérifié** : 5 nouveaux tests d'interface (25 au total), build, rendu dans le navigateur sur ordinateur et téléphone, sans défilement horizontal.

---

# Lots suivants

Plan revu le 9 octobre 2026 pour intégrer le besoin « interface complète et gestion du produit » : piloter LucidNews depuis l'interface, sans terminal pour les opérations courantes. Les anciens lots 15 à 18 sont repris et renumérotés selon le nouvel ordre (voir la correspondance plus bas).

## Ordre d'exécution et dépendances

| Ordre | Lot | Dépend de | Pourquoi à cette place |
|---|---|---|---|
| ✅ | 15 — Cartes d'actualité interactives | — | Clôturé. |
| 1 | 16 — Socle de pilotage et Réglages | — | Écriture sécurisée de la config et des clés : prérequis des lots 17, 18 et 20. |
| 2 | 17 — Gestion des sources | 16 | Ajouter, modifier, activer, supprimer une source demande l'écriture de la config. |
| 3 | 18 — Domaines surveillés et couverture | 16, 17 | Les recommandations de sources s'ajoutent avec l'outil du lot 17. |
| 4 | 19 — Qualité de la veille | 18 (couverture), 12 (filtrage) | Rassemble couverture, santé, fraîcheur, doublons et fiabilité sur une page. |
| 5 | 20 — Lancer et planifier les runs | 16 | Dernier usage qui demande encore le terminal. |
| 6 | 21 — Newsletter : contenu et préférences | 20 (fréquence) | Hebdomadaire, niveau de détail, aperçu. |
| 7 | 22 — Newsletter : envoi fiable | 21 | Opt-in, désinscription, fournisseur d'e-mails, journal des envois. |
| 8 | 23 — Recherche dans l'archive | — | Utile seul ; placé après le cœur du pilotage. |
| 9 | 24 — Finitions de l'interface | 15 à 23 | Mode sombre et contrastes, une fois toutes les pages créées. |
| 10 | 25 — Dette technique | — | Renommage du paquet en fin de chantier, pour ne pas gêner les lots en cours. |
| 11 | 26 — Comptes et SaaS | 22, 25 | Hors périmètre actuel. |
| En parallèle | 12 — Annoter au moins 30 news | — | Action humaine ; donne les chiffres de filtrage du lot 19. |

**Correspondance avec l'ancien plan** : ancien 15 (finitions) → 24 · ancien 16 (newsletter) → 21 et 22 · ancien 17 (comptes et SaaS) → 26 · ancien 18 (dette technique) → 25.

## Navigation visée

On garde les écrans existants et on n'ajoute qu'**une** page : Réglages.

| Page | Contenu après le plan |
|---|---|
| Édition | Édition du jour, cartes interactives (lot 15). |
| Archives | Éditions passées, recherche (lot 23). |
| Sources | Onglet « Sources » : santé et gestion (lot 17). Onglet « Domaines » : domaines suivis, couverture, recommandations (lot 18). |
| Qualité | Onglet « Vue d'ensemble » : indicateurs de la veille (lot 19). Onglets « Annoter » et « Résultats » : existants. |
| Préférences | Préférences des abonnés (existant), niveau de détail et aperçu de la newsletter (lot 21). |
| Réglages (nouvelle) | Clés API, IA, collecte et traitement (lot 16), lancement et planification des runs (lot 20). |

## Lot 12 — Annoter au moins 30 news

🟡 Action humaine · Prérequis à toute conclusion sur la qualité du filtrage.

- Annoter au moins 30 news dans l'écran Qualité, en mélangeant retenues et écartées. L'archive en contient 48.
- Remplir le champ Notes en cas d'hésitation.
- Lancer `uv run lucidnews-eval` pour obtenir la mesure de départ, puis `--rerun` une fois comme référence.

---

## Lot 16 — Socle de pilotage et page Réglages

📋 Prochain lot.

- **Objectif** : modifier la configuration et les clés API depuis l'interface, de façon sûre.
- **Fonctionnalités** :
  - clés API : saisie, remplacement, suppression ; l'interface montre seulement « configurée » ou « absente », jamais la valeur ;
  - IA : fournisseur, modèle, langues de sortie, quota par minute, budget de tokens par run ;
  - collecte et traitement : fenêtre de collecte, seuils par profil, dédoublonnage par sujet, nombre maximal de news, étiquettes exclues, corroboration, réutilisation de l'archive ;
  - copie de sauvegarde avant chaque écriture et retour à la version précédente.
- **Pages** : Réglages (nouvelle).
- **Frontend** : page Réglages par sections ; formulaires validés (`react-hook-form` + `zod`, déjà installés) ; messages d'erreur par champ.
- **Backend** :
  - module d'écriture de `config.json` : lecture du fichier brut (les `${VARIABLE}` restent intacts), validation par le modèle `Config`, écriture atomique, copie `.bak` ;
  - écriture des clés dans `.env` (déjà ignoré par Git), droits `600` ;
  - rechargement du contexte de l'API après écriture.
- **Données et API** : `GET/PUT /api/settings`, `GET /api/secrets` (noms et état seulement), `PUT/DELETE /api/secrets/<nom>`. Routes locales seulement, avec les protections existantes (adresse locale, Host et Origin vérifiés, corps JSON limité).
- **Sécurité** : aucune clé dans les réponses, les journaux ou les messages d'erreur ; seuls les noms de variables déclarés par la config sont acceptés.
- **Critères de validation** : un réglage changé dans l'interface est appliqué au run suivant ; une config invalide est refusée sans toucher au fichier ; les `${VARIABLE}` sont conservés ; une clé enregistrée n'apparaît nulle part ensuite.
- **Tests** : aller-retour de config, refus d'une config invalide, conservation des `${VARIABLE}`, écriture atomique et sauvegarde, clé jamais renvoyée, routes refusées hors de localhost.
- **Dépendances** : aucune. Prérequis des lots 17, 18 et 20.

---

## Lot 17 — Gestion des sources

📋 Planifié.

- **Objectif** : gérer les sources depuis l'interface, avec leur état réel.
- **Fonctionnalités** :
  - liste des sources configurées, avec statut de santé, dernière collecte réussie, dernière erreur, volume et score de qualité (existants) ;
  - ajouter une source (RSS, dépôt ou compte GitHub, subreddit, chaîne Telegram) ;
  - modifier sa configuration, l'activer ou la désactiver ;
  - supprimer avec confirmation ;
  - « Tester » une source : une collecte d'essai, sans IA ni archive, qui dit combien de contenus elle renvoie ou quelle erreur elle produit ;
  - Hacker News, OSS Insight, GDELT, Google News : activer, désactiver, régler ;
  - X (Twitter) : affiché en lecture seule, car il demande des cookies ou un jeton Apify (procédure documentée).
- **Pages** : Sources, onglet « Sources ».
- **Frontend** : tableau existant enrichi d'actions ; panneau d'édition ; `ConfirmDialog` existant pour la suppression.
- **Backend** : opérations sur `config.sources` via le socle du lot 16 ; test de source par le scraper existant, avec un délai maximal ; contrôle des URL par `url_security` (pas d'adresse interne).
- **Données et API** : `GET /api/sources/config`, `POST /api/sources/config`, `PUT/DELETE /api/sources/config/<clé>`, `POST /api/sources/test`.
- **Critères de validation** : chaque action modifie réellement `config.json` ; une source ajoutée apparaît au run suivant ; aucune source ni aucun statut n'est inventé (une source sans historique est marquée « pas encore collectée ») ; une URL interne ou invalide est refusée.
- **Tests** : ajout, modification, activation, suppression, refus des doublons, test d'une source en échec, URL interne refusée, affichage de l'état « pas encore collectée ».
- **Dépendances** : lot 16.

---

## Lot 18 — Domaines surveillés et couverture

📋 Planifié. Une décision est à prendre avant de commencer (voir « Blocages »).

- **Objectif** : choisir les domaines technologiques suivis et savoir si les sources les couvrent assez.
- **Fonctionnalités** :
  - domaines suivis choisis parmi les 12 catégories de LucidNews (IA et LLM, développement logiciel, Cloud, DevOps, cybersécurité, Data, bases de données, Open Source, infrastructure, outils développeur, Web, technologies émergentes) ;
  - par domaine : sources qui le couvrent réellement (d'après l'archive), volume de news, fraîcheur de la dernière news, part fiable ;
  - lacunes : domaines sous un seuil de sources ou de news ;
  - recommandations : sources du catalogue intégré pour ce domaine, absentes de la config, marquées clairement « recommandée, non configurée » ; ajout en un clic (outil du lot 17) après un test ;
  - option « ne publier que les domaines suivis », appliquée réellement à la sélection du digest.
- **Pages** : Sources, onglet « Domaines ».
- **Frontend** : liste des domaines avec bascule ; carte de couverture par domaine ; badge distinct « disponible » et « recommandée ».
- **Backend** : réglage `digest.watched_categories` ; calcul de couverture à partir de l'archive (catégories données par l'IA, par source) ; catalogue de recommandations construit à partir des 31 flux vérifiés de la config d'exemple et du catalogue de l'assistant, rattachés aux 12 catégories.
- **Données et API** : `GET /api/coverage?days=`, `PUT /api/settings` (domaines suivis), `GET /api/catalog?category=`.
- **Critères de validation** : la couverture vient seulement de l'archive ; une source recommandée n'apparaît jamais comme active ; le filtre des domaines change réellement le digest suivant.
- **Tests** : calcul de couverture sur une archive de test, détection d'une lacune, recommandation qui exclut les sources déjà configurées, filtre appliqué à la sélection.
- **Dépendances** : lots 16 et 17.

---

## Lot 19 — Qualité de la veille

📋 Planifié.

- **Objectif** : savoir, sur une seule page, si la veille est pertinente et fiable.
- **Fonctionnalités** (indicateurs réels, sur une période choisie) :
  - couverture des domaines (lot 18) et diversité des sources (nombre de sources actives, part de la première source) ;
  - sources inactives ou en échec, erreurs de collecte récentes (santé existante) ;
  - fraîcheur : âge des news publiées, délai entre publication et édition ;
  - qualité du filtrage : résultats de l'évaluation (lot 11), avec la mention « échantillon insuffisant » tant que le lot 12 n'est pas fait ;
  - doublons : doublons fusionnés par URL et par sujet à chaque run ;
  - répartition Confirmé / Fiable / Non vérifié / Rumeur, et news sans analyse IA.
- **Pages** : Qualité, nouvel onglet « Vue d'ensemble » (les onglets Annoter et Résultats restent).
- **Frontend** : tuiles d'indicateurs et graphiques (`recharts`, déjà installé) ; chaque indicateur indique sa source et sa période.
- **Backend** : enregistrer par run les compteurs de sélection qui ne sont pas encore gardés (fusions par URL, doublons par sujet, news au-dessus du seuil) ; calcul des indicateurs.
- **Données et API** : nouvelles colonnes de run dans l'archive ; `GET /api/quality/overview?days=`.
- **Critères de validation** : chaque chiffre se retrouve dans l'archive ; un run sans donnée est marqué comme tel, sans valeur inventée.
- **Tests** : calcul de chaque indicateur sur une archive de test, période vide, archive ancienne sans les nouvelles colonnes.
- **Dépendances** : lot 18 pour la couverture ; lot 12 pour des chiffres de filtrage significatifs.

---

## Lot 20 — Lancer et planifier les runs

📋 Planifié. Une décision est à prendre avant de commencer (voir « Blocages »).

- **Objectif** : générer une édition depuis l'interface et régler sa fréquence.
- **Fonctionnalités** :
  - bouton « Lancer un run » avec suivi : étape en cours, journal récent, résultat ;
  - un seul run à la fois ;
  - fréquence de génération (par exemple chaque jour à 7 h), appliquée réellement ;
  - historique des runs (déjà dans l'archive) avec leur statut.
- **Pages** : Réglages, section « Runs ».
- **Frontend** : bouton, état en direct (interrogation régulière), historique.
- **Backend** : lancement du pipeline dans un processus séparé ; verrou ; journal sans secret ; planification selon la décision.
- **Données et API** : `POST /api/runs`, `GET /api/runs/current`, `GET/PUT /api/schedule`.
- **Critères de validation** : un run lancé depuis l'interface produit la même édition qu'en terminal ; un second lancement pendant un run est refusé ; la planification déclenche réellement un run.
- **Tests** : verrou, run en échec affiché comme tel, journal sans clé, planification calculée correctement.
- **Dépendances** : lot 16.

---

## Lot 21 — Newsletter : contenu et préférences

📋 Planifié. Reprend une partie de l'ancien lot 16.

- **Objectif** : une newsletter qui suit réellement les préférences de chaque abonné.
- **Fonctionnalités** :
  - envoi hebdomadaire (le choix existe déjà dans les préférences, l'envoi non) : sélection des meilleures news de la semaine depuis l'archive ;
  - niveau de détail : « bref » (titre, résumé) ou « complet » (avec contexte et impact), appliqué au rendu de l'e-mail ;
  - aperçu de la newsletter d'un abonné dans l'interface ;
  - e-mail HTML refait selon la direction UI.
- **Pages** : Préférences.
- **Frontend** : champ « niveau de détail » ; aperçu dans un cadre isolé (`iframe` sans script).
- **Backend** : sélection hebdomadaire (`items_between` existe) ; rendu selon le niveau de détail ; route d'aperçu.
- **Données et API** : champ `detail_level` dans les préférences ; `GET /api/subscribers/<id>/preview`.
- **Critères de validation** : un abonné hebdomadaire reçoit une sélection de la semaine ; « bref » et « complet » donnent deux e-mails différents ; l'aperçu est identique à l'e-mail envoyé.
- **Tests** : sélection de la semaine, rendu des deux niveaux, aperçu échappé (aucun HTML de source exécuté).
- **Dépendances** : lot 20 pour déclencher l'envoi hebdomadaire.

---

## Lot 22 — Newsletter : envoi fiable

📋 Planifié. Reprend la suite de l'ancien lot 16.

- **Objectif** : des envois sûrs, traçables et conformes.
- **Fonctionnalités** : double opt-in ; lien de désinscription signé ; fournisseur d'e-mails transactionnels à la place du SMTP direct ; journal des envois (qui, quand, quelle édition, résultat) ; abonnés en base de données au lieu du fichier JSON ; envoi selon le fuseau horaire de l'abonné.
- **Pages** : Préférences (statut d'inscription, journal des envois).
- **Frontend** : statut de l'abonné (en attente, confirmé, désinscrit) ; journal des envois.
- **Backend** : jetons signés ; table des envois ; adaptateur du fournisseur ; migration des abonnés.
- **Données et API** : tables `subscribers` et `deliveries` ; routes de confirmation et de désinscription ; clé du fournisseur gérée par le lot 16.
- **Critères de validation** : aucun envoi avant confirmation ; un lien de désinscription modifié est refusé ; chaque envoi est journalisé.
- **Tests** : jetons valides, expirés et falsifiés ; migration JSON vers base ; journal d'un envoi en échec.
- **Dépendances** : lot 21 ; lot 16 pour la clé du fournisseur.

---

## Lot 23 — Recherche dans l'archive

📋 Planifié.

- **Objectif** : retrouver une news passée par mot-clé, domaine, source ou fiabilité.
- **Fonctionnalités** : recherche plein texte, filtres, résultats ouverts dans la carte du lot 15.
- **Pages** : Archives.
- **Frontend** : champ de recherche, filtres, liste de résultats.
- **Backend** : index plein texte SQLite (FTS5) sur l'archive, alimenté à l'enregistrement des news.
- **Données et API** : `GET /api/search?q=&category=&source=&label=`.
- **Critères de validation** : résultats pertinents sur l'archive réelle ; requête vide ou trop longue refusée proprement.
- **Tests** : indexation, recherche, filtres, caractères spéciaux.
- **Dépendances** : aucune (profite du lot 15).

---

## Lot 24 — Finitions de l'interface

📋 Planifié. Ancien lot 15.

- **Objectif** : finir le rendu premium sur toutes les pages, y compris les nouvelles.
- **Fonctionnalités** : mode sombre (couleurs déjà prévues) ; contrastes AA vérifiés sur chaque écran ; socle commun allégé (environ 168 Ko compressé aujourd'hui) ; `eslint` et `prettier`.
- **Pages** : toutes.
- **Frontend** : jetons de couleur sombres, contrôle des contrastes, découpage du socle.
- **Backend** : aucun.
- **Critères de validation** : chaque page lisible dans les deux thèmes ; aucune erreur de lint ; poids du socle réduit et mesuré.
- **Tests** : tests existants dans les deux thèmes, contrôle automatique des contrastes.
- **Dépendances** : lots 15 à 23 (pour couvrir toutes les pages).

---

## Lot 25 — Dette technique

📋 Planifié. Ancien lot 18.

- Renommer le paquet Python `src` en `lucidnews` : tous les imports et points d'entrée sont concernés.
- Découper `orchestrator.py` (environ 1 450 lignes) en étapes : collecte, sélection, envoi.
- Métadonnées fusionnées entre sources : les auteurs peuvent se mélanger (par exemple « Lobsters » affiché sur une news Hacker News).
- **Critère** : aucun changement de comportement ; tous les tests passent sans modification de fond.

---

## Lot 26 — Comptes et SaaS (phase 4)

📋 Planifié, hors périmètre actuel. Ancien lot 17.

- Comptes utilisateurs et authentification. Les pages Préférences et Réglages passeront alors d'un usage local à un usage par compte, avec des rôles (administrateur, abonné).
- Activation des limites de l'offre Free et de l'offre Premium.
- Paiement, seulement après validation du produit.

---

## Paramètres : où ils vivent et comment ils s'appliquent

Un paramètre n'est ajouté que s'il est réellement appliqué par le système.

| Paramètre | Portée | Page | Appliqué par | Lot |
|---|---|---|---|---|
| Langues de génération | Toute l'application | Réglages | Enrichissement (une version par langue) | 16 |
| Langue reçue | Un abonné | Préférences | Choix de la version à envoyer | Existant |
| Domaines suivis | Toute l'application | Sources › Domaines | Couverture et filtre du digest | 18 |
| Domaines reçus | Un abonné | Préférences | Sélection par abonné | Existant |
| Sources actives | Toute l'application | Sources | Collecte | 17 |
| Sources reçues | Un abonné | Préférences | Sélection par abonné | Existant |
| Fréquence de génération | Toute l'application | Réglages › Runs | Planification | 20 |
| Fréquence de réception | Un abonné | Préférences | Envoi quotidien ou hebdomadaire | 21 |
| Importance minimale, infos non confirmées, nombre de news | Un abonné | Préférences | Sélection par abonné | Existant |
| Niveau de détail des résumés | Un abonné | Préférences | Rendu de l'e-mail | 21 |
| Critères de pertinence (seuils par profil, étiquettes exclues) | Toute l'application | Réglages | Sélection du digest | 16 |

**Écartés** : consignes IA personnalisées par abonné (coût IA multiplié par le nombre d'abonnés), longueur de résumé générée à la demande (demanderait un appel IA par abonné ; le niveau de détail réutilise les textes déjà produits).

## Blocages et décisions en attente

| Sujet | Bloque | Recommandation |
|---|---|---|
| Lots 14 bis et 15 terminés mais pas encore commités | Rien, mais à faire avant le lot 16 | Commiter avec les messages préparés. |
| Annotations du lot 12 | Les chiffres de filtrage du lot 19 (affichés « échantillon insuffisant » d'ici là) | Annoter au fil de l'eau. |
| Domaines personnalisés au-delà des 12 catégories | Le lot 18 | Commencer avec les 12 catégories ; un domaine libre demande de changer les consignes IA, l'évaluation et les préférences. |
| Méthode de planification des runs | Le lot 20 | Planificateur intégré au serveur local, actif tant qu'il tourne ; sinon tâche système (launchd ou cron) générée par l'interface. |
| Source X (Twitter) | Rien | Lecture seule dans l'interface : elle dépend de cookies ou d'un jeton Apify. |

## Analyse : besoins d'une newsletter moderne

| Besoin | Utilité | Données | Dépendances | Backend | Frontend | Risques | Décision |
|---|---|---|---|---|---|---|---|
| Envoi hebdomadaire | Lecteurs qui ne veulent pas un e-mail par jour | Archive (`items_between`) | Planification | Sélection de la semaine | Aucun (choix existant) | Doublons d'une semaine sur l'autre | Retenu, lot 21 |
| Niveau de détail | Lecture rapide ou approfondie | Blocs d'enrichissement existants | Rendu e-mail | Rendu à deux niveaux | Champ de préférence | Aucun coût IA | Retenu, lot 21 |
| Aperçu de la newsletter | Vérifier avant d'envoyer | Préférences + digest | Rendu e-mail | Route d'aperçu | Cadre isolé | HTML de source mal échappé | Retenu, lot 21 |
| Double opt-in et désinscription signée | Conformité (RGPD), réputation d'envoi | Jetons, statut d'abonné | Fournisseur d'e-mails | Jetons signés, routes publiques | Statut | Clé de signature à protéger | Retenu, lot 22 |
| Fournisseur transactionnel | Délivrabilité, rebonds | Clé du fournisseur | Lot 16 | Adaptateur | Aucun | Coût, dépendance externe | Retenu, lot 22 |
| Journal des envois | Savoir ce qui est parti et ce qui a échoué | Table des envois | Lot 22 | Écriture à chaque envoi | Liste | Données personnelles à limiter | Retenu, lot 22 |
| Recherche dans l'archive | Retrouver une info passée | Archive | Aucune | Index FTS5 | Recherche | Taille de l'index | Retenu, lot 23 |
| Statistiques d'ouverture et de clic | Mesurer l'intérêt | Pixels et liens suivis | Fournisseur | Webhooks | Graphiques | Vie privée, consentement | Reporté (après le lot 22, sur décision) |
| Alertes immédiates (news critiques) | Ne pas attendre l'édition | Importance « critique » | Planification, envoi fiable | Envoi hors édition | Préférence | Trop d'e-mails | Reporté |
| Flux RSS des éditions | Lire dans un lecteur RSS | Éditions | Aucune | Route RSS | Lien | Faible | Reporté (simple, à ajouter si demandé) |
| Favoris, « à lire plus tard » | Garder une news | Lien news-utilisateur | Comptes | Table | Bouton | Aucun sans comptes | Reporté au lot 26 |

---

# Annexes

## Points observés à confirmer

| Observation | Où | Suite |
|---|---|---|
| 18 sources sur 29 n'ont rien collecté sur les 8 runs archivés. | Lot 8 | À confirmer avec des runs quotidiens. Elles passeront « silencieuses » après 5 runs vides. |
| La corroboration n'a pas encore joué sur un vrai run. | Lot 5 | À observer. Le lot 14 bis augmente les chances (news sous le seuil et 72 h d'archive). |
| La qualité d'un rapprochement « même événement » fait par l'IA. | Lot 14 bis | À surveiller avec l'écran Qualité (« faux fiables ») : un mauvais rapprochement avec un site officiel donnerait « Confirmé ». |
| Un compte officiel est vu comme une source communautaire (cas curl). | Lot 9 | ✅ Réglé au lot 13. |
| 13 domaines de l'archive restent inconnus du registre (blogs personnels, sites de projets, phys.org…). | Lot 13 | À trier au fil des runs, après vérification de chaque site. |
| Aucun compte X officiel n'est inscrit (non vérifiable sans connexion). | Lot 13 | À ajouter dans `reliability.accounts` par la personne qui gère le projet. |
| Les comptes GitHub suivis ne sont pas filtrables dans les préférences (leurs news portent le dépôt). | Lot 10 | À revoir si le besoin apparaît. |
| Quota journalier exact de `gemini-3.5-flash-lite` sur l'offre gratuite. | Lot 5 | À confirmer. Un run de 24 h a consommé environ 140 000 tokens. |
| Choix de l'offre IA pour la production. | Lot 1 | Décision à prendre. |
| Message exact d'un quota épuisé chez chaque fournisseur. | Lot 14 | Gemini : format de l'erreur vérifié dans le code du SDK. Autres fournisseurs : d'après leur documentation. À confirmer lors d'un vrai épuisement. |
| Une édition passée montre l'état le plus récent de ses news : une news publiée « Sans analyse IA » y apparaît avec son analyse après le run qui l'a analysée, même si son score est bas. | Lot 14 | Comportement de l'archive (une ligne par news). À figer par édition si cela gêne. |

## Décisions prises

| Question | Décision |
|---|---|
| Nom du produit | LucidNews |
| Fonctions retirées | WeChat, README zh/ja, site Pages, Finance + OpenBB |
| Profil `ai-creator` | Gardé, traduit en anglais |
| Plan de la phase 2 | Archive → échecs IA → santé des sources → corroboration → évaluation → registre |
| Sources mortes | Retirées de la config locale |
| Premier écran | Édition du jour, avec de vraies données |
| API | En Python, à côté du moteur |
| Images des modèles | Non versionnées (`Templates/` ignoré) |
| Lot après Archives et Sources | Fiche d'une news |
| Préférences | Version locale, sans comptes (A) |
| Lot après Préférences | Mesure de la qualité (A) |
| Registre de confiance | Lancé avant la fin des annotations ; seulement des comptes et sites vérifiés à la main |
| Lot après le registre | Budget IA et réutilisation de l'enrichissement d'abord (A) |
| Quota IA épuisé | L'application continue et affiche les news sans analyse IA, seulement dans ce cas |
| Lot après le lot 14 | Lot 14 bis (recommandation A, prise par défaut) |
| Interface complète (9 oct.) | Plan revu : lots 15 à 26 réordonnés, une seule page ajoutée (Réglages) |
| Rôle du score de qualité | Départager les news de même score, sans jamais passer devant une news mieux notée |
| Style des réponses | Skill explainer : français simple, sections, questions oui/non |

## Historique des commits

| Commit | Date | Lot | Message |
|---|---|---|---|
| `57432f9` | 2026-10-06 | 1 | import Horizon baseline (MIT, © 2026 Thysrael) |
| `e9cd02b` | 2026-10-06 | 1 | rebrand to LucidNews and drop legacy Horizon-specific features |
| `70c1f41` | 2026-10-06 | 1 | harden digest selection, rendering and source config |
| `22da2c9` | 2026-10-06 | 1 | reliability scoring, IT category taxonomy and en/fr localization |
| `e9d1b64` | 2026-10-06 | 1 | subscriber preferences, plan hooks and per-preference delivery |
| `8a745a8` | 2026-10-06 | 1 | curated IT source catalog and documented environment |
| `2cc5721` | 2026-10-06 | 1 | AI request quota limiter, classifier retries and product documentation |
| `0b6f852` | 2026-10-06 | 1 | ignore local config copies, env variants and key files |
| `d62ca35` | 2026-10-06 | 1 | readable apostrophes in digests and localized content-angle prefix |
| `c01db56` | 2026-10-06 | 1 | fix leftover command name in configuration guide |
| `933b55a` | 2026-10-06 | 2 | SQLite archive of runs and items with analysis reuse |
| `47b4110` | 2026-10-06 | 3 | retry items whose AI analysis or enrichment failed |
| `f2269ab` | 2026-10-06 | 4 | per-source health tracking and lucidnews-sources report |
| `54f0e88` | 2026-10-06 | 5 | corroboration by independent publishers |
| `9e0496c` | 2026-10-07 | 6, 7, 8 | read-only API and React app (edition, archive, source health) |
| `2e77a82` | 2026-10-08 | 9 | item detail page with full reliability breakdown |
| `efc5fbb` | 2026-10-08 | 10 | local subscriber preferences screen |
| `337b0a2` | 2026-10-08 | 11 | hand-annotation quality evaluation |
| `b7abe50` | 2026-10-09 | — | lots overview (closed and upcoming work) |
| `b1c18cf` | 2026-10-09 | 13 | social accounts as publishers and wider trust registry |
| `7bcd919` | 2026-10-09 | 14 | run token budget, non-blocking quota exhaustion and enrichment reuse |
