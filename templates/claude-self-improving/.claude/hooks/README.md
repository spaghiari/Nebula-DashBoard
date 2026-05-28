# Claude Code hooks - `{{label}}`

Filets de sécurité automatiques exécutés par le harness Claude Code
lors d'événements tool-use. Chaque hook lit un JSON sur stdin (cf.
doc Claude Code hooks), peut bloquer un appel via `exit 2`, ou laisser
passer via `exit 0`.

Les hooks sont écrits en **Python stdlib** : portables Windows/Unix
sans dépendance à `bash`. Ils sont câblés dans `.claude/settings.json`
via `python "${CLAUDE_PROJECT_DIR}/.claude/hooks/X.py"` — chemin
**absolu** via `${CLAUDE_PROJECT_DIR}`, jamais relatif (le shell
dérive sur un `cd` et casserait les hooks).

## Hooks fournis par l'overlay

| Fichier | Event | Matcher | Rôle |
|---|---|---|---|
| `em-dash-precommit.py` | PreToolUse | `Bash` | Si `git commit` → cherche `—` dans le diff staged hors exceptions. Bloque si trouvé. Convention typographique ASCII-only. |
| `improvements-validate.py` | PreToolUse | `Bash` | Si `git commit` → valide le format des registres `.claude/{improvements,backlog,ideas}.md` et `digests/*.md` staged (statut whitelist, P0/P1/P2, dates YYYY-MM-DD, champ `par <author>` en mode équipe). Bloque si format invalide. |
| `co-authored-by-precommit.py` | PreToolUse | `Bash` | Si `git commit` → recherche tolérante `co-?authored-?by[^a-z]+claude` (case-insensitive) sur le JSON brut stdin. Bloque si le message contient le trailer interdit. |
| `protect-local-files.py` | PreToolUse | `Edit\|Write\|MultiEdit` | Refuse toute modification de `CLAUDE.local.md` ou `.claude/settings.local.json`. |
| `remind-check-all.py` | Stop | - | À la fin d'un turn : si fichiers de code non-committés → rappel de lancer `/check-all`. À configurer selon la stack du projet (`WATCHED_DIRS`). |
| `statusline.py` | StatusLine | - | Provider de statusline Claude Code (infos contextuelles). |

## Hooks à ajouter par projet selon la stack

| Hook suggéré | Trigger | Rôle |
|---|---|---|
| `<langage>-lint-on-edit.sh` | PostToolUse `Edit\|Write\|MultiEdit` | Lint syntaxique automatique sur tout fichier du langage principal fraîchement modifié (ex: `php -l`, `node --check`, `go vet`, `cargo check`). Alerte si parse error. |
| `<convention>-precommit.sh` | PreToolUse `Bash` | Vérifications projet-spécifiques au commit (accents, longueur de ligne, conventions de nommage). |

## Prérequis runtime

- **`python`** dans le PATH (Python 3.8+). C'est le seul prérequis :
  les 6 hooks sont en stdlib pure. Sur le poste hôte, `python` est
  déjà requis pour faire tourner Nebula.
- `git` dans le PATH pour les hooks pre-commit (em-dash,
  improvements-validate, co-authored-by, remind-check-all, statusline).
- Outils projet-spécifiques selon la stack (à documenter à
  l'instanciation).

> Note : les hooks utilisent l'invocation `python` (et non `python3`),
> cohérente avec le poste hôte Windows. Sur un hôte Unix où seul
> `python3` existe, adapter les commandes dans `.claude/settings.json`.

## Désactiver un hook

Soit retirer son entrée dans `.claude/settings.json` section
`hooks`, soit renommer le `.py` en `.py.disabled`.

## Mode équipe / solo

Le hook `improvements-validate.py` vérifie par défaut le champ `par
<author>` sur les items de registres (mode équipe). En mode solo,
l'overlay pose automatiquement `validate_author: false` dans
`.claude/settings.local.json`. Pour le faire manuellement :

```json
// .claude/settings.local.json
{
  "validate_author": false
}
```

Cf. [`memory/overview.md § Mode projet`](../memory/overview.md) pour
le choix de mode.

## Tester un hook manuellement

```bash
# Test PreToolUse Bash (par exemple le validator)
echo '{"tool_name":"Bash","tool_input":{"command":"git commit -m test"}}' \
    | python .claude/hooks/improvements-validate.py

# Test PreToolUse Edit
echo '{"tool_name":"Edit","tool_input":{"file_path":"src/<fichier>"}}' \
    | python .claude/hooks/protect-local-files.py
```

Si `exit 2` → le hook bloque. Si stdout contient un message → il
sera renvoyé à Claude.

## Format stdin attendu par event

| Event | Champs lus |
|---|---|
| PreToolUse Edit/Write | `tool_input.file_path` |
| PreToolUse Bash | `tool_input.command` |
| PostToolUse Edit/Write | `tool_input.file_path`, `tool_response` |
| Stop | (rien de critique, lit `cwd` éventuellement) |
