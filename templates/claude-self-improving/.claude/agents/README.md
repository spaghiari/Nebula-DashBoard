# Claude Code agents - `{{label}}`

Sous-agents spécialisés du projet. Chaque fichier `.md` à frontmatter
YAML est un agent invocable par Claude Code (CLI ou via délégation
depuis un autre agent).

## Agents fournis par le template

| Fichier (template) | Rôle | Quand l'invoquer |
|---|---|---|
| `{{name}}-expert.md.example` | Expert exhaustif du projet pour les tâches non-triviales (review, design, impl, refactor, bug fix, release) | Feature M (10-20 fichiers), design non-trivial, review pré-commit conséquent, bug fix multi-fichiers |
| `{{name}}-impl-validator.md.example` | Validation d'impl finie : 5 axes (pitfalls, lints, docs, tests manuels, conventions globales) avec verdict GO / NO-GO | Fin de mode impl de l'expert, slash command `/diff-review`, validation pré-MR |
| `{{name}}-pitfall-auditor.md.example` | Audit profond du registre `pitfalls/` sur 1 fichier ou diff. Format de sortie standardisé | Review pré-commit profonde, validation de feature livrée, post-mortem de bug |

> **Note** : les fichiers fournis par le template ont l'extension
> `.md.example`. Pour les activer dans le projet, les renommer en
> `.md` en remplaçant `{{name}}` par le préfixe court retenu pour le
> projet (déclaré dans `memory/overview.md`).

## Conventions

Chaque agent commence par un frontmatter YAML standard :

```yaml
---
name: {{name}}-xxx
description: <rôle court, capacités, coût attendu>
tools: All tools
---
```

- **Préfixe `{{name}}-`** systématique (cohérence avec les autres
  identifiants du projet, par exemple `app-` pour un projet « MyApp »).
- **Suffixe descriptif court** : `-expert`, `-auditor`, `-keeper`,
  `-validator`, `-syncer`, `-compiler`.

## Pattern de délégation

Documenté dans
[`.claude/memory/conventions/multi-agent.md`](../memory/conventions/multi-agent.md).

`{{name}}-expert` peut déléguer à un sous-agent persistant ou à un
fork (Agent sans `subagent_type`) selon la nature de la sous-tâche
(parallélisation, isolation de contexte, spécialisation profonde).

## Ajouter un nouveau sous-agent

1. Créer `.claude/agents/{{name}}-<nom>.md` avec frontmatter YAML.
2. Définir un format de sortie standardisé dans le corps.
3. Tester en local (invocable via `Task` dans Claude Code).
4. Ajouter à la table « Agents installés » de ce fichier.
5. Mentionner dans l'agent parent (`{{name}}-expert.md`) si délégation
   prévue.
6. Inscrire au registre `.claude/improvements.md` (DONE) si l'ajout
   répond à un item identifié.

Critère d'opportunité : créer un sous-agent quand un pattern de
délégation se répète et qu'un format de sortie standardisé émerge.
Sinon préférer le fork ad-hoc.

## Sous-agent suggéré pour le mode équipe : `{{name}}-digest-compiler`

Si le projet est en mode équipe avec digests actifs (cf.
`memory/overview.md § Mode projet`), créer un sous-agent dédié au
compilage du digest hebdomadaire :

- **Rôle** : agrégation pure (sources structurées → digest formaté).
- **Tools** : Read, Grep, Bash (`git log`, `git diff`).
- **Format de sortie** : aligné sur
  [`conventions/digests.md`](../memory/conventions/digests.md).
- **Invocation** : par la slash command `/digest-week` ou
  directement.

Voir le template `{{name}}-digest-compiler.md.example` (à créer pour
le projet).
