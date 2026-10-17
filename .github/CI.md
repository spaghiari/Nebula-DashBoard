# CI de Nebula

Workflow : `.github/workflows/ci.yml`. Déclencheurs : push sur `main`, tags,
pull requests, lancement manuel, et chaque lundi (nouvelles règles des outils
de sécurité ; le job `tests` n'y tourne pas, Windows coûte plus de minutes).

| Job | Système | Contenu |
|---|---|---|
| `tests` | Windows, Python 3.10 (minimum) et 3.14 | `python -m unittest discover -s tests` dans `dashboard/` |
| `audit` | Ubuntu | `.github/scripts/audit.py` : contrôles maison |
| `securite` | Ubuntu | bandit, semgrep, gitleaks, garde-fou sur les fichiers de dépendances |

`audit.py` (stdlib, fichiers suivis par git uniquement) vérifie : tiret long
dans la section de tête du CHANGELOG (les anciens dans `dashboard/` ne sont
que signalés), références internes, fichiers de données personnelles suivis,
`__version__` égal à la première version du CHANGELOG, `import server`,
`node --check` des `.js` (ignoré sans `node`).

Actions épinglées par SHA de commit (version en commentaire) ; outils de
sécurité à version figée. Pour mettre à jour : changer la version, relire les
nouveaux résultats.

## Lancer en local

```
# depuis la racine du dépôt
python .github/scripts/audit.py                 # ou : ... audit.py <racine>
cd dashboard && python -m unittest discover -s tests
pip install bandit==1.9.4
bandit -r dashboard -x dashboard/tests -ll
```

Semgrep et gitleaks : voir les commandes dans `ci.yml` (semgrep est
pénible à installer sous Windows ; la CI suffit).
