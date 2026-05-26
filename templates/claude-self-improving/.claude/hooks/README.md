# Claude Code hooks - `{{label}}`

Filets de sécurité automatiques exécutés par le harness Claude Code
lors d'événements tool-use. Chaque hook lit un JSON sur stdin (cf.
doc Claude Code hooks), peut bloquer un appel via `exit 2`, ou laisser
passer via `exit 0`.

## Hooks fournis par le template

| Fichier | Event | Matcher | Rôle |
|---|---|---|---|
| `em-dash-precommit.sh` | PreToolUse | `Bash` | Si `git commit` → grep `—` dans le diff staged hors exceptions. Bloque si trouvé. Convention typographique ASCII-only. |
| `improvements-validate.sh` | PreToolUse | `Bash` | Si `git commit` → valide le format des registres `.claude/{improvements,backlog,ideas}.md` et `digests/*.md` staged (statut whitelist, P0/P1/P2, dates YYYY-MM-DD, champ `par <author>` en mode équipe). Bloque si format invalide. |
| `co-authored-by-precommit.sh` | PreToolUse | `Bash` | Si `git commit` → grep tolérant `co-?authored-?by[^a-z]+claude` (case-insensitive) sur le JSON brut stdin. Bloque si le message contient le trailer interdit. |
| `protect-local-files.sh` | PreToolUse | `Edit\|Write\|MultiEdit` | Refuse toute modification de `CLAUDE.local.md` ou `.claude/settings.local.json`. |
| `remind-check-all.sh` | Stop | - | À la fin d'un turn : si fichiers de code non-committés → rappel de lancer `/check-all`. À configurer selon la stack du projet. |
| `statusline.sh` | StatusLine | - | Provider de statusline Claude Code (infos contextuelles). |

## Hooks à ajouter par projet selon la stack

| Hook suggéré | Trigger | Rôle |
|---|---|---|
| `<langage>-lint-on-edit.sh` | PostToolUse `Edit\|Write\|MultiEdit` | Lint syntaxique automatique sur tout fichier du langage principal fraîchement modifié (ex: `php -l`, `node --check`, `go vet`, `cargo check`). Alerte si parse error. |
| `<convention>-precommit.sh` | PreToolUse `Bash` | Vérifications projet-spécifiques au commit (accents, longueur de ligne, conventions de nommage). |

## Prérequis runtime

- `bash` dans le PATH (Git Bash, WSL, ou MSYS sur Windows).
- `git` dans le PATH pour les hooks pre-commit Bash.
- Outils projet-spécifiques selon la stack (à documenter à
  l'instanciation).

## Désactiver un hook

Soit retirer son entrée dans `.claude/settings.json` section
`hooks`, soit renommer le `.sh` en `.sh.disabled`.

## Mode équipe / solo

Le hook `improvements-validate.sh` vérifie par défaut le champ `par
<author>` sur les items de registres (mode équipe). Pour désactiver
en mode solo :

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
    | bash .claude/hooks/improvements-validate.sh

# Test PreToolUse Edit
echo '{"tool_name":"Edit","tool_input":{"file_path":"src/<fichier>"}}' \
    | bash .claude/hooks/protect-local-files.sh
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
