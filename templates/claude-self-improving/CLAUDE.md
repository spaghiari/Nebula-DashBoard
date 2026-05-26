# CLAUDE.md

Mémoire projet **always-on** pour `{{label}}`. Le détail thématique
vit dans `.claude/memory/` (sommaire en bas).

> **Ce fichier est issu d'un template.** À l'instanciation, remplacer
> `{{label}}` par le nom du projet, `{{name}}-` par le préfixe court
> retenu pour les agents et identifiants (par exemple `am-` pour le
> projet AstreinteManager d'origine). Voir `.claude/memory/overview.md`
> pour les autres décisions de bootstrap.

## Règles ALWAYS-ON (à appliquer sans relecture)

### Communication

- **Langue projet** : à déclarer dans `memory/overview.md`. Tous les
  artefacts rédigés dans cette langue : commentaires de code, doc
  inline, READMEs, CHANGELOG, ce fichier ET messages de commit git.
- **Cite `file:line`** pour toute référence de code - ne paraphrase
  jamais une ligne importante.
- **Conventions typographiques** (em-dash, caractères accentués,
  encodage) déclarées dans `memory/conventions/` et enforced par
  hooks de pre-commit (`.claude/hooks/`).

### Édition

- **Ne crée jamais de `.md` ad-hoc** à la racine (plan, analyse,
  notes temporaires) sans demande explicite. Travaille depuis le
  contexte conversationnel. Fichiers `.md` modifiables sans demande :
  ceux qui existent (READMEs, CLAUDE.md, CHANGELOG, CONTRIBUTING),
  `.claude/commands/*.md`, `.claude/memory/**/*.md`,
  `.claude/digests/**/*.md`.
- **Ne touche jamais** à `CLAUDE.local.md`, `.claude/settings.local.json`
  ni à la mémoire user-locale `~/.claude/projects/.../memory/` (gérée
  par Claude Code, refus du hook `protect-local-files.sh`).
- **Délégation à `{{name}}-expert` par défaut pour les tâches
  conséquentes** (feature M+ / 10-20 fichiers, bug fix multi-fichiers
  3+, refactor à effets de bord, design non-trivial). Ne pas
  court-circuiter sous prétexte que le cache mémoire est warm. Détail :
  [`conventions/multi-agent.md`](.claude/memory/conventions/multi-agent.md).
- **Après un edit du module**, lancer `/check-all` (à instancier
  selon les linters du projet). Si fichier ajouté/supprimé/renommé :
  aussi `/readme-sync`.
- **Classification mémoire user-locale vs projet versionnée** : avant
  TOUTE écriture de mémoire, appliquer le test à 3 questions de
  [`conventions/memory-classification.md`](.claude/memory/conventions/memory-classification.md).
  Mémoire user-locale = strict minimum (profil utilisateur). Conventions
  de comportement Claude sur le projet -> `.claude/memory/` versionné.
  **La mémoire projet s'auto-suffit.**

### Pipeline d'auto-amélioration (5 registres versionnés)

Quand un signal d'amélioration émerge, **proposer** son ajout au
registre correspondant à l'utilisateur **avant la fin du turn** -
jamais d'ajout silencieux :

| Signal | Registre | Recettes |
|---|---|---|
| Idée pré-engagement (à trier vers backlog/roadmap/improvements) | [`ideas.md`](.claude/ideas.md) | [`conventions/ideas-generation.md`](.claude/memory/conventions/ideas-generation.md) |
| Action différée court terme (refactor, fix, idée validée) avec priorité P0/P1/P2 | [`backlog.md`](.claude/backlog.md) | [`conventions/backlog.md`](.claude/memory/conventions/backlog.md) |
| Évolution majeure long terme (vision, axes stratégiques, jalons par version) | [`roadmap.md`](.claude/roadmap.md) | [`conventions/roadmap.md`](.claude/memory/conventions/roadmap.md) |
| Friction observée sur Claude / sous-agent / slash command / mémoire | [`improvements.md`](.claude/improvements.md) | [`conventions/self-improvement.md`](.claude/memory/conventions/self-improvement.md) |
| Synthèse hebdomadaire à pousser au N+1 ou reçue d'un N-1 | [`digests/`](.claude/digests/) | [`conventions/digests.md`](.claude/memory/conventions/digests.md) |
| Pattern qui se cristallise (bug post-mortem, convention, sous-système) | mémoire `.claude/memory/<thème>.md` | [`conventions/memory-enrichment.md`](.claude/memory/conventions/memory-enrichment.md) |

Pipeline unifié 4 stages (IDEAS / VALIDATED / IN PROGRESS / DONE) :
[`conventions/pipeline.md`](.claude/memory/conventions/pipeline.md).
Cycle de vie des items DONE (cristallisation patterns + archivage) :
[`conventions/done-lifecycle.md`](.claude/memory/conventions/done-lifecycle.md).
Mesure de l'effort des features (XXS-XXL + humain vs IA) :
[`conventions/effort-sizing.md`](.claude/memory/conventions/effort-sizing.md).

### Attribution d'auteur (équipe)

**Pour les projets en mode équipe** (cf. `memory/overview.md § Mode
projet`), **tout item ajouté à un registre** (`ideas`, `backlog`,
`roadmap`, `improvements`, `digests`) **doit comporter le champ
`par <author>`** :

```
- **[STATUT] <titre>** (Pn, ajouté YYYY-MM-DD par <author>)
```

Pour les items DONE livrés par un autre que l'auteur initial,
ajouter aussi `livré par <author>` dans le bloc DONE.

L'identifiant `<author>` suit la convention déclarée dans
`memory/overview.md § Identité auteur` (par défaut : `git config
user.name` court, par exemple `antoine.b`). Le hook
`improvements-validate.sh` valide la présence du champ au commit
quand le mode équipe est actif.

Pour les projets en **mode solo**, l'auteur est implicite (le
mainteneur unique) et peut être omis - mais l'inclure
systématiquement n'est jamais une erreur.

