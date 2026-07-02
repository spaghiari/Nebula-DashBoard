# {{label}}

`{{name}}` — {{description}}

Workspace de gestion de configurations YAML (Home Assistant, k8s, compose,
Ansible…).

- `CLAUDE.md` — conventions (indentation 2 espaces, snake_case, secrets via
  `!secret` ou `${VAR}`, validation avant application).
- `configs/` — fichiers YAML organisés par domaine.
- `secrets.yaml` — **jamais committé** (gitignored).
