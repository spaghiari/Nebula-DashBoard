---
description: Review pré-MR/PR consolidée d'un diff. Liste les fichiers modifiés, délègue la validation 5 axes à `{{name}}-impl-validator`, vérifie les conventions de commit (em-dash, accents, Co-Authored-By), produit un rapport unifié avec verdict GO / NO-GO. Read-only.
---

Review automatisée d'un diff (branche en cours vs base) avant
commit/MR. Orchestre la validation 5 axes via le sous-agent
`{{name}}-impl-validator` et ajoute la couche conventions de commit
(historique git) que le sous-agent ne voit pas seul.

**Argument** : optionnel, base de comparaison. Défaut : `main..HEAD`
(diff de la branche courante vs `main`).

Exemples :
- `/diff-review` → `main..HEAD`
- `/diff-review origin/main` → `origin/main..HEAD`
- `/diff-review 4.2.0` → `4.2.0..HEAD` (toutes les modifs depuis
  une release ; tags du repo sans préfixe `v`, cf. `git tag -l`)
- `/diff-review feature/xyz` → `feature/xyz..HEAD`

Cette commande **ne modifie rien**. Elle produit un rapport. À toi
de trancher si les violations identifiées sont corrigées avant
commit ou si le verdict GO/NO-GO autorise la publication.

## Prérequis

`/diff-review` s'appuie sur `git diff` et `git log` pour collecter
le périmètre et auditer l'historique des commits (axe 5bis). La
commande **doit s'exécuter dans le thread principal Claude Code**
où Bash est autorisé via la whitelist `permissions.allow` du
`.claude/settings.json` (cf. `git status`, `git diff:*`, `git log:*`).

**Ne pas sous-déléguer à un agent secondaire** (`general-purpose`,
sous-agent ad-hoc) : ces threads tournent en sandbox et bloquent
Bash. La commande échoue alors silencieusement avec un verdict
« INDÉTERMINÉ - exécution bloquée » et `{{name}}-impl-validator` ne peut
pas charger le diff.

Friction observée pendant la validation post-livraison 4.3.0 :
test grandeur nature en sous-agent → échec ; relance en thread
principal → succès. Workaround disponible côté `{{name}}-impl-validator`
**mode 2 (dégradé)** : si l'appelant doit absolument déléguer à un
agent secondaire sandboxé, il peut pré-collecter le diff via Bash
autorisé chez lui (`git diff <range>`) et le passer au validator
entre marqueurs `===DIFF===` / `===END DIFF===` dans le prompt.
Verdict alors suffixé `(mode dégradé : pas d'audit historique
git)`. Détail : `.claude/agents/{{name}}-impl-validator.md` § Modes
d'invocation.

## Méthode

### Étape 1 - Collecte du périmètre

```bash
# Range git (depuis l'argument ou défaut main..HEAD)
RANGE="${ARG:-main..HEAD}"

# Liste des fichiers touchés (ajoutés/modifiés/supprimés)
git diff --name-only "$RANGE"

# Liste des commits du range
git log --oneline "$RANGE"

# Stat global
git diff --stat "$RANGE"
```

Si la liste est vide → arrêter ici, rapporter « Aucun fichier modifié
dans le range `<RANGE>` ».

### Étape 2 - Catégorisation des fichiers

Classer les fichiers touchés selon le tableau de filtrage de
`{{name}}-impl-validator` (cf.
[`.claude/agents/{{name}}-impl-validator.md`](../agents/{{name}}-impl-validator.md)) :

- Code module : `application/`, `library/<Projet>/`,
  `public/css/`, `public/js/`, `public/img/`
- Doc module : `*.md` racine, `CHANGELOG.md`, `README.md` des
  sous-dossiers code
- Outillage Claude : `.claude/agents/`, `.claude/commands/`,
  `.claude/hooks/`, `.claude/memory/`, `CLAUDE.md`,
  `.claude/{ideas,backlog,roadmap,improvements}.md`
- Config : `module.info`, `configuration.php`, `.gitignore`

### Étape 3 - Délégation à `{{name}}-impl-validator`

Si **fichiers code module touchés** (axes 1-2-4 pertinents) :

- Invoquer `{{name}}-impl-validator` avec le range git en entrée
- Le sous-agent retournera la matrice 5 axes + verdict
- Récupérer le rapport tel quel (ne pas le réécrire)

Si **diff doc-only ou outillage Claude only** (axes 1-2-4 N/A) :

- Skip la délégation à `{{name}}-impl-validator`
- Marquer les axes 1, 2, 4 comme « N/A (diff sans code module) »
- Effectuer manuellement les axes 3 et 5

### Étape 4 - Audit complémentaire des commits du range

Le sous-agent `{{name}}-impl-validator` ne voit que les fichiers, pas
l'historique git. Vérifier sur l'historique du range :

```bash
# Présence de Co-Authored-By Claude (interdit, convention équipe)
git log "$RANGE" --pretty=full | grep -i "Co-Authored-By.*Claude"

# Format des messages de commit (type(scope): message)
git log "$RANGE" --pretty=format:'%s' | grep -vE '^(feature|fix|update|push|doc)\(.+\): .+'

# Em-dash dans les messages de commit
git log "$RANGE" --pretty=format:'%s%n%b' | grep '—'

# Accents oubliés (heuristique : mots très courants en français)
git log "$RANGE" --pretty=format:'%s%n%b' | grep -iwE 'amelioration|deplacement|operationnel|deja|apres|ete|coherence|reecrire|recriture'
```

