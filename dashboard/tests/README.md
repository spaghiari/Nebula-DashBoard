# Tests automatisés (`unittest`, stdlib)

Aucune dépendance : `unittest` + bibliothèque standard. Tout tourne en **bac à
sable** (dossier temporaire, `ATELIER_ROOT` / `USERPROFILE` / `HOME` redirigés
avant l'import de `dashcore`) : aucun test ne lit ni n'écrit les vraies données
du poste. Windows et Linux ; ce qui est propre à Windows est ignoré ailleurs
avec un motif explicite.

## Lancer

```sh
# depuis la racine du dépôt
python -m unittest discover -s dashboard/tests
# depuis dashboard/
python -m unittest discover -s tests
# un seul module / plus de détail
python -m unittest discover -s dashboard/tests -p "test_mcps.py" -v
# tests navigateur facultatifs (Edge/Chrome headless)
NEBULA_UI_TESTS=1 python -m unittest discover -s dashboard/tests
```

Durée : quelques secondes (serveurs HTTP et dépôts git temporaires inclus).

## Fichiers

| Fichier | Couvre |
|---|---|
| `_support.py` | Bac à sable commun (à importer avant `dashcore`), `reset_sandbox()`, `ServerProcess` (serveur réel en sous-process, port libre, arrêt par handle) |
| `test_helpers_json.py` | `read_json_strict` / `CorruptJsonError`, `write_json` atomique, `.bak` non tourné sur fichier corrompu, BOM `utf-8-sig` |
| `test_env_local.py` | Coffre `.env.local(.enc)` illisible -> refus d'écriture (409), invisibles retirés ; round-trip DPAPI (Windows) |
| `test_workspace_io.py` | `project_dir_for_path` (tout `[^A-Za-z0-9]` -> `-`), cache des stats (ajout de ligne, nouveau fichier, suppression, purge), `overlays_active` de `/api/overview` |
| `test_plugins.py` | `uninstall_plugin` : ids refusés, correspondance exacte, entrées réservées, confinement des liens, `settings.json` corrompu |
| `test_workspaces.py` | Garde de purge `delete_workspace`, create/duplicate : 409, rollback, registre corrompu sans orphelin |
| `test_mcps.py` | Sync `.mcp.json` non destructive (serveurs étrangers préservés, fichier illisible -> 409), refus des valeurs masquées |
| `test_skills_library.py` | `list_library`, distribution / désynchronisation, cache de `_hash_dir` (hash identique à l'algorithme de référence, invalidation par mtime_ns + taille, aucune relecture sur cache valide) |
| `test_overlays.py` | `list_overlays` / `apply_overlay` : exclusion `__pycache__` / `.pyc` (`_is_junk`), idempotence, fragment CLAUDE.md, profondeur, mode-gating, hook référencé absent ; `requires` (409 sans écriture, ordre `order_by_requires`), `settings_patch` (fusion par matcher sans doublon, idempotente, création si absent, corrompu -> 409, groupe sans `matcher` type UserPromptSubmit fusionné sous la clé vide), mode du prérequis préservé, `overlays_usage` ; copie de l'overlay réel |
| `test_team.py` | Module claude-team (`api_team`) : agents générés (outils dérivés des capacités, read_only, modèle par défaut / overrides, marqueur généré, non-écrasement, `regenerate`), préfixe (défaut, override, persistance `team.prefix`, relecture à la régénération, manifeste corrompu), `team_config_hash` (stable, change si un corps / agent change, égal au one-liner de `/eval` exécuté en sous-process), `team_state`, `improvement_state` (journal vide, lignes invalides, stats, `baseline_current` vrai / faux / inexécutables, compteurs des registres) ; hook `evals-lock.py` en sous-process (refus sous `.claude/evals/`, autorisé ailleurs, `evals_unlocked`) ; scénario réel self-improving + claude-team (7 agents, settings.json fusionné, ré-application sans changement, `prefix: dash` puis régénération, 409 sans prérequis, création de workspace ordonnée) ; cohérence du jeu de démarrage livré (JSON valide, `agent` du manifeste, `grader` / `target` valides, regex compilables, `scope` sur `diff`) ; routage always-on : description générée avec déclencheurs (`auto` true / false / absent), `team_state.routing`, `set_routing` (valide, 400, 409, section absente écrite par défaut, pas d'écriture si inchangé), hook `team-router.py` en sous-process (classification des 4 types + inconnu, modes auto / assiste / manuel, slash command, UTF-8, `team.json` absent), jeu réel (5 descriptions « À utiliser automatiquement », critic / evaluator « Jamais », hook UserPromptSubmit câblé une fois) |
| `test_mcp_probe.py` | Verdict mémorisé de « Diagnostiquer » : signature de config (champs techniques seuls, normalisation aller-retour d'édition), écriture atomique dans `DATA_DIR`, élagage, fichier corrompu, fenêtre de 7 jours, `last_probe` exposé sans être persisté dans le registre |
| `test_plugin_updates.py` | Plugins « à jour » : comparaison de versions, révision / contenu vs clone local du marketplace, sources distantes (épinglée, branche, version non vérifiable), confinement des sources relatives, rafraîchissement CLI (échec -> HTTP 502, verrou 409) |
| `test_mcp_recipes.py` | Catalogue livré cohérent (ids, transport, `${KEY}` déclarés), recettes locales CRUD + validation, fichier corrompu jamais écrasé |
| `test_files.py` | Explorateur : `.env*` / `.mcp.json` créables avec contenu réel, écrasement refusé (403) |
| `test_data_migration.py` | Migration vers `NEBULA_DATA_DIR` : copie sans écrasement, source intacte, marqueur, `--migrate-data` ; démarrage serveur réel |
| `test_active_sessions.py` | Purge des PID morts / recyclés, états `running` / `idle` |
| `test_system_update.py` | Stash nommé et vérifié, jamais de pop du stash utilisateur ; bascule auto de `origin` GitLab -> Forgejo (variantes d'URL, fork intouché, idempotence) (dépôts git temporaires ; ignoré sans git) |
| `test_server_http.py` | Serveur réel : Host étranger 403, Origin étrangère 403, corps non-objet 400, liste blanche statique, export refusé en GET, hôte configuré, `/api/overlays` avec `usage`, routes `team` / `improvement`, `POST .../team/routing` (XHR requis, 404 sans manifeste, section par défaut puis mode, 400 invalide), `team_routing` de `/api/overview` |
| `test_config.py` | Variables `NEBULA_*`, hôtes autorisés, garde-fous des fonctions Windows-only |
| `ui/cdp.py` | Client CDP minimal (WebSocket stdlib) |
| `ui/test_ui_smoke.py` | Front headless (facultatif : `NEBULA_UI_TESTS=1` + navigateur trouvé, sinon ignoré) : accueil + requête agrégée, erreur réseau, rendu de chaque route sans erreur ni 5xx, aucune exception JS |

## Règle

Tout correctif de bug ajoute (ou étend) un test qui échoue sans le correctif.
