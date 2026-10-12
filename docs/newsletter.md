# Newsletter

Le module `lucidnews/newsletter/` pose les fondations d'une plateforme de newsletter tech : abonnés, préférences, plans, sélection personnalisée, plan d'envoi, double confirmation et journal des envois. Les abonnés arrivent par l'écran Préférences, par e-mail (IMAP) ou via le code, et **ne reçoivent rien avant d'avoir confirmé**.

## Modèle

```
Subscriber
├── email
├── plan                 free | premium          (aucun paiement, aucune restriction aujourd'hui)
├── created_at
├── status               pending | confirmed | unsubscribed
├── confirmed_at / unsubscribed_at
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

`lucidnews/newsletter/render.py` convertit le Markdown du digest en e-mail HTML et texte. Le texte des sources est déjà échappé par le générateur de digest ; tout `<` restant devient littéral. Aucun script, aucune image distante, aucun formulaire.

## Plans Free / Premium

`lucidnews/newsletter/plans.py` contient `PLAN_LIMITS` : nombre maximal de catégories, de sources, d'items, fréquences autorisées. **Les deux plans sont illimités aujourd'hui.** Le jour où l'offre Premium existera, il suffira de modifier cette table : le code d'envoi applique déjà les limites. Il n'y a ni paiement ni paywall.

## Stockage

`data/newsletter.sqlite3` (ignoré par git) : tables `subscribers` et `deliveries`. Il remplace `data/subscribers.json`.

- **Migration** : à la première ouverture, si la base est vide et que `subscribers.json` existe, ses lecteurs sont importés **comme confirmés** (ils recevaient déjà le digest et aucune preuve de consentement n'existe pour leur redemander ; envoyer des mails de confirmation à tous automatiquement serait un envoi non demandé). Le fichier est renommé `subscribers.json.migrated`, jamais supprimé. La migration n'est faite qu'une fois.
- **Supprimer** un lecteur (bouton Supprimer) efface tout : sa ligne et son journal d'envois.
- **Se désinscrire** (lien) garde seulement l'adresse, avec le statut « désinscrit », pour ne plus jamais lui écrire. Seule une nouvelle demande (« Envoyer le lien de confirmation ») le remet en attente.
- L'ancien `SubscriberStore` (fichier JSON) ne sert plus qu'à la migration.

## Double confirmation (double opt-in)

1. Un lecteur ajouté (écran Préférences ou e-mail `SUBSCRIBE`) est **en attente** et reçoit un lien de confirmation. Rien d'autre ne lui est envoyé.
2. Le lien ouvre une page avec un bouton. Ouvrir le lien ne change rien (les antivirus et aperçus de liens ouvrent les liens) ; le bouton confirme.
3. Le digest ne part qu'aux lecteurs **confirmés** : le plan d'envoi les filtre, et l'envoi revérifie chaque adresse dans la base.

## Liens signés

Chaque lien est un jeton signé (HMAC-SHA256) avec un secret que seul l'expéditeur connaît (`NEWSLETTER_SIGNING_KEY`, au moins 16 caractères, dans `.env`). Rien n'est stocké : un lien modifié, expiré, ou fait pour une autre action est refusé.

- Confirmation : valable 7 jours.
- Désinscription : n'expire jamais (partir doit rester possible).
- Chaque e-mail contient le lien de désinscription **de son lecteur** et les en-têtes `List-Unsubscribe` et `List-Unsubscribe-Post` (désinscription en un clic des clients mail).

## Service public

`uv run lucidnews-public` (port 8780) est un processus **séparé** de `lucidnews-api`, qui reste sur localhost. Il ne sert que `GET /confirm`, `GET /unsubscribe` (une page avec un bouton, rien n'est modifié), `POST /confirm`, `POST /unsubscribe` (aussi le clic unique des clients mail) et `GET /health`. Ni archive, ni liste d'abonnés, ni réglages. Il n'écrit jamais le jeton dans ses journaux.

Il lit et écrit la **même** `newsletter.sqlite3` que le pipeline : il doit tourner là où est le dossier `data/`. Mettez-le derrière un proxy HTTPS (Caddy, nginx) ou un tunnel (Cloudflare Tunnel) ; `email.public_base_url` est l'adresse publique de ce proxy, en `https`.

## Fournisseur d'envoi

`email.provider` :

- `smtp` (défaut) : le serveur SMTP configuré, une connexion par message.
- `resend` : l'API HTTPS de Resend (`RESEND_API_KEY`, nom réglable par `email.resend_api_key_env`). Avec Resend, un digest sans lien de désinscription est refusé.

Les clés se gèrent dans Réglages › Clés API (jamais réaffichées). Le message d'erreur d'un envoi raté ne contient jamais la clé.

## Journal des envois

Chaque envoi, réussi ou raté, est écrit dans `deliveries` : lecteur, date, type (confirmation, quotidien, hebdomadaire), objet, édition (ou semaine) et résultat avec l'erreur. Préférences › Journal des envois : celui du lecteur choisi, ou de tous quand personne n'est choisi. Un envoi hebdomadaire entièrement raté laisse la semaine « à envoyer » : le run suivant du même jour réessaie.

## Inscription par email

Avec `email.imap_enabled`, la boîte configurée est relevée à chaque run :

- un email dont le sujet vaut `SUBSCRIBE` crée un lecteur **en attente** et lui envoie le lien de confirmation (un lecteur désinscrit qui redemande repasse en attente) ;
- un email dont le sujet vaut `UNSUBSCRIBE` le désinscrit (statut « désinscrit »).

## Ajouter un abonné depuis le code

```python
from lucidnews.newsletter import DigestPreferences

from lucidnews.newsletter.db import SubscriberDB

db = SubscriberDB("data/newsletter.sqlite3")
db.add("lecteur@example.com", DigestPreferences(language="fr", categories=["ai", "cybersecurity"], min_importance="high"))  # confirmé d'office : à réserver à vos propres adresses
```

## Prochaines étapes

Voir la [roadmap](roadmap.md) : gestion des préférences par lien, envoi selon le fuseau horaire du lecteur.
