---
description: Crée une nouvelle branche `feature/{{name}}` à partir de `main` pour engager une feature M+ (effort >= 3 h équivalent humain). Vérifie le working tree propre + branche courante = main, valide le slug kebab-case, exécute `git checkout -b feature/{{name}}`. Recommandé pour features L+, recommandé mais pas obligatoire pour features M+. Cf. `conventions/git.md` § « Branches feature ».
argument-hint: {{name}}
---

Crée une branche feature `feature/{{name}}` à partir de `main` pour
engager une nouvelle feature M+. Recommandé pour les features
nécessitant un point de retour propre (rollback facile en cas de
régression observée post-livraison) ou une review propre via
MR/PR.

**Argument** : `{{name}}` (obligatoire). Identifiant kebab-case court
décrivant la feature (lettres minuscules, chiffres, tirets
uniquement). Exemples : `dropdown-tp-hybride`, `release-publish`,
`bulk-groups-api`.

**Quand l'utiliser** :

- Feature L+ (effort estimé >= 7 h équivalent humain) : **recommandé**
  fortement (point de retour propre obligatoire pour minimiser le
  risque de régression difficilement diagnosticable post-merge).
- Feature M+ (effort estimé 3-7 h) : **recommandé** si la feature
  touche le module produit. Optionnel pour les changements doc /
  outillage Claude purs.
- Feature S- (< 3 h) ou changements doc seuls : **non recommandé**.
  Commit direct sur `main` est plus efficace.

Cohérent avec la convention `effort-sizing.md` § « Catégories
d'effort » qui définit les seuils XXS / XS / S / M / M+ / L / XL.

## Méthode

### Étape 1 - Pré-vol

1. Valider `$1` :
   - Format kebab-case strict : `^[a-z0-9-]+$` (lettres minuscules,
     chiffres, tirets uniquement, pas de tiret en début/fin)
   - Longueur 3 à 50 caractères
   - Sinon : afficher l'erreur explicite + exemples valides,
     arrêter ici.

2. Vérifier la branche courante :
   ```bash
   current_branch="$(git rev-parse --abbrev-ref HEAD)"
   if [ "$current_branch" != "main" ]; then
       echo "Erreur : branche courante = $current_branch (attendu : main)."
       echo "  Repasser sur main : git checkout main"
       echo "  Ou pull les changements en cours avant de créer une"
       echo "  nouvelle branche feature."
       exit 1
   fi
   ```

3. Vérifier que `main` est à jour avec `origin/main` :
   ```bash
   git fetch origin main 2>/dev/null
   ahead_behind="$(git rev-list --left-right --count main...origin/main 2>/dev/null)"
   ahead="$(printf '%s' "$ahead_behind" | awk '{print $1+0}')"
   behind="$(printf '%s' "$ahead_behind" | awk '{print $2+0}')"
   if [ "$behind" -gt 0 ]; then
       echo "Erreur : main est en retard de $behind commit(s) sur origin."
       echo "  Pull avant : git pull origin main"
       exit 1
   fi
   ```
   Si la branche locale est en avance (ahead > 0) c'est OK -
   l'utilisateur a juste des commits locaux non pushés, la nouvelle
   branche partira de là.

4. Vérifier le working tree propre :
   ```bash
   if [ -n "$(git status --porcelain)" ]; then
       echo "Erreur : working tree dirty. Commiter ou stasher avant."
       echo "  git stash"
       echo "  ou commit les changements en cours sur main."
       exit 1
   fi
   ```

5. Vérifier que la branche `feature/$1` n'existe pas déjà
   (locale ou remote) :
   ```bash
   if git rev-parse --verify "feature/$1" >/dev/null 2>&1; then
       echo "Erreur : branche feature/$1 existe déjà localement."
       echo "  git branch --list 'feature/*'"
       exit 1
   fi
   if git ls-remote --exit-code --heads origin "feature/$1" >/dev/null 2>&1; then
       echo "Erreur : branche feature/$1 existe déjà sur origin."
       echo "  git fetch origin feature/$1 && git checkout feature/$1"
       exit 1
   fi
   ```

