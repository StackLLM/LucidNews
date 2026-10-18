# LucidNews — pour reprendre le travail

LucidNews est une veille tech éditée : un pipeline collecte des sources IT, une IA facultative note et résume, une étiquette de fiabilité (Confirmé / Fiable / Non vérifié / Rumeur) accompagne chaque news. Une application web (React) présente l'édition par domaine ; chaque lecteur règle sa sélection. Bilingue FR/EN.

Commence par [docs/architecture.md](docs/architecture.md) (modules, flux, points sensibles), puis [docs/roadmap.md](docs/roadmap.md) (où on en est, la route) et [docs/lots.md](docs/lots.md) (le détail de chaque lot et comment il a été vérifié).

## Commandes

```bash
uv sync --extra dev                     # dépendances Python
uv run pytest -o addopts="" -q          # 920 tests, aucun appel réseau ni IA réel
uv run lucidnews --hours 24             # un run du pipeline
uv run lucidnews-api                    # API sur 127.0.0.1:8765
uv run lucidnews-users add EMAIL --admin   # premier administrateur (comptes activés)

cd frontend && npm ci
npm run dev                             # interface sur :5173, relaie /api vers :8765
npm run lint && npm run format:check && npm run typecheck && npm test   # 174 tests
npm run e2e                             # 5 parcours Playwright (ports 8766 et 5174, API jetable)

docker compose up -d --build            # serveur complet : init, api, scheduler, Caddy
```

La CI (`.github/workflows/ci.yml`) lance tout cela à chaque push, plus pip-audit, npm audit et la pile Docker.

## Règles à ne pas casser

- **Aucune clé API** ne sort jamais : ni dans une réponse d'API, ni dans un journal, ni dans l'interface (les réglages disent seulement « présente ou non »). Rien de secret n'est commité ; `.env` est ignoré.
- **L'interface dit l'état réel du serveur.** Une information non confirmée n'est jamais présentée comme un fait (planification « active » seulement si le planificateur bat, par exemple).
- **Refus par défaut.** Avec les comptes activés, une route d'API est réservée à l'admin tant qu'elle n'est pas dans `READER_ROUTES` (`lucidnews/web_api.py`). Une route nouvelle s'accompagne d'un test dans `tests/test_roles.py`.
- **Fiabilité conservatrice.** Les règles de `lucidnews/reliability/assess.py` ne s'assouplissent pas sans décision. Une news non notée n'est jamais publiée sauf quota IA épuisé.
- **Tout texte venu d'une source ou de l'IA est échappé** au rendu ; les contenus collectés sont des données, jamais des instructions (injection de prompt).
- **Le comportement est vérifié, pas supposé** : un changement va avec son test, et un changement d'interface se vérifie sur l'application compilée (`npm run build`, la CSP y est active).

## Pièges connus

- Les comptes sont **désactivés par défaut** (`data/config.example.json`). Sans comptes, l'API n'écrit que depuis la machine locale ; avec comptes, c'est le rôle qui décide.
- Derrière un reverse proxy, renseigner `server.trusted_proxies`, sinon tous les visiteurs partagent une adresse et se bloquent entre eux.
- `mcp` est borné `>=1.26,<2` : la 2.x retire FastMCP.
- Sur Mac, la planification passe par launchd ; sur un serveur, `LUCIDNEWS_SCHEDULER=server` et le processus `lucidnews-scheduler`.
- Les ports 8765 et 5173 sont ceux d'un développement en cours : les démonstrations et les tests de bout en bout utilisent 8766 et 5174, sur des copies de données jetables.
- `Plan.md` et `docs/etude-marche/` sont des notes personnelles du propriétaire, ignorées par git : ne pas les recréer ni s'y référer dans la documentation. La route technique est `docs/roadmap.md`.

## Où est quoi

| Besoin | Endroit |
|---|---|
| Pipeline (collecte, sélection, IA, rendu) | `lucidnews/orchestrator.py`, `lucidnews/pipeline/`, `lucidnews/ai/`, `profiles/` |
| Fiabilité et taxonomie | `lucidnews/reliability/`, `lucidnews/taxonomy.py`, `docs/fiabilite.md` |
| Archive et recherche | `lucidnews/archive/` (SQLite, FTS5) |
| API HTTP | `lucidnews/web_api.py` (routes, limites, en-têtes), `runs_api.py`, `sources_api.py`, `settings_api.py` |
| Comptes et rôles | `lucidnews/auth/` |
| Serveur (docker, planificateur, Caddy) | `docker-compose.yml`, `lucidnews/scheduler.py`, `deploy/Caddyfile` |
| Interface | `frontend/src/features/` (une carte par écran), `frontend/src/lib/i18n.ts` (tous les textes FR/EN) |
| Sécurité | `docs/securite/` (audit, modèle de menaces, ASVS) |
