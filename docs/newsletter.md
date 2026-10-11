# Newsletter

Le module `src/newsletter/` pose les fondations d'une plateforme de newsletter tech : abonnés, préférences, plans, sélection personnalisée et plan d'envoi. Il n'y a pas encore d'interface d'inscription : les abonnés arrivent par email (IMAP) ou via le code.

## Modèle

```
Subscriber
├── email
├── plan                 free | premium          (aucun paiement, aucune restriction aujourd'hui)
├── created_at
└── preferences: DigestPreferences
    ├── language          "en", "fr"…            (défaut : en)
    ├── categories        ["ai", "cybersecurity"] (vide = toutes)
    ├── sources           ["hackernews", "LWN.net"] types de source ou noms de flux (vide = toutes)
    ├── frequency         daily | weekly         (weekly : les 7 derniers jours, voir plus bas)
    ├── min_importance    low | medium | high | critical (vide = tout le digest)
    ├── include_unconfirmed  true                 (false = exclut « Non vérifié » et « Rumeur »)
    ├── max_items         null                   (plafond par email)
    └── detail_level      brief | complete       (défaut : complete)
```

## Fonctionnement d'un envoi

À la fin d'un run, si `email.enabled` vaut `true` :

1. `plan_deliveries` charge les abonnés et applique les limites de leur plan (`effective_preferences`).
2. Les abonnés aux préférences identiques sont regroupés : **un seul rendu par jeu de préférences**, quel que soit le nombre d'abonnés.
3. Pour chaque groupe, `select_items` filtre le digest du jour (déjà trié par score) : catégories, sources, importance, fiabilité, plafond.
4. Le digest est rendu dans la langue du groupe, au niveau de détail choisi, et envoyé avec un sujet localisé.

Si le quota IA a été épuisé pendant le run, les news non analysées sont ajoutées dans une section à part, « Sans analyse IA ». Comme elles n'ont ni catégorie, ni importance, ni vérification, un abonné ne les reçoit que s'il ne filtre ni par catégorie ni par importance et accepte les infos non confirmées. Son filtre de sources et son plafond `max_items` s'appliquent toujours (les news analysées passent en premier).

Un abonné ne reçoit que sa langue.

## Niveau de détail

- **bref** : titre, fiabilité, résumé, source.
- **complet** : le bref, plus les blocs de contexte, les références et les tags de l'enrichissement.

Les deux réutilisent les textes déjà produits : aucun appel IA supplémentaire. Deux niveaux différents sont deux rendus distincts.

## Envoi hebdomadaire

Un abonné `weekly` reçoit les meilleures news **publiées des 7 derniers jours** (archive), pas le digest du jour.

- Jour d'envoi : `email.weekly_day` (0 = lundi, défaut), au premier run de ce jour. Le run peut venir de la planification ou d'un lancement manuel ; il est aussi déclenché quand le run du jour ne trouve rien de nouveau.
- Au plus une fois par semaine ISO : la semaine envoyée est notée dans `data/weekly_sent.json`. Un second run le même jour n'envoie rien. Si le fichier est illisible, l'envoi n'est pas bloqué.
- Plafond : `email.weekly_max_items` (15), ou le `max_items` de l'abonné s'il est plus bas.
- Pas de news non analysées, et aucun e-mail si rien ne correspond aux préférences de la semaine.
- Le Mac doit être allumé au moment du run : sans run ce jour-là, la semaine n'est pas envoyée (elle l'est au prochain run du même jour de la semaine suivante).

## Aperçu

Dans Préférences, « Voir l'aperçu » montre l'e-mail d'un abonné avec ses préférences enregistrées. Il est construit par le même code que l'envoi (`plan_deliveries` puis `render_selection`), depuis l'archive : dernière édition publiée pour un abonné quotidien, 7 derniers jours pour un hebdomadaire. Route : `GET /api/subscribers/<id>/preview` (API locale seulement). Le HTML est affiché dans un `iframe` sans script.

## Rendu de l'e-mail

`src/newsletter/render.py` convertit le Markdown du digest en e-mail HTML et texte. Le texte des sources est déjà échappé par le générateur de digest ; tout `<` restant devient littéral. Aucun script, aucune image distante, aucun formulaire.

## Plans Free / Premium

`src/newsletter/plans.py` contient `PLAN_LIMITS` : nombre maximal de catégories, de sources, d'items, fréquences autorisées. **Les deux plans sont illimités aujourd'hui.** Le jour où l'offre Premium existera, il suffira de modifier cette table : le code d'envoi applique déjà les limites. Il n'y a ni paiement ni paywall.

## Stockage

`data/subscribers.json` (ignoré par git) :

```json
{ "version": 1, "subscribers": [ { "email": "lecteur@example.com", "plan": "free", "preferences": { "language": "fr", "categories": ["ai"] }, "created_at": "2026-10-06T08:00:00Z" } ] }
```

- L'ancien format (liste d'emails) est lu automatiquement et converti à la prochaine écriture.
- La désinscription **supprime** l'abonné : aucune donnée n'est conservée.
- `SubscriberStore` (`load`, `save`, `get`, `add`, `remove`) est la seule porte d'accès. Le remplacer par une base de données ne touche pas le code d'envoi.

## Inscription par email

Avec `email.imap_enabled`, la boîte configurée est relevée à chaque run :

- un email dont le sujet vaut `SUBSCRIBE` inscrit l'expéditeur, avec les préférences par défaut ;
- un email dont le sujet vaut `UNSUBSCRIBE` le désinscrit.

## Ajouter un abonné depuis le code

```python
from src.newsletter import DigestPreferences, SubscriberStore

store = SubscriberStore("data/subscribers.json")
store.add("lecteur@example.com", DigestPreferences(language="fr", categories=["ai", "cybersecurity"], min_importance="high"))
```

## Prochaines étapes

Voir la [roadmap](roadmap.md) : gestion des préférences par lien, double opt-in, fournisseur d'emailing transactionnel, base de données.
