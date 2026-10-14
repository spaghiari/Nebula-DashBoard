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
| `test_active_sessions.py` | Purge des PID morts / recyclés, états `running` / `idle` |
| `test_system_update.py` | Stash nommé et vérifié, jamais de pop du stash utilisateur (dépôts git temporaires ; ignoré sans git) |
| `test_server_http.py` | Serveur réel : Host étranger 403, Origin étrangère 403, corps non-objet 400, liste blanche statique, export refusé en GET, hôte configuré |
| `test_config.py` | Variables `NEBULA_*`, hôtes autorisés, garde-fous des fonctions Windows-only |
| `ui/cdp.py` | Client CDP minimal (WebSocket stdlib) |
| `ui/test_ui_smoke.py` | Smoke test front headless (facultatif : `NEBULA_UI_TESTS=1` + navigateur trouvé, sinon ignoré) |
| `gitlab-ci.yml` | CI GitLab minimale, inactive par défaut (voir l'en-tête du fichier pour l'activer) |

## Règle

Tout correctif de bug ajoute (ou étend) un test qui échoue sans le correctif.
