# Dépendances du frontend

Règle : **une dépendance = un besoin réel**. Rien n'est ajouté pour faire joli.
Les versions installées sont fixées par `package-lock.json`.
Un paquet n'est installé que lorsqu'un écran en a besoin.

## Installé aujourd'hui

| Paquet                                                                               | Version    |
| ------------------------------------------------------------------------------------ | ---------- |
| `react`, `react-dom`                                                                 | 19.3       |
| `react-router`                                                                       | 8.4        |
| `@tanstack/react-query`                                                              | 5.104      |
| `motion`                                                                             | 14.0       |
| `lucide-react`                                                                       | 1.52       |
| `zod`                                                                                | 4.6        |
| `@fontsource-variable/plus-jakarta-sans`, `@fontsource-variable/newsreader`          | 5.3        |
| `recharts` (Santé des sources)                                                       | 3.10       |
| `react-day-picker` + `date-fns` (Archives)                                           | 10.0 / 4.4 |
| `radix-ui` (interrupteur, confirmation de suppression)                               | 1.7        |
| `react-hook-form` + `@hookform/resolvers` (Préférences)                              | 7.89 / 5.9 |
| Build : `vite` 8.3, `typescript` 7.0, `tailwindcss` + `@tailwindcss/vite` 4.3        |            |
| Tests : `vitest` 5.0, `jsdom`, `@testing-library/react`, `@testing-library/jest-dom` |            |

## Prévu, pas encore installé

`eslint`, `prettier`.

## Socle

| Paquet                          | Rôle                    | Justification                                                                                                     |
| ------------------------------- | ----------------------- | ----------------------------------------------------------------------------------------------------------------- |
| `react`, `react-dom` (19)       | Interface               | Choix du projet                                                                                                   |
| `typescript`                    | Typage                  | Les données viennent de modèles Python stricts (pydantic). Les types évitent les erreurs de champ                 |
| `vite` + `@vitejs/plugin-react` | Serveur de dev et build | Démarrage rapide, build statique servi par nginx                                                                  |
| `react-router` (8)              | Navigation entre écrans | 5 écrans prévus. L'état des filtres (date, langue, catégorie) vit dans l'URL : un lien partagé rouvre la même vue |

## Par besoin

| Besoin                       | Paquet                                                                      | Justification                                                                                                         | Rejeté et pourquoi                                                                            |
| ---------------------------- | --------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------- |
| **UI (styles)**              | `tailwindcss` (4)                                                           | Tokens de la direction UI déclarés une fois. Le verre se fait avec ses classes natives                                | CSS-in-JS : coût à l'exécution, rien de plus                                                  |
| **UI (composants)**          | `radix-ui`                                                                  | Menus, fenêtres, onglets, interrupteur, info-bulles accessibles au clavier et aux lecteurs d'écran, sans style imposé | Bibliothèque stylée complète (MUI, Chakra) : impose son look, contraire d'un rendu sur mesure |
| **Charts**                   | `recharts`                                                                  | Courbe lissée, point mis en avant, bulle de valeur, barres : couvre les 3 graphiques prévus                           | `d3` seul : trop bas niveau. `chart.js` : rendu canvas, moins facile à styler finement        |
| **Animations**               | `motion`                                                                    | Cascade d'entrée, transitions d'écran, sortie animée des éléments : impossible proprement en CSS seul                 | GSAP : surdimensionné pour des transitions d'interface                                        |
| **Glass effects**            | _aucun_                                                                     | `backdrop-filter` + transparence CSS suffisent                                                                        | Toute librairie « glassmorphism » : inutile                                                   |
| **Icônes**                   | `lucide-react`                                                              | Trait fin et régulier, cohérent avec le rendu des modèles. Import icône par icône                                     | Plusieurs jeux d'icônes mélangés                                                              |
| **Formulaires**              | `react-hook-form`                                                           | Écran des préférences : langues, catégories, fréquence, seuil. Peu de rendus, gestion des erreurs                     | Gestion à la main : vite fragile dès 6 champs                                                 |
| **Validation**               | `zod` + `@hookform/resolvers`                                               | Un même schéma valide le formulaire **et** les réponses de l'API. Reflète les modèles Python                          | Validation dupliquée à la main                                                                |
| **Dates / calendrier**       | `react-day-picker` (+ `date-fns`, déjà requis par lui)                      | Choisir une édition passée dans les archives. Libellés FR/EN via les locales `date-fns`                               | Plusieurs librairies de dates                                                                 |
| **Gestion d'état (serveur)** | `@tanstack/react-query`                                                     | Éditions, articles, santé des sources : cache, rechargement, états de chargement et d'erreur                          | Redux : trop lourd pour des données surtout lues                                              |
| **Gestion d'état (local)**   | _aucun_                                                                     | État d'interface = `useState` + contexte + URL                                                                        | Zustand : à ajouter seulement si un état partagé complexe apparaît                            |
| **Polices**                  | `@fontsource-variable/plus-jakarta-sans`, `@fontsource-variable/newsreader` | Polices servies par l'app elle-même : pas d'appel externe, pas de saut de mise en page                                | Google Fonts en ligne : dépendance réseau et vie privée                                       |

## Ce qui reste sans librairie

| Besoin                      | Solution                                                                                               |
| --------------------------- | ------------------------------------------------------------------------------------------------------ |
| Textes EN/FR de l'interface | Dictionnaires typés, alignés sur les textes déjà présents côté Python. Pluriels via `Intl.PluralRules` |
| Format des dates et nombres | `Intl.DateTimeFormat`, `Intl.NumberFormat`                                                             |
| Animations off              | Contexte React + `prefers-reduced-motion`                                                              |
| Notifications discrètes     | Un composant maison basé sur `motion`                                                                  |

## Outils de développement

| Paquet                                                 | Justification                                                           |
| ------------------------------------------------------ | ----------------------------------------------------------------------- |
| `vitest` + `jsdom`                                     | Tests rapides, même configuration que Vite                              |
| `@testing-library/react` + `@testing-library/jest-dom` | Tester ce que l'utilisateur voit (étiquettes de fiabilité, formulaires) |
| `eslint` + `typescript-eslint`                         | Erreurs courantes détectées avant l'exécution                           |
| `prettier` + `prettier-plugin-tailwindcss`             | Classes Tailwind triées : diffs lisibles                                |

## Total

**15 paquets livrés au navigateur** (dont React, React DOM et les 2 polices).
TypeScript, Vite, Tailwind (via `@tailwindcss/vite`) et les outils ci-dessus
servent seulement au build.
Toute nouvelle dépendance doit être ajoutée à ce fichier avec sa justification.
