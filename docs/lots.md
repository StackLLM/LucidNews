# Lots de travail — LucidNews

Ce document regroupe tous les lots : ceux qui sont **clôturés** et ceux qui
**restent à faire**. Il complète la [roadmap](roadmap.md), qui donne les priorités.

État au 9 octobre 2026. Dernier lot clôturé : lot 14.

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

**Lots suivants**

- [Lot 12 — Annoter au moins 30 news](#lot-12--annoter-au-moins-30-news) 🟡
- [Lot 14 bis — Fin de la phase 2 (données et sources)](#lot-14-bis--fin-de-la-phase-2-données-et-sources) 📋
- [Lot 15 — Finitions de l'interface](#lot-15--finitions-de-linterface) 📋
- [Lot 16 — Newsletter (phase 3)](#lot-16--newsletter-phase-3) 📋
- [Lot 17 — Comptes et SaaS (phase 4)](#lot-17--comptes-et-saas-phase-4) 📋
- [Lot 18 — Dette technique](#lot-18--dette-technique) 📋

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

# Lots suivants

## Lot 12 — Annoter au moins 30 news

🟡 Action humaine · Prérequis à toute conclusion sur la qualité.

- Annoter au moins 30 news dans l'écran Qualité, en mélangeant retenues et écartées. L'archive en contient 48.
- Remplir le champ Notes en cas d'hésitation.
- Lancer `uv run lucidnews-eval` pour obtenir la mesure de départ.
- Lancer ensuite `--rerun` une fois, comme référence pour les futurs changements de consigne.

---

## Lot 14 bis — Fin de la phase 2 (données et sources)

📋 Planifié. Partie B du lot 14 (la partie A, budget IA, est clôturée).

- Étendre la corroboration aux news sous le seuil et aux runs précédents, grâce à l'archive.
- Donner à chaque source un score de qualité, utilisé dans la sélection.
- Option pour recalculer les étiquettes de l'archive avec le registre actuel (sans appel IA), si l'on veut que l'interface reflète un changement de registre sur les anciennes éditions.

---

## Lot 15 — Finitions de l'interface

📋 Planifié.

- Mode sombre (couleurs déjà prévues dans la direction UI).
- Alléger le socle commun (environ 168 Ko compressé) : version allégée de `motion` et de `zod`.
- Ajouter `eslint` et `prettier`, déjà listés dans les dépendances prévues.
- Vérifier les contrastes (AA minimum) sur tous les écrans.

---

## Lot 16 — Newsletter (phase 3)

📋 Planifié.

- Envoi hebdomadaire : le choix est déjà enregistré dans les préférences, l'envoi n'existe pas encore.
- Double opt-in et lien de désinscription signé.
- Fournisseur d'e-mails transactionnels à la place du SMTP direct (délivrabilité, rebonds, statistiques).
- E-mail HTML refait selon la direction UI.
- Abonnés stockés dans une base de données au lieu du fichier JSON (même interface).
- Envois planifiés selon le fuseau horaire de chaque abonné.

---

## Lot 17 — Comptes et SaaS (phase 4)

📋 Planifié, hors périmètre actuel.

- Comptes utilisateurs et authentification. L'écran Préférences passera alors de la version locale à une version par compte.
- Activation des limites de l'offre Free et de l'offre Premium.
- Paiement, seulement après validation du produit.

---

## Lot 18 — Dette technique

📋 Planifié.

- Renommer le paquet Python `src` en `lucidnews` : tous les imports et points d'entrée sont concernés.
- Découper `orchestrator.py` (environ 1 100 lignes) en étapes : collecte, sélection, envoi.
- Métadonnées fusionnées entre sources : les auteurs peuvent se mélanger (par exemple « Lobsters » affiché sur une news Hacker News).

---

# Annexes

## Points observés à confirmer

| Observation | Où | Suite |
|---|---|---|
| 18 sources sur 29 n'ont rien collecté sur les 8 runs archivés. | Lot 8 | À confirmer avec des runs quotidiens. Elles passeront « silencieuses » après 5 runs vides. |
| La corroboration n'a pas encore joué sur un vrai run. | Lot 5 | À observer quand deux médias couvriront le même événement. |
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
