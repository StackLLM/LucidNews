# Direction UI — LucidNews

Ce document fixe la direction visuelle du futur frontend. Aucun écran n'est encore
construit.

## 1. Les deux références analysées

| Référence                                                     | Ce que c'est                             | Ce qu'elle apporte                                                                                |
| ------------------------------------------------------------- | ---------------------------------------- | ------------------------------------------------------------------------------------------------- |
| **A — « Agenta »** (`Templates/image.png` du dépôt LucidNews) | Page d'accueil marketing d'un SaaS       | L'ambiance : fond clair teinté, cartes translucides, profondeur, graphique, fil chronologique     |
| **B — « Paypay »** (`Mysalary/Templates/image.png`)           | Écran d'application (édition de facture) | Les composants d'app : grille 2 colonnes, cartes blanches, tableau, champs, interrupteur, boutons |

**Choix retenu : A pour l'atmosphère, B pour la structure des écrans.**
A seul est une page vitrine, il ne fournit aucun composant d'application.
B seul est propre mais plat : pas de verre, pas de profondeur.

Les deux images ont été analysées avec la méthode de la skill UI-Stealer :
on garde la **structure**, on remplace la **palette** et le **contenu**.
Les règles propres à Melko (charte Encre/Forêt/Saphir, mascotte, scripts `.bat`,
ports, double dépôt) ne s'appliquent pas à LucidNews.

## 2. Analyse détaillée

### Structure

- A : barre de navigation en pilule sombre, flottante, centrée. Héros texte à gauche,
  grappe de cartes de données à droite. Puis un grand bloc sombre arrondi.
- B : barre de navigation blanche pleine largeur, onglet actif souligné. Fil d'Ariane.
  Grille **2/3 + 1/3** : contenu principal à gauche, colonne de cartes d'appoint à droite.
- **Pour LucidNews** : la grille 2/3 + 1/3 de B porte la lecture (article à gauche,
  fiabilité et sources à droite). La navigation flottante de A, en version claire et
  en verre, sert de barre supérieure.

### Composants

- A : carte graphique, cartes KPI (icône + chiffre + légende), liste chronologique
  avec pastilles colorées, notifications flottantes (« Invoice sent to… »).
- B : carte d'identité (logo rond + nom + email), bandeau coloré à formes circulaires,
  tableau éditable, bloc « montant dû » avec gros chiffre, interrupteur, boutons
  secondaires pâles, bouton principal plein.
- **Pour LucidNews** :
  - bandeau coloré de B → carte « Édition du jour » (date, langue, 48 collectés → 13 retenus) ;
  - liste chronologique de A → historique d'un sujet et fil des éditions ;
  - bloc « montant dû » de B → carte « Fiabilité » (étiquette, type de source, corroborations) ;
  - cartes KPI de A → chiffres de santé des sources ;
  - notification flottante de A → retour discret après une action (préférences enregistrées).

### Spacing

- B : grille de 8 px. Marges de carte ≈ 32 px. Écart entre cartes ≈ 24 px.
  Lignes de tableau ≈ 56 px.
- A : beaucoup d'air autour du héros, cartes serrées entre elles (≈ 16 px).
- **Pour LucidNews** : grille de 4/8 px. Carte : 32 px (bureau), 20 px (mobile).
  Écart entre cartes : 24 px. Largeur de lecture limitée à ≈ 68 caractères.

### Typographie

- A et B : sans-serif géométrique, proche de Gilroy (estimation, police non
  identifiable avec certitude depuis une image). Titres très gras, chiffres en gras,
  textes secondaires gris clair et fins.