### Étape 2 - Création de la branche

```bash
git checkout -b "feature/$1"
```

Affiche le récap :

```
Branche feature/{{name}} créée à partir de main (HEAD <SHA>).
Tu es maintenant sur feature/{{name}}.

Workflow recommandé :
  1. Travailler la feature (commits sur cette branche)
  2. git push -u origin feature/{{name}}  (créer la branche sur origin)
  3. À la livraison :
     git checkout main
     git pull origin main
     git merge --no-ff feature/{{name}}  (merge avec commit explicite)
     git push origin main
     git branch -d feature/{{name}}      (clean local)
     git push origin :feature/{{name}}   (clean remote)
  4. Si besoin de release : /release-prep X.Y.Z (sur main post-merge)

Convention de merge : --no-ff (commit de merge explicite, préserve
la trace de la branche dans l'historique). Cf.
`conventions/git.md § Branches feature`.
```

### Étape 3 - Optionnel : push de la nouvelle branche

Ne pas pusher automatiquement (l'utilisateur peut vouloir faire des
commits locaux d'abord). Mentionner la commande dans le récap.

## Format de sortie attendu

```markdown
## /feature-start {{name}} - rapport

**Slug** : {{name}}
**Branche créée** : feature/{{name}}
**Base** : main (HEAD <SHA>)

### Pré-vol
- ✓ Slug valide (kebab-case)
- ✓ Branche courante = main
- ✓ main à jour avec origin/main
- ✓ Working tree propre
- ✓ Branche feature/{{name}} n'existe pas déjà

### Branche créée
git checkout -b feature/{{name}}

### Workflow recommandé suite
- Commits locaux + push -u origin feature/{{name}}
- Merge final --no-ff sur main + push
- Clean branche locale et remote
```

## Anti-patterns

- ❌ **Créer une branche pour une feature S** : commit direct sur
  main est plus efficace. Le point de retour propre est inutile
  pour 1-2 fichiers de fix mineur.
- ❌ **Créer une branche depuis une autre branche feature** : les
  branches feature partent toujours de `main`. Si vous voulez
  empiler des features, utilisez plutôt 1 seule branche pour
  l'ensemble cohérent (ou plusieurs PRs séparées sur main).
- ❌ **Slug avec underscore ou camelCase** : convention kebab-case
  stricte pour cohérence. `dropdown-tp-hybride` ✓,
  `dropdown_tp_hybride` ❌, `dropdownTpHybride` ❌.
- ❌ **Working tree dirty** : commiter ou stasher avant. Sinon les
  modifications en cours suivent la nouvelle branche par accident.
- ❌ **Merge fast-forward (sans --no-ff)** : on perd la trace de la
  branche dans l'historique. Toujours `--no-ff` pour les
  features M+.
- ❌ **Squash and merge** : perte des commits intermédiaires de la
  branche. Difficile pour `git bisect`. Réservé aux cas où la
  branche contient beaucoup de commits intermédiaires de WIP qu'on
  veut effacer (rare).

## Lien avec les autres outils

| Outil | Lien |
|---|---|
| [`conventions/git.md § Branches feature`](../memory/conventions/git.md) | Convention détaillée (seuil M+, naming, merge --no-ff, lien avec `/release-prep`). |
| [`conventions/effort-sizing.md`](../memory/conventions/effort-sizing.md) | Définition des seuils d'effort (XXS / XS / S / M / M+ / L / XL) qui guident la décision « branche ou pas ». |
| [`/release-prep`](release-prep.md) | Le commit release-marker doit être créé sur `main` après merge (pas dans la branche feature). Si `/release-prep` est lancé sur une branche feature, il échoue avec erreur. |

## Quand NE PAS l'utiliser

- Feature S (< 3 h) ou changement doc seul : commit direct sur main
- Bug fix critique en prod : commit direct sur main + push immédiat
  (vitesse > review structurée)
- Refactor purement local (1 fichier, < 50 L) : commit direct
- Doc seule (CLAUDE.md, .claude/memory/, README) : commit direct
