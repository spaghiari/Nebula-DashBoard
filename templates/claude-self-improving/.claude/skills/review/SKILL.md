---
name: review
description: Revue structurée avant de proposer un commit — correctness, sécurité, tests, effets de bord, conventions. Déclencher avant un commit sur une tâche M+ ou sur demande.
---

# Skill : revue pré-commit

Exécute une revue structurée avant de proposer un commit.

## Déclenchement

Quand l'utilisateur demande une revue, ou avant un commit sur une
tâche de taille M+ (cf. `.claude/memory/conventions.md § effort`).

## Étapes

1. Lister les fichiers modifiés : `git diff --name-only` (et
   `git diff --cached --name-only` pour le staged).
2. Pour chaque fichier, vérifier les 5 axes :
   - **Correctness** — le code fait ce qu'il est censé faire ; pas
     d'erreur de logique évidente.
   - **Sécurité** — pas de secret/token exposé, pas d'injection, pas
     de permission trop large.
   - **Tests** — les modifications sont couvertes (ou le noter).
   - **Effets de bord** — imports valides, exports non cassés, pas de
     régression sur les usages distants.
   - **Conventions** — cohérence avec `.claude/memory/conventions.md`
     et pièges connus de `.claude/memory/pitfalls.md`.
3. Vérifier l'absence de résidus : `console.log`, `print()` de debug,
   `TODO`/`FIXME` oubliés, fichiers `.md` ad-hoc non demandés.
4. Résumer : **OK** (une phrase) ou liste des problèmes trouvés, du
   plus grave au plus léger. Pas de faux positif cosmétique.

## Délégation

Pour une revue conséquente (diff large, feature livrée), déléguer à
l'agent `{{name}}-impl-validator` (verdict GO / NO-GO sur 5 axes) ou
`{{name}}-pitfall-auditor` (audit profond des pièges).
