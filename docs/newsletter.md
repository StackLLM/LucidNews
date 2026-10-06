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
    ├── frequency         daily | weekly         (weekly : stocké, pas encore envoyé)
    ├── min_importance    low | medium | high | critical (vide = tout le digest)
    ├── include_unconfirmed  true                 (false = exclut « Non vérifié » et « Rumeur »)
    └── max_items         null                   (plafond par email)
```

## Fonctionnement d'un envoi

À la fin d'un run, si `email.enabled` vaut `true` :

1. `plan_deliveries` charge les abonnés et applique les limites de leur plan (`effective_preferences`).
2. Les abonnés aux préférences identiques sont regroupés : **un seul rendu par jeu de préférences**, quel que soit le nombre d'abonnés.
3. Pour chaque groupe, `select_items` filtre le digest du jour (déjà trié par score) : catégories, sources, importance, fiabilité, plafond.
4. Le digest est rendu dans la langue du groupe et envoyé avec un sujet localisé.

Un abonné ne reçoit que sa langue. Les abonnés `weekly` sont signalés comme non servis, sans erreur.

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

Voir la [roadmap](roadmap.md) : envoi hebdomadaire, gestion des préférences par lien, double opt-in, fournisseur d'emailing transactionnel, base de données.
