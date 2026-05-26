---
description: Orchestre les commandes de vérification automatisées du projet (linters + audits structurels) et produit un rapport consolidé. À instancier par projet selon sa stack technique.
---

Lance en séquence les commandes de vérification du projet, puis
consolide en un tableau de synthèse unique.

> **Ce fichier est un template.** Le projet doit le compléter avec la
> séquence réelle de ses linters et audits, et créer les slash
> commands correspondants (`/lint-<langage>`, etc.) dans
> `.claude/commands/`. La structure ci-dessous reste valide quel que
> soit le détail.

## Structure recommandée en 3 phases

### Phase 1 - Fail-fast syntaxique (séquentiel obligatoire)

(À instancier selon la stack du projet. Ex : `/lint-<langage>` qui
vérifie la syntaxe du langage principal. Si parse error : STOPPER
ICI - les autres lints porteraient des faux positifs sur du code
invalide.)

### Phase 2 - Lints indépendants (parallélisable)

Les linters non-syntaxiques sont **indépendants** entre eux et
peuvent être exécutés en parallèle après le fail-fast Phase 1.
Regrouper les appels Bash/Grep dans un même message (cf.
[`conventions/parallelization.md`](../memory/conventions/parallelization.md)).

Exemples typiques :
- Lint d'un autre langage (CSS, JS, HTML, ...) si applicable
- Vérifications de conventions de code (longueur de ligne, em-dash,
  accents, indentation)
- Vérifications de structure (PHPDoc, JSDoc, docstrings)

### Phase 3 - Audits structurels (parallélisable)

Audits transverses indépendants des linters :
- `/check-pitfalls` (à créer pour le projet selon `pitfalls.md`)
- `/readme-sync` (cohérence READMEs sous-dossiers + hubs/spokes
  mémoire)

## Format de sortie consolidé

```markdown
## /check-all - rapport YYYY-MM-DD

| # | Commande | Statut | N items | Notes |
|---|---|---|---|---|
| 1 | /lint-<langage> | ✅ / ⚠ / ❌ | n | <résumé court> |
| 2 | /lint-<autre> | ... | ... | ... |
| 3 | /check-pitfalls | ... | ... | ... |
| 4 | /readme-sync | ... | ... | ... |

### Items à traiter

(Pour chaque ❌ ou ⚠, lien vers la commande détaillée + 1 ligne
résumé)

### Verdict global

- ✅ **GO** : aucun bloquant, le code peut être commité.
- ⚠ **GO avec réserves** : items non-bloquants à examiner.
- ❌ **NO-GO** : bloquants identifiés, fixer avant commit.
```

## Cycle d'invocation

| Quand | Pourquoi |
|---|---|
| Après tout edit non-trivial | Vérification de base avant commit |
| Avant commit conséquent | Validation pré-commit |
| Avant release majeure | Validation pré-release (en plus des tests manuels) |
| Sur signal | Si un linter ou audit identifie un faux positif récurrent → friction inscrite dans `improvements.md` |

## Anti-patterns

- **Skipper Phase 1** : faire les lints CSS/JS avant le lint syntaxique
  principal = bruit énorme sur du code cassé.
- **Tableau sans verdict** : si le tableau dit 17 problèmes sans
  hiérarchie, ce n'est pas actionnable. Préférer 5 items priorisés.
- **Auto-fix sans validation** : les linters de Phase 2 peuvent
  proposer des fix automatiques. Dans le contexte `/check-all`, mode
  **rapport-seulement** : lister les fichiers qui seraient modifiés,
  sans appliquer le fix.

Lance la séquence. Produis le rapport. Stop.
