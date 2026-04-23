# Workspace — {{label}}

## Contexte
{{description}}

## Structure
- `configs/`     — fichiers YAML (organisés par domaine)
- `secrets.yaml` — **ne jamais committer**, référencé via `!secret`
- `notes.md`     — journal

## Tâches fréquentes
1. Ajouter/modifier une config
2. Valider la syntaxe YAML (indentation, anchors, tags)
3. Déboguer un chargement qui échoue (logs)
4. Refactoriser une config longue en sous-fichiers (includes/imports)
5. Générer un diff de config lisible

## Conventions
- Indentation : 2 espaces, jamais de tabs
- Clés en snake_case
- Chaque bloc significatif commenté (`# description`)
- Secrets via `!secret <nom>` ou `${VAR}` selon l'outil
- Toujours valider avant d'appliquer (`check config` / `kubectl apply --dry-run=client`)