Si une heuristique remonte, signaler le commit et le mot suspect (à
vérifier manuellement, peut être un faux positif si dans un nom
technique).

### Étape 5 - Rapport consolidé

Produire un rapport unique qui :

1. Reprend la matrice 5 axes du sous-agent (si appelé)
2. Ajoute une section « Axe 5bis - Historique git » avec les
   findings de l'étape 4
3. Réajuste le verdict global en intégrant les findings 5bis :
   - Co-Authored-By Claude présent → 🔴 critique → NO-GO
   - Format de commit non conforme → ⚠ mineur → GO avec réserves
   - Em-dash dans message → 🔴 critique → NO-GO
   - Accent suspect → ℹ info → pas d'impact verdict

## Format de sortie

```markdown
## Diff review

**Range** : `<RANGE>` (par ex. `main..HEAD`)
**Commits** : <N> commits
**Fichiers** : <M> fichiers (X ajoutés, Y modifiés, Z supprimés)
**Stat** : +<N>/-<N> lignes

### Commits dans le range

| # | Hash | Message |
|---|---|---|
| 1 | <hash> | <subject> |
| 2 | <hash> | <subject> |
| ... | ... | ... |

### Validation 5 axes (déléguée à `{{name}}-impl-validator`)

[Coller ici la matrice + verdict du sous-agent, OU « N/A - diff sans
code module »]

### Axe 5bis - Historique git

| Vérification | Statut | Détail |
|---|---|---|
| Co-Authored-By Claude | ✅ aucun / 🔴 présent dans <hash> | <détail> |
| Format `type(scope): msg` | ✅ tous / ⚠ <hash> non conforme | <détail> |
| Em-dash dans messages | ✅ aucun / 🔴 présent dans <hash> | <détail> |
| Accents français | ✅ / ℹ <mot suspect dans hash> | <détail> |

### Verdict global

**GO** ✅ : diff prêt à publier (commit final, push, MR).

(ou)

**GO avec réserves** ⚠ : diff publiable mais <N points> à adresser
en commit de suivi. Détails ci-dessus.

(ou)

**NO-GO** 🔴 : <N violations critiques> à corriger avant
publication. Voir détails ci-dessus.

### Actions suggérées

- (si NO-GO) Corriger les <N violations critiques> listées axe X.Y
- (si GO avec réserves) Ouvrir un item backlog P2 pour les points
  mineurs (cf. `.claude/backlog.md`)
- (si GO) Lancer `/check-all` une dernière fois si pas déjà inclus
  dans le verdict du sous-agent
```

## Cas particuliers

### Range vide

Si `git diff --name-only "$RANGE"` ne retourne rien (rien à comparer
ou base déjà identique à HEAD) :

```markdown
## Diff review

**Range** : `<RANGE>`
Aucun fichier modifié dans ce range. Pas de review nécessaire.
```

### Range invalide

Si la base n'existe pas (typo dans la branche/tag) :

```markdown
## Diff review

🔴 Erreur : la base `<base>` n'existe pas dans le repo. Vérifie
l'argument (branche, tag ou commit valide attendu).
```

### Diff trop gros (> 50 fichiers code)

Marquer dans le rapport : « ⚠ Diff > 50 fichiers code, scinder en
plusieurs MR recommandé. Le sous-agent valide quand même mais le
verdict porte sur l'ensemble ».

### Repo sans branche `main`

Si `main` n'existe pas (ex: `master`), demander à l'utilisateur de
préciser la base. Ne pas deviner.

## Anti-patterns

- ❌ **Réécrire le rapport du sous-agent** - reprendre tel quel pour
  cohérence, on ajoute juste l'axe 5bis et ajuste le verdict
- ❌ **Modifier les commits ou les fichiers** - lecture seule
  stricte, l'utilisateur tranche
- ❌ **Faux positifs accents systématiques** - ne signaler que les
  mots qui sont clairement français, pas les noms techniques
  (`tete`, `fr`, etc.)
- ❌ **Cascade > 2 niveaux** - si `{{name}}-impl-validator` délègue à
  `{{name}}-pitfall-auditor`, ne pas re-déléguer encore
- ❌ **Ignorer Co-Authored-By Claude** - convention équipe stricte,
  toujours bloquer

## Cycle recommandé

| Quand | Pourquoi |
|---|---|
| Avant chaque MR/PR | Validation pré-publication systématique |
| Avant un push d'une branche feature | Catch les violations avant qu'elles n'arrivent dans la branche partagée |
| Avant un release tag | Audit final de la diff `X.Y.Z..HEAD` (tags sans préfixe `v` ; `git fetch` au préalable si tag créé via UI GitLab) |
| Après une session multi-commits | Vérification globale de la cohérence |

## Lien avec les autres outils

| Outil | Lien |
|---|---|
| [`{{name}}-impl-validator`](../agents/{{name}}-impl-validator.md) | Délégué pour les axes 1-4 (matrice 5 axes) |
| [`{{name}}-pitfall-auditor`](../agents/{{name}}-pitfall-auditor.md) | Délégué en cascade par `{{name}}-impl-validator` pour l'axe 1 si > 3 fichiers critiques |
| [`/check-all`](check-all.md) | Lints + check-pitfalls + readme-sync. Inclus dans le verdict du sous-agent |
| [`/check-pitfalls`](check-pitfalls.md) | 27 pitfalls. Inclus dans l'axe 1 |
| [`/contracts-audit`](contracts-audit.md) | Audit ciblé 1 fichier. Plus rapide si 1 seul fichier modifié |