- **Pour LucidNews**, deux familles seulement :
  - **Plus Jakarta Sans** (interface, chiffres, étiquettes) : proche du rendu
    géométrique des modèles, libre de droits ;
  - **Newsreader** (titres d'articles et texte de lecture) : serif dessinée pour la
    lecture d'actualité. Elle donne le ton éditorial d'une newsletter.
- Échelle : 12 · 13 · 14 · 16 · 18 · 22 · 28 · 36 · 48 px. Chiffres tabulaires
  pour les scores et les compteurs.

### Cartes

- B : blanc pur, rayon ≈ 24 px, ombre très diffuse et très claire, aucune bordure.
- A : blanc ou translucide, bordure fine claire, ombre plus marquée sous les cartes
  flottantes.
- **Pour LucidNews** : deux niveaux.
  - **Carte de lecture** : blanc opaque, rayon 24 px, ombre diffuse (B). Jamais de
    verre sous un texte long : la lisibilité passe avant l'effet.
  - **Carte flottante** : verre (A), pour la navigation, la colonne de droite fixe,
    les menus et les notifications.

### Boutons

- B : principal = indigo plein, grand, rayon 14 px. Secondaire = fond indigo très pâle,
  texte indigo. Tertiaire = blanc + icône.
- A : pilules avec flèche « → », contour fin sur fond sombre.
- **Pour LucidNews** : principal plein (couleur d'accent), secondaire pâle, fantôme
  avec contour fin. Flèche « → » qui glisse de 2 px au survol.

### Inputs

- B : champs à fond blanc, bordure gris très clair, rayon 12 px, préfixe « $ » grisé,
  placeholder gris clair.
- **Pour LucidNews** : même base. Focus = anneau d'accent doux à 3 px. Erreur = texte
  court sous le champ, jamais une couleur seule.

### Tableaux

- B : en-têtes gris fins, séparateurs horizontaux seulement, pas de lignes verticales,
  pas de zébrage.
- **Pour LucidNews** : même sobriété pour le tableau de santé des sources. Statut en
  pastille colorée + texte. Sur mobile, chaque ligne devient une carte.

### Graphiques

- A : courbe blanche épaisse et lissée sur fond violet, point mis en avant avec une
  bulle de valeur, grille verticale très légère.
- **Pour LucidNews** : courbe lissée, fond clair, un seul point mis en avant,
  bulle de valeur. Usages : contenus retenus par édition, taux de sélection par source,
  répartition par catégorie. Pas de 3D, pas de camembert décoratif.

### Effets

- A : fond menthe très pâle, motif de grandes lignes arrondies à très faible opacité,
  cartes translucides, ombres colorées sous les cartes violettes.
- B : formes circulaires semi-transparentes dans le bandeau indigo.
- **Pour LucidNews** : fond teinté + motif de lignes à ≈ 5 % d'opacité + deux halos
  flous très lents. Verre réservé aux éléments flottants. Formes circulaires de B
  dans la carte « Édition du jour ».

### Animations

- Les modèles sont statiques. Les animations sont donc une **création**, pas une copie.
- Entrée des cartes en cascade (fondu + 12 px). Survol : la carte monte de 2 px et
  son ombre s'élargit. Changement d'écran en fondu. Tracé progressif de la courbe à
  l'apparition. Compteurs qui défilent une seule fois.
- Durées : 150 ms (survol), 250 ms (ouverture), 400 ms (entrée). Courbe
  `cubic-bezier(0.22, 1, 0.36, 1)`.
- Respect de `prefers-reduced-motion` et bouton « animations off » (repris de la skill).

### Responsive

- B : 2 colonnes. A : héros + grappe de cartes.
- **Pour LucidNews** :
  - ≥ 1280 px : grille 2/3 + 1/3, colonne de droite fixe au défilement ;
  - 768–1279 px : une colonne, la carte « Fiabilité » remonte sous le titre ;
  - < 768 px : navigation en barre basse, tableaux en cartes, marges de 16 px.

### Détails visuels

- Pastilles d'icône rondes à fond pâle (B : « Customize », A : liste chronologique).
- Badge de vérification bleu à côté d'un nom (B : « Monlight Agency ») → réutilisé pour
  les sources officielles.
- Menu « … » discret en haut à droite des cartes.
- Séparateurs très fins, presque invisibles.

## 3. Ce qu'on ne reprend pas

| Élément                                            | Pourquoi                                          |
| -------------------------------------------------- | ------------------------------------------------- |
| Dégradés violet saturé, cartes orange et rose de A | Trop chargé. Contraire de « calme »               |
| Gros bloc noir pleine largeur de A                 | Rupture trop forte pour un outil de lecture       |
| Chiffres marketing « 45+ », « 89 % »               | Aucun chiffre inventé dans LucidNews              |
| Icônes 3D jaunes de A                              | Style différent du reste, bruit visuel            |
| Flux de paiement, « Send Invoice », logo Wise de B | Pas de paiement dans cette phase                  |
| Avatar emoji de B                                  | Le produit n'a pas encore de comptes utilisateurs |

## 4. Couleurs propres à LucidNews

La couleur d'accent ne doit **jamais** se confondre avec les couleurs de fiabilité.
La fiabilité est le cœur du produit : elle a sa propre gamme.

| Rôle             | Clair                                                                   | Usage                                                        |
| ---------------- | ----------------------------------------------------------------------- | ------------------------------------------------------------ |
| Encre            | `#0F1530`                                                               | Texte principal, navigation (reprend le bleu nuit de A)      |
| Texte secondaire | `#5B6478`                                                               | Métadonnées, légendes                                        |
| Fond             | `#F2F6F6`                                                               | Fond de page, teinte menthe très pâle (A)                    |
| Surface          | `#FFFFFF`                                                               | Cartes de lecture                                            |
| Verre            | `rgba(255,255,255,0.62)` + flou 20 px + bordure `rgba(255,255,255,0.7)` | Éléments flottants                                           |
| Accent           | `#4C3FD8`                                                               | Bouton principal, lien actif, courbe (indigo de B, désaturé) |
| Accent pâle      | `#EEECFC`                                                               | Boutons secondaires, pastilles d'icône                       |
| Confirmé         | `#0E7C5A`                                                               | Étiquette « Confirmé »                                       |
| Fiable           | `#1F6FB2`                                                               | Étiquette « Fiable »                                         |
| Non vérifié      | `#B26A00`                                                               | Étiquette « Non vérifié »                                    |
| Rumeur           | `#B4233C`                                                               | Étiquette « Rumeur »                                         |

- Chaque étiquette de fiabilité = couleur **+ texte + icône**. Jamais la couleur seule.
- Contrastes à vérifier (AA minimum) au moment du développement : à confirmer.
- Mode sombre : prévu dans les tokens, réalisé après le mode clair.

## 5. Ombres et rayons

| Token            | Valeur                                                               |
| ---------------- | -------------------------------------------------------------------- |
| `radius-card`    | 24 px                                                                |
| `radius-control` | 12 px                                                                |
| `radius-pill`    | 999 px                                                               |
| `shadow-card`    | `0 1px 2px rgba(15,21,48,.04), 0 12px 40px -16px rgba(15,21,48,.12)` |
| `shadow-float`   | `0 24px 64px -24px rgba(15,21,48,.22)`                               |
| `shadow-accent`  | `0 12px 28px -12px rgba(76,63,216,.45)` (bouton principal seulement) |
