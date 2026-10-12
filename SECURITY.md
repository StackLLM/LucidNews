# Sécurité

## Signaler une vulnérabilité

Ne publiez pas de vulnérabilité dans une issue. Signalez-la en privé aux mainteneurs du dépôt, avec :

- la description du problème et son impact ;
- les étapes pour le reproduire ;
- la version ou le commit concerné.

## Secrets

- Les secrets vivent uniquement dans `.env` ou dans l'environnement d'exécution. `.env`, `data/config.json`, `data/subscribers.json`, les cookies et les fichiers de session sont dans `.gitignore`.
- `data/config.json` référence les secrets par **nom de variable** (`api_key_env`, `password_env`, `url_env`) ou par `${VAR}`, jamais par valeur.
- Le serveur MCP masque les valeurs développées depuis l'environnement dans la configuration qu'il expose.

## Contenu non fiable

Tout contenu collecté (titres, articles, commentaires, résultats de recherche) est traité comme des **données** : les prompts interdisent d'en suivre les instructions, et le rendu Markdown/HTML échappe tout texte et n'autorise que des liens `http(s)`. Les requêtes webhook passent par `lucidnews/url_security.py`.
