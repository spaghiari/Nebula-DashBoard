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
