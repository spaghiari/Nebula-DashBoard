# Templates de workspace

Chaque sous-dossier est un template. Le dashboard les découvre automatiquement.

## Structure minimale

    templates/mon-template/
      .template.json     ← métadonnées (obligatoire)
      CLAUDE.md          ← contenu initial du workspace
      ...                ← tout autre fichier/dossier à copier

## `.template.json`

```json
{
  "label": "Nom affiché",
  "description": "Courte description visible dans la modale",
  "emoji": "📦"
}
```

## Placeholders interpolés

Dans **tous les fichiers texte** (< 512 KB, extensions `.md`, `.txt`, `.json`,
`.yaml/.yml`, `.py`, `.js`, `.ts`, `.sh`, `.bat`, `.ps1`, `.html`, `.css`,
`.cfg`, `.ini`, `.toml`, `.gitignore`, `.env`) :

| Placeholder | Remplacé par |
|---|---|
| `{{name}}`        | ID du workspace |
| `{{label}}`       | Label |
| `{{description}}` | Description |
| `{{tools}}`       | Outils / stack |
| `{{date}}`        | Date du jour ISO (YYYY-MM-DD) |
| `{{emoji}}`       | Emoji choisi |

Les fichiers binaires sont copiés tels quels.

## Ajouter un template

1. Duplique un template existant : `cp -r templates/blank templates/mon-template`
2. Édite `.template.json` et le contenu.
3. Recharge le dashboard → il apparaît dans le sélecteur.

Pas de redémarrage du serveur nécessaire — la liste est lue à chaque ouverture
de la modale.

## Templates fournis

- **blank** — minimal
- **dev-python** — projet Python avec src/, tests/, venv
- **dev-node** — projet Node.js ESM
- **audit** — audit sécurité (checklists, rapports datés)
- **automation** — workflows / scripts d'automatisation
- **config-yaml** — configs YAML (HA, k8s, compose…)

## Overlays (modules)

Un **overlay** vit aussi dans `templates/<id>/`, mais porte un marker
`.nebula-overlay.json` (a la place de `.template.json`). Il ne cree pas un
workspace : il se pose **par-dessus** un template deja applique, a la
creation (cases « Modules optionnels ») ou plus tard (onglet Configuration
du workspace, page Templates § Modules). Idempotent : ne copie que les
fichiers absents, n'ecrase jamais un fichier existant. Logique dans
`dashboard/dashcore/api_overlays.py`.

### `.nebula-overlay.json`

| Cle | Role |
|---|---|
| `id`, `label`, `description`, `emoji` | Identite (comme un template) |
| `signature_file` | Fichier dont la presence dans le workspace = overlay actif (ex. `.claude/improvements.md`, `.claude/team.json`) |
| `requires` | Ids d'overlays qui doivent deja etre actifs. Activation refusee (409) sinon ; a la creation, l'ordre d'application suit les dependances et un overlay dont le prerequis n'est pas coche est refuse avec un message |
| `features` | Liste `{icon, title, text}` rendue par l'UI (icone = cle de `js/icons.js`, `text` accepte `<code>`) |
| `after_apply` | Phrase affichee sous les features (« Apres activation : ... ») |
| `claude_md` | Traitement special de `CLAUDE.md` : fichier complet si absent, sinon fragment appende entre `begin_marker` / `end_marker` (idempotent) |
| `mode_gated`, `depth`, `seeds` | Options de bootstrap (mode projet, profondeur d'install, exemples). Leur presence fait apparaitre les champs mode / langue / profondeur dans la modale |
| `settings_patch` | Fragment fusionne dans `.claude/settings.json` du workspace : dicts fusionnes recursivement, listes de hooks fusionnees par `matcher` sans doublon de `command`, scalaires existants jamais ecrases. Cree le fichier s'il est absent. Les hooks references doivent etre livres par l'overlay (garde `_missing_hook_refs`) |
| `no_copy` | Chemins (relatifs a l'overlay) qui documentent le module dans ce catalogue mais ne sont jamais copies dans un workspace ni comptes dans `file_count` (ex. `README.md` de `claude-team`). Absence de la cle = aucun filtre |
| `generators` | Hooks de post-application : `team_agents` genere `.claude/agents/<prefix>-<id>.md` depuis `.claude/team.json` (`dashcore/api_team.py`). Payload d'activation : `prefix` (safe_id, defaut = id du workspace, persiste dans `team.prefix`), `models`, `default_model`, `regenerate`. L'entree du module dans `GET /api/workspaces/<id>/overlays` porte aussi `routing` (mode / gate de relecture du routage always-on, lu dans `team.json`), modifiable par `POST /api/workspaces/<id>/team/routing` (`{"mode": "manuel\|assiste\|auto", "review_gate": "always\|from_3_files\|never"}`) sans regeneration |

Les groupes de hooks sans `matcher` (UserPromptSubmit, Stop...) fusionnent
sous la cle vide : `matcher` absent, `null` ou `""` designent le meme
groupe (aucun doublon a la re-application).

### Overlays fournis

- **claude-self-improving** - memoire structuree, registres, conventions,
  agents / commandes / hooks pre-commit (`claude-self-improving/README.md`).
- **claude-team** - equipe de 7 agents generes depuis un manifeste
  (prefixe choisi a l'activation) + routage always-on (le fil principal
  route question / conception / tache S / relecture vers les agents sans
  appel explicite, modes `manuel` / `assiste` / `auto`, hook
  `team-router.py`) + `/team` (orchestration complete par le fil
  principal) + boucle d'amelioration mesuree (evals verrouillees, `/eval`,
  `/improve`, `/eval-add`, empreinte de configuration). Requiert
  `claude-self-improving` (`claude-team/README.md`).
