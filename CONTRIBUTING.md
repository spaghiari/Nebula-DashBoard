# Contribuer à Nebula

Merci de l'intérêt ! Nebula est un tableau de bord local pour Claude Code,
écrit en **Python stdlib uniquement** (aucune dépendance externe) avec un
frontend en JavaScript vanilla.

## Démarrer

```bash
cd dashboard
python server.py          # http://127.0.0.1:4777/
python -m unittest discover -s tests
```

Python 3.10 minimum. Les tests tournent en CI sous Windows (3.10 et 3.14),
détail dans [`.github/CI.md`](.github/CI.md).

## Règles du projet

- **Stdlib uniquement** : toute PR qui ajoute une dépendance sera refusée.
- **Constantes partagées** dans `dashboard/dashcore/config.py`.
- **Suppression de dossiers** : `_remove_dir_or_link()` (`helpers.py`) et
  jamais `shutil.rmtree` directement (plante sur les symlinks Windows).
- **Aucune donnée personnelle** dans le dépôt : pas de `registry.json`
  rempli, de `workspaces.json` rempli, de jeton ni de chemin local.
- **Langue** : français pour le code commenté, la doc et les commits.
- Ajoute ou adapte un test pour tout comportement modifié.

## Proposer un changement

1. Ouvre d'abord une *issue* pour les changements non triviaux.
2. Fork, branche dédiée, commits au format `type(scope): message` avec
   `type` parmi `feature`, `fix`, `update`, `doc`.
3. Vérifie que `python -m unittest discover -s tests` passe.
4. Ouvre la PR en décrivant le problème résolu et comment le vérifier.

## Sécurité

Ne signale pas une faille dans une issue publique : voir
[`SECURITY.md`](SECURITY.md).
