# claude-tooling

Vue d'ensemble des outils Claude installés pour `{{label}}` : slash
commands, sous-agents, hooks, settings. La référence détaillée vit
dans `.claude/{commands,agents,hooks}/` et dans les conventions
correspondantes.

## Sous-agents installés

| Agent | Rôle | Coût typique |
|---|---|---|
| `{{name}}-expert` | Feature M+, design, refactor, bug fix | ~250-300K tokens |
| `{{name}}-impl-validator` | Validation 5 axes, verdict GO / NO-GO | ~30-50K tokens |
| `{{name}}-pitfall-auditor` | Audit profond des pitfalls projet | ~20-40K tokens |

(À étendre/ajuster pour le projet.)

## Slash commands installés

Voir `conventions/commands.md` (à créer pour le projet) pour la table
détaillée. Génériques fournis par le template : `/pipeline`,
`/brainstorm`, `/self-review`, `/diff-review`, `/feature-start`,
`/readme-sync`, `/check-all`, `/digest-week`.

## Hooks installés

Voir `conventions/hooks.md` (à créer pour le projet). Génériques, en
Python stdlib (portables, câblés via
`python "${CLAUDE_PROJECT_DIR}/.claude/hooks/X.py"`) :
`em-dash-precommit.py`, `co-authored-by-precommit.py`,
`improvements-validate.py`, `protect-local-files.py`,
`remind-check-all.py`, `statusline.py`.

## Settings

`.claude/settings.json` : permissions (allow/deny), wiring hooks,
statusline. Versionné, partagé à toute l'équipe.
`.claude/settings.local.json` : gitignored, per-user (mode équipe vs
solo via `validate_author`).