### Git

- **Pas de commit/push sans demande explicite**. Présenter un diff
  propre, attendre validation, puis commiter au format `type(scope):
  message` avec `type ∈ {feature, fix, update, push, doc}`.
- **Pas de trailer `Co-Authored-By: Claude`** dans aucun commit
  (convention configurable - cf. `.claude/hooks/co-authored-by-precommit.sh`).
- **Convention de mention de version dans le code** : voir
  `conventions/git.md` une fois ce fichier produit pour le projet.

### Pièges silencieux à toujours garder en tête

(À compléter par le projet en fonction de sa stack. Voir
[`pitfalls.md`](.claude/memory/pitfalls.md) et ses spokes
`pitfalls/<catégorie>.md`.)

## Outillage Claude (slash commands, agents, hooks)

Slash commands, sous-agents, hooks et settings documentés dans
[`claude-tooling.md`](.claude/memory/claude-tooling.md). Slash commands
génériques fournis par le template :

- `/pipeline` — vue synthétique des 5 registres.
- `/brainstorm <topic>` — production proactive d'idées (mode
  audit-driven pour topics code-rattachés).
- `/self-review` — audit READ-ONLY des outils Claude eux-mêmes
  (cohérence des pointeurs, hubs/spokes, registres).
- `/diff-review` — validation pré-MR via sous-agent validator.
- `/feature-start {{name}}` — création de branche feature/{{name}}.
- `/readme-sync` — cohérence READMEs sous-dossiers.
- `/check-all` — orchestration des linters/audits projet (à
  instancier selon stack).
- `/digest-week` — production du digest hebdomadaire (cf.
  `conventions/digests.md`).

Sous-agents génériques : `{{name}}-expert` (feature M+), 
`{{name}}-impl-validator` (validation 5 axes), `{{name}}-pitfall-auditor`
(audit pitfalls profond). À instancier pour le projet.

## Mémoire détaillée - sommaire `.claude/memory/`

Le projet utilise un modèle hub-and-spoke : un fichier hub thématique
au niveau racine de `memory/`, et un dossier `<thème>/` avec des
spokes détaillés quand le contenu grossit. Lire le hub pertinent
**avant d'agir** sur la tâche correspondante.

| Hub | Quand le lire |
|---|---|
| [`overview.md`](.claude/memory/overview.md) | Démarrage, mode projet (solo/équipe), identité auteur, layout, commandes ops |
| [`domain.md`](.claude/memory/domain.md) | Toute tâche métier sur le domaine du projet |
| [`architecture.md`](.claude/memory/architecture.md) | Toucher au code structurant (modules, services, couches) |
| [`security.md`](.claude/memory/security.md) | **Avant tout traitement de donnée sensible / mutation** (hub avec spokes) |
| [`frontend.md`](.claude/memory/frontend.md) | Édition d'interface, UI, styling (hub avec spokes si applicable) |
| [`subsystems.md`](.claude/memory/subsystems.md) | Toucher à un sous-système optionnel ou périphérique (hub avec spokes) |
| [`performance.md`](.claude/memory/performance.md) | Optimisation, requête lourde, batching, cache |
| [`conventions.md`](.claude/memory/conventions.md) | Workflow git, tests, hooks, conventions code, pipeline, sizing, done-lifecycle, **digests** (hub avec spokes) |
| [`pitfalls.md`](.claude/memory/pitfalls.md) | **Avant tout edit non-trivial** : registre des pièges silencieux par catégorie (hub avec spokes) |
| [`diagnostics.md`](.claude/memory/diagnostics.md) | Troubleshooting incident, paths logs, outils diagnostic |
| [`claude-tooling.md`](.claude/memory/claude-tooling.md) | Slash commands, agents, hooks, settings (vue d'ensemble) |
